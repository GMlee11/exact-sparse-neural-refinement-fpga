"""Preflight hierarchical mask-aware sparse refinement.

The proposed engine traverses one frame coordinate space instead of restarting
the neural pipeline for every compacted region. Conv3 computes only selected
output positions. Conv2 and Conv1 use one- and two-pixel dilations so every
value in the selected Conv3 receptive field is still exact. A third dilation
identifies the LR pixels that must cross the external interface.

This module is deliberately an architecture gate, not a board result. It uses
the frozen physical worklist and measured balanced-engine cycles, but labels
all new cycle and traffic values as estimates until RTL and physical capture
replace them.
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import numpy as np
import yaml


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "configs" / "sparse_refinement_hierarchical_mask_v1.yaml"
DEFAULT_JSON = ROOT / "results" / "tables" / "sparse_refinement_hierarchical_mask_preflight.json"
DEFAULT_MARKDOWN = ROOT / "results" / "tables" / "sparse_refinement_hierarchical_mask_preflight.md"


# Store one layer's mask population and cycle estimate as an immutable record.
@dataclass(frozen=True)
class MaskLayerEstimate:
    """One layer's selected positions and conservative service estimate."""

    name: str
    dilation_pixels: int
    active_positions: int
    inactive_positions: int
    active_fraction: float
    issue_cycles_per_active_position: int
    estimated_cycles: int


# Expand a binary mask by a clipped square radius without requiring SciPy.
def dilate_mask(mask: np.ndarray, radius: int) -> np.ndarray:
    """Return a clipped square/Chebyshev dilation without SciPy dependency."""

    source = np.asarray(mask, dtype=bool)
    if source.ndim != 2:
        raise ValueError("mask must have height-by-width rank 2")
    if radius < 0:
        raise ValueError("mask radius must be nonnegative")
    if radius == 0:
        return source.copy()

    height, width = source.shape
    padded = np.pad(source, radius, mode="constant", constant_values=False)
    result = np.zeros_like(source)
    for row_offset in range(2 * radius + 1):
        for column_offset in range(2 * radius + 1):
            result |= padded[
                row_offset : row_offset + height,
                column_offset : column_offset + width,
            ]
    return result


# Convert frozen work-list rectangles into one overlap-checked pixel mask.
def selected_mask_from_manifest(
    manifest: dict[str, object],
    *,
    width: int,
    height: int,
    tile_width: int,
    tile_height: int,
) -> np.ndarray:
    """Rasterize frozen descriptors and reject overlap or off-grid geometry."""

    rows = manifest.get("original_descriptors")
    if not isinstance(rows, list) or not rows:
        raise ValueError("worklist manifest has no original descriptors")
    selected = np.zeros((height, width), dtype=bool)
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("worklist descriptor must be a mapping")
        x = int(row["core_x"])
        y = int(row["core_y"])
        core_width = int(row["core_width"])
        core_height = int(row["core_height"])
        if (
            x < 0
            or y < 0
            or x + core_width > width
            or y + core_height > height
            or x % tile_width
            or y % tile_height
            or core_width % tile_width
            or core_height % tile_height
        ):
            raise ValueError("worklist descriptor is outside the macro-tile grid")
        view = selected[y : y + core_height, x : x + core_width]
        if np.any(view):
            raise ValueError("worklist descriptors overlap")
        view[:] = True
    return selected


# Match the RTL's signed ties-away-from-zero requantization rule.
def _round_ties_away(values: np.ndarray, shift: int) -> np.ndarray:
    """Apply deterministic signed integer rounding for the exactness check."""

    magnitude = np.abs(values)
    rounded = (magnitude + (1 << (shift - 1))) >> shift
    return np.where(values < 0, -rounded, rounded)


# Execute a compact integer convolution used only to prove mask dependencies.
def _toy_conv_q7(
    activation: np.ndarray,
    weights: np.ndarray,
    bias: np.ndarray,
    *,
    relu: bool,
    shift: int = 3,
) -> np.ndarray:
    """Run a small deterministic 3x3 integer layer for dependency verification."""

    height, width, input_channels = activation.shape
    output_channels = weights.shape[0]
    if weights.shape[1:] != (input_channels, 3, 3):
        raise ValueError("toy convolution weight dimensions are inconsistent")
    padded = np.pad(activation.astype(np.int64), ((1, 1), (1, 1), (0, 0)))
    accumulators = np.broadcast_to(
        bias.astype(np.int64), (height, width, output_channels)
    ).copy()
    for kernel_row in range(3):
        for kernel_column in range(3):
            samples = padded[
                kernel_row : kernel_row + height,
                kernel_column : kernel_column + width,
                :,
            ]
            kernel = weights[:, :, kernel_row, kernel_column]
            accumulators += np.tensordot(samples, kernel, axes=([2], [1]))
    output = _round_ties_away(accumulators, shift)
    if relu:
        output = np.maximum(output, 0)
    return np.clip(output, -128, 127).astype(np.int8)


# Check that two/one/zero mask radii preserve every selected three-layer output.
def verify_hierarchical_exactness(seed: int = 20260804) -> bool:
    """Prove selected outputs survive hierarchical zero-insertion exactly."""

    rng = np.random.default_rng(seed)
    height, width = 13, 17
    activation = rng.integers(-32, 33, size=(height, width, 3), dtype=np.int8)
    weights1 = rng.integers(-4, 5, size=(5, 3, 3, 3), dtype=np.int8)
    weights2 = rng.integers(-4, 5, size=(5, 5, 3, 3), dtype=np.int8)
    weights3 = rng.integers(-4, 5, size=(12, 5, 3, 3), dtype=np.int8)
    biases1 = rng.integers(-16, 17, size=5, dtype=np.int32)
    biases2 = rng.integers(-16, 17, size=5, dtype=np.int32)
    biases3 = rng.integers(-16, 17, size=12, dtype=np.int32)

    selected = np.zeros((height, width), dtype=bool)
    selected[3:8, 4:11] = True
    selected[9:12, 13:16] = True
    conv1_mask = dilate_mask(selected, 2)
    conv2_mask = dilate_mask(selected, 1)

    full1 = _toy_conv_q7(activation, weights1, biases1, relu=True)
    full2 = _toy_conv_q7(full1, weights2, biases2, relu=True)
    full3 = _toy_conv_q7(full2, weights3, biases3, relu=False)

    masked1 = _toy_conv_q7(activation, weights1, biases1, relu=True)
    masked1[~conv1_mask] = 0
    masked2 = _toy_conv_q7(masked1, weights2, biases2, relu=True)
    masked2[~conv2_mask] = 0
    masked3 = _toy_conv_q7(masked2, weights3, biases3, relu=False)
    masked3[~selected] = 0
    return bool(np.array_equal(full3[selected], masked3[selected]))


# Exercise the dependency rule over many disconnected, edge-touching, and
# randomly fragmented selections rather than relying on one illustrative mask.
def verify_hierarchical_exactness_suite(
    seed: int = 20260805,
    *,
    trials: int = 64,
) -> bool:
    """Property-test three-layer dependency closure across random masks."""

    if trials <= 0:
        raise ValueError("trials must be positive")
    rng = np.random.default_rng(seed)
    height, width = 11, 14
    for _ in range(trials):
        activation = rng.integers(-32, 33, size=(height, width, 3), dtype=np.int8)
        weights1 = rng.integers(-4, 5, size=(4, 3, 3, 3), dtype=np.int8)
        weights2 = rng.integers(-4, 5, size=(4, 4, 3, 3), dtype=np.int8)
        weights3 = rng.integers(-4, 5, size=(12, 4, 3, 3), dtype=np.int8)
        biases1 = rng.integers(-16, 17, size=4, dtype=np.int32)
        biases2 = rng.integers(-16, 17, size=4, dtype=np.int32)
        biases3 = rng.integers(-16, 17, size=12, dtype=np.int32)
        selected = rng.random((height, width)) < rng.uniform(0.02, 0.75)
        selected[rng.integers(0, height), rng.integers(0, width)] = True

        conv1_mask = dilate_mask(selected, 2)
        conv2_mask = dilate_mask(selected, 1)
        full1 = _toy_conv_q7(activation, weights1, biases1, relu=True)
        full2 = _toy_conv_q7(full1, weights2, biases2, relu=True)
        full3 = _toy_conv_q7(full2, weights3, biases3, relu=False)

        masked1 = full1.copy()
        masked1[~conv1_mask] = 0
        masked2 = _toy_conv_q7(masked1, weights2, biases2, relu=True)
        masked2[~conv2_mask] = 0
        masked3 = _toy_conv_q7(masked2, weights3, biases3, relu=False)
        if not np.array_equal(full3[selected], masked3[selected]):
            return False
    return True


# Combine frozen geometry, cycle evidence, and gate thresholds into one report.
def analyze_contract(config: dict[str, object]) -> dict[str, object]:
    """Calculate mask populations, cycle bounds, traffic, and gate status."""

    geometry = config["geometry"]
    pipeline = config["pipeline"]
    transport = config["transport"]
    evidence = config["evidence"]
    gate = config["acceptance"]
    if not all(
        isinstance(section, dict)
        for section in (geometry, pipeline, transport, evidence, gate)
    ):
        raise ValueError("hierarchical-mask contract sections must be mappings")

    manifest_path = ROOT / str(evidence["worklist_manifest"])
    physical_path = ROOT / str(evidence["balanced_physical_report"])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    physical = json.loads(physical_path.read_text(encoding="utf-8"))
    width = int(geometry["lr_width"])
    height = int(geometry["lr_height"])
    tile_width = int(geometry["tile_width"])
    tile_height = int(geometry["tile_height"])
    frame_positions = width * height
    selected = selected_mask_from_manifest(
        manifest,
        width=width,
        height=height,
        tile_width=tile_width,
        tile_height=tile_height,
    )

    overhead = int(pipeline["active_control_overhead_cycles"])
    bypass_cycles = int(pipeline["bypass_cycles_per_inactive_position"])
    layers: list[MaskLayerEstimate] = []
    masks: dict[str, np.ndarray] = {}
    rows = pipeline.get("convolution_layers")
    if not isinstance(rows, list) or len(rows) != 3:
        raise ValueError("hierarchical pipeline must declare three layers")
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("convolution layer must be a mapping")
        name = str(row["name"])
        radius = int(row["selected_mask_dilation_pixels"])
        layer_mask = dilate_mask(selected, radius)
        masks[name] = layer_mask
        active = int(layer_mask.sum())
        inactive = frame_positions - active
        issue = int(row["issue_cycles_per_active_position"])
        layers.append(
            MaskLayerEstimate(
                name=name,
                dilation_pixels=radius,
                active_positions=active,
                inactive_positions=inactive,
                active_fraction=active / frame_positions,
                issue_cycles_per_active_position=issue,
                estimated_cycles=active * (issue + overhead) + inactive * bypass_cycles,
            )
        )

    if not (
        np.all(masks["conv3"] <= masks["conv2"])
        and np.all(masks["conv2"] <= masks["conv1"])
    ):
        raise RuntimeError("hierarchical masks are not nested")
    raw_mask = dilate_mask(selected, int(geometry["receptive_field_radius"]))
    startup = int(pipeline["frame_startup_cycles"])
    output_cycles = int(selected.sum()) * int(
        pipeline["output_cycles_per_selected_lr_position"]
    )
    estimated_cycles = max(
        max(layer.estimated_cycles for layer in layers),
        frame_positions,
        output_cycles,
    ) + startup
    measured_cycles = int(physical["scenarios"]["frame"]["balanced"]["average_compute_cycles"])
    cycle_reduction = 100.0 * (1.0 - estimated_cycles / measured_cycles)
    clock_hz = int(pipeline["fabric_clock_hz"])
    compute_ms = estimated_cycles * 1000.0 / clock_hz
    required_clock_hz = math.ceil(estimated_cycles / (float(gate["realtime_deadline_ms"]) / 1000.0))

    axis_word_bytes = int(transport["axis_word_bytes"])
    selected_lr_positions = int(selected.sum())
    selected_hr_pixels = selected_lr_positions * int(geometry["scale"]) ** 2
    current_packet_words = int(manifest["traffic"]["compact_packet_words"])
    current_words = current_packet_words + selected_hr_pixels
    proposed_words = int(raw_mask.sum()) + selected_hr_pixels
    proposed_bytes = (
        proposed_words * axis_word_bytes
        + int(transport["tile_mask_bytes"])
        + int(transport["frame_header_bytes"])
    )
    current_bytes = current_words * axis_word_bytes
    traffic_reduction = 100.0 * (1.0 - proposed_bytes / current_bytes)

    exact = verify_hierarchical_exactness() and verify_hierarchical_exactness_suite()
    compute_pass = cycle_reduction >= float(
        gate["minimum_estimated_compute_cycle_reduction_percent"]
    )
    traffic_pass = traffic_reduction >= float(
        gate["minimum_estimated_axis_traffic_reduction_percent"]
    )
    authorized = exact and compute_pass and traffic_pass
    return {
        "schema_version": 1,
        "artifact": "sparse_refinement_hierarchical_mask_preflight_v1",
        "experiment_id": config["experiment_id"],
        "decision": (
            "authorize_masked_rtl_prototype" if authorized else "reject_before_rtl"
        ),
        "selected_workload": {
            "source_descriptors": int(manifest["source_descriptors"]),
            "compacted_regions": int(manifest["compacted_regions"]),
            "selected_lr_positions": selected_lr_positions,
            "selected_fraction": selected_lr_positions / frame_positions,
            "raw_dependency_positions": int(raw_mask.sum()),
        },
        "layers": [layer.__dict__ for layer in layers],
        "cycle_estimate": {
            "measured_balanced_region_cycles": measured_cycles,
            "estimated_masked_pipeline_cycles": estimated_cycles,
            "estimated_reduction_percent": cycle_reduction,
            "estimated_compute_ms_at_routed_clock": compute_ms,
            "realtime_deadline_ms": float(gate["realtime_deadline_ms"]),
            "estimated_realtime_pass": compute_ms <= float(gate["realtime_deadline_ms"]),
            "minimum_clock_hz_for_compute_deadline": required_clock_hz,
        },
        "axis_traffic_estimate": {
            "current_balanced_region_bytes": current_bytes,
            "proposed_sparse_residual_bytes": proposed_bytes,
            "estimated_reduction_percent": traffic_reduction,
            "classical_base_owner": transport["classical_base_owner"],
        },
        "exactness": {
            "hierarchical_dependency_check": exact,
            "conv1_contains_conv2": bool(np.all(masks["conv2"] <= masks["conv1"])),
            "conv2_contains_conv3": bool(np.all(masks["conv3"] <= masks["conv2"])),
        },
        "gate": {
            "compute_reduction_pass": compute_pass,
            "traffic_reduction_pass": traffic_pass,
            "exactness_pass": exact,
            "authorized": authorized,
        },
        "evidence_boundary": {
            "new_values_are_estimates": True,
            "selector_generalization_claimed": False,
            "energy_claimed": False,
            "accepted_worklists": evidence["accepted_worklists"],
            "excluded_claims": evidence["excluded_claims"],
        },
    }


# Render the preflight result as a compact human-readable evidence table.
def render_markdown(result: dict[str, object]) -> str:
    """Render an advisor-readable preflight report."""

    layers = result["layers"]
    cycles = result["cycle_estimate"]
    traffic = result["axis_traffic_estimate"]
    rows = "\n".join(
        f"| {row['name']} | {row['dilation_pixels']} | {row['active_positions']:,} | "
        f"{100.0 * row['active_fraction']:.2f}% | {row['estimated_cycles']:,} |"
        for row in layers
    )
    return f"""# Hierarchical Mask-Aware Sparse Accelerator Preflight

| Layer | Mask dilation | Active LR positions | Active fraction | Estimated cycles |
|---|---:|---:|---:|---:|
{rows}

| Gate quantity | Result |
|---|---:|
| Exact selected-output dependency check | `{result['exactness']['hierarchical_dependency_check']}` |
| Measured balanced-region cycles | {cycles['measured_balanced_region_cycles']:,} |
| Estimated persistent masked cycles | {cycles['estimated_masked_pipeline_cycles']:,} |
| Estimated compute-cycle reduction | {cycles['estimated_reduction_percent']:.2f}% |
| Estimated compute time at 100 MHz | {cycles['estimated_compute_ms_at_routed_clock']:.3f} ms |
| Minimum clock for 33.33-ms compute | {cycles['minimum_clock_hz_for_compute_deadline'] / 1e6:.2f} MHz |
| Estimated AXI traffic reduction | {traffic['estimated_reduction_percent']:.2f}% |
| Decision | `{result['decision']}` |

This authorizes an RTL prototype because the architecture estimates exceed the
locked compute and traffic gates while preserving selected output dependencies.
It does not claim measured speed, selector generalization, or energy. At the
currently routed 100-MHz clock, even the estimate remains above 33.33 ms.
"""


# Define the command-line paths while preserving reproducible repository defaults.
def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse reproducible contract and output paths."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--output-markdown", type=Path, default=DEFAULT_MARKDOWN)
    return parser.parse_args(argv)


# Run the preflight, write tracked artifacts, and fail when the locked gate fails.
def main(argv: Sequence[str] | None = None) -> int:
    """Run the preregistered preflight and materialize its evidence."""

    args = parse_args(argv)
    config = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    if not isinstance(config, dict) or int(config.get("schema_version", -1)) != 1:
        raise ValueError("hierarchical-mask config must be a schema-v1 mapping")
    result = analyze_contract(config)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_markdown.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="ascii"
    )
    args.output_markdown.write_text(render_markdown(result), encoding="ascii")
    if not result["gate"]["authorized"]:
        raise RuntimeError("hierarchical-mask preflight gate failed")
    print(
        "SPARSE_HIERARCHICAL_MASK_PREFLIGHT_PASS "
        f"cycle_reduction={result['cycle_estimate']['estimated_reduction_percent']:.6f} "
        f"traffic_reduction={result['axis_traffic_estimate']['estimated_reduction_percent']:.6f}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
