"""Build the controlled evidence package for the sparse SR accelerator paper.

The report aligns four execution organizations around one trained INT8 model:
dense full-frame execution, independent halo jobs, rectangle compaction, and
the persistent hierarchical-mask dataflow. Complete physical measurements stay
separate from calibrated sensitivity projections so the paper cannot
accidentally present analytical values as board results.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

import numpy as np
import yaml

from src.hardware.analyze_sparse_hierarchical_mask import (
    dilate_mask,
    verify_hierarchical_exactness_suite,
)


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "configs" / "sparse_accelerator_paper_v1.yaml"
DEFAULT_JSON = ROOT / "results" / "tables" / "sparse_accelerator_paper_v1.json"
DEFAULT_MARKDOWN = ROOT / "results" / "tables" / "sparse_accelerator_paper_v1.md"
DEFAULT_LATEX = ROOT / "docs" / "paper" / "generated" / "sparse_accelerator_paper_v1.tex"


# Load one tracked physical report and reject missing or malformed artifacts.
def _load_report(relative_path: str) -> dict[str, object]:
    """Load a repository-relative JSON evidence artifact."""

    path = ROOT / relative_path
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"evidence report is not a JSON object: {relative_path}")
    return payload


# Expand one row-major macro-tile decision into its exact LR pixel support.
def tile_grid_to_pixel_mask(
    tile_grid: np.ndarray,
    *,
    tile_width: int,
    tile_height: int,
) -> np.ndarray:
    """Expand a two-dimensional tile grid into a boolean LR pixel mask."""

    grid = np.asarray(tile_grid, dtype=bool)
    if grid.ndim != 2:
        raise ValueError("tile grid must have rank two")
    if tile_width <= 0 or tile_height <= 0:
        raise ValueError("tile dimensions must be positive")
    return np.repeat(np.repeat(grid, tile_height, axis=0), tile_width, axis=1)


# Count contiguous true runs independently in every row of a binary mask.
def count_row_spans(mask: np.ndarray) -> int:
    """Count row-wise active spans used to characterize mask fragmentation."""

    source = np.asarray(mask, dtype=bool)
    if source.ndim != 2:
        raise ValueError("span mask must have rank two")
    padded = np.pad(source, ((0, 0), (1, 0)), constant_values=False)
    return int(np.logical_and(padded[:, 1:], ~padded[:, :-1]).sum())


# Select exactly count cells using a deterministic center-out ordering.
def _clustered_grid(rows: int, columns: int, count: int) -> np.ndarray:
    """Create a compact tile cluster with a deterministic center preference."""

    coordinates = [(row, column) for row in range(rows) for column in range(columns)]
    center_row = (rows - 1) / 2.0
    center_column = (columns - 1) / 2.0
    coordinates.sort(
        key=lambda item: (
            max(abs(item[0] - center_row), abs(item[1] - center_column)),
            abs(item[0] - center_row) + abs(item[1] - center_column),
            item[0],
            item[1],
        )
    )
    grid = np.zeros((rows, columns), dtype=bool)
    for row, column in coordinates[:count]:
        grid[row, column] = True
    return grid


# Construct one exact-density grid for each controlled spatial shape.
def make_shape_grid(
    shape: str,
    *,
    rows: int,
    columns: int,
    count: int,
    rng: np.random.Generator,
) -> np.ndarray:
    """Create a deterministic clustered, striped, fragmented, or random mask."""

    if not 0 < count <= rows * columns:
        raise ValueError("selected tile count is outside the grid")
    grid = np.zeros((rows, columns), dtype=bool)
    if shape == "clustered":
        return _clustered_grid(rows, columns, count)
    if shape == "horizontal":
        order = [(row, column) for row in range(rows) for column in range(columns)]
    elif shape == "vertical":
        order = [(row, column) for column in range(columns) for row in range(rows)]
    elif shape == "checker":
        order = sorted(
            ((row, column) for row in range(rows) for column in range(columns)),
            key=lambda item: ((item[0] + item[1]) % 2, item[0], item[1]),
        )
    elif shape == "random":
        flat = rng.permutation(rows * columns)[:count]
        grid.flat[flat] = True
        return grid
    else:
        raise ValueError(f"unsupported mask shape: {shape}")
    for row, column in order[:count]:
        grid[row, column] = True
    return grid


# Summarize the exact dependency closure and compact AXI traffic for one mask.
def mask_metrics(
    tile_grid: np.ndarray,
    *,
    tile_width: int,
    tile_height: int,
    scale: int,
    layer_radii: Sequence[int],
    input_radius: int,
    bitmap_bytes: int = 8,
    row_span_descriptor_bytes: int = 4,
) -> dict[str, object]:
    """Calculate selected support, per-layer work, traffic, and fragmentation."""

    selected = tile_grid_to_pixel_mask(
        tile_grid,
        tile_width=tile_width,
        tile_height=tile_height,
    )
    layer_masks = [dilate_mask(selected, radius) for radius in layer_radii]
    input_mask = dilate_mask(selected, input_radius)
    selected_positions = int(selected.sum())
    output_words = selected_positions * scale * scale
    input_words = int(input_mask.sum())
    tile_row_spans = count_row_spans(tile_grid)
    return {
        "selected_tiles": int(np.asarray(tile_grid, dtype=bool).sum()),
        "selected_fraction": float(np.asarray(tile_grid, dtype=bool).mean()),
        "tile_row_spans": tile_row_spans,
        "bitmap_mask_bytes": bitmap_bytes,
        "row_span_mask_bytes": tile_row_spans * row_span_descriptor_bytes,
        "selected_lr_positions": selected_positions,
        "input_dependency_positions": input_words,
        "layer_active_positions": [int(mask.sum()) for mask in layer_masks],
        "total_active_layer_positions": int(sum(mask.sum() for mask in layer_masks)),
        "layer_row_spans": [count_row_spans(mask) for mask in layer_masks],
        "axis_words": input_words + output_words,
        "axis_bytes": 4 * (input_words + output_words),
    }


# Decode the tracked 60-bit row-major mask used by the canonical board run.
def decode_tile_mask(mask_hex: str, *, rows: int, columns: int) -> np.ndarray:
    """Return a boolean tile grid from a bounded hexadecimal mask."""

    value = int(mask_hex, 16)
    if value < 0 or value >> (rows * columns):
        raise ValueError("tile mask contains bits outside the configured grid")
    return np.asarray(
        [bool((value >> index) & 1) for index in range(rows * columns)],
        dtype=bool,
    ).reshape(rows, columns)


# Explain independent execution with exact halo geometry and secondary bounds.
def build_independent_tile_bounds(
    config: dict[str, object],
    reports: dict[str, dict[str, object]],
    cycle_model: dict[str, float],
) -> dict[str, object]:
    """Separate exact work duplication from the physical canonical comparison."""

    geometry = config["geometry"]
    manifest = reports["canonical_mask_manifest"]
    mask = decode_tile_mask(
        str(manifest["worklist"]["mask_hex"]),
        rows=int(geometry["tile_rows"]),
        columns=int(geometry["tile_columns"]),
    )
    per_tile_metrics = []
    for row, column in np.argwhere(mask):
        one_tile = np.zeros_like(mask)
        one_tile[row, column] = True
        per_tile_metrics.append(
            mask_metrics(
                one_tile,
                tile_width=int(geometry["tile_width"]),
                tile_height=int(geometry["tile_height"]),
                scale=int(geometry["scale"]),
                layer_radii=[int(value) for value in geometry["layer_radii"]],
                input_radius=int(geometry["input_radius"]),
            )
        )

    persistent = reports["hierarchical"]
    trained = reports["trained_tile"]
    independent_active = sum(
        int(metrics["total_active_layer_positions"]) for metrics in per_tile_metrics
    )
    persistent_active = int(persistent["architecture_delta"]["active_layer_positions"])
    serialized_cycles = len(per_tile_metrics) * int(trained["physical"]["neural_cycles"])
    serialized_axis_bytes = sum(int(metrics["axis_bytes"]) for metrics in per_tile_metrics)

    # This optimistic calibration charges one fixed traversal cost for all
    # independent tiles. Real independent launches charge setup repeatedly, so
    # the value is deliberately favorable to the baseline rather than to us.
    optimistic_cycles = int(
        round(
            cycle_model["fixed_cycles"]
            + cycle_model["cycles_per_active_position"] * independent_active
        )
    )
    proposed_cycles = int(persistent["physical_performance"]["average_fpga_cycles"])
    physical_independent = reports["balanced_pipeline"]["physical_organizations"][
        "frame"
    ]["independent"]
    return {
        "selected_tiles": len(per_tile_metrics),
        "mask_hex": str(manifest["worklist"]["mask_hex"]),
        "persistent_active_layer_positions": persistent_active,
        "independent_active_layer_positions": independent_active,
        "halo_duplication_percent": 100.0 * (independent_active / persistent_active - 1.0),
        "optimistic_one_traversal_cycles": optimistic_cycles,
        "physical_single_tile_serial_projection_cycles": serialized_cycles,
        "exact_independent_axis_bytes": serialized_axis_bytes,
        "physical_full_frame_cycles": int(physical_independent["average_compute_cycles"]),
        "physical_full_frame_axis_bytes": physical_axis_bytes(physical_independent),
        "physical_full_frame_capture_available": True,
        "proposed_cycles": proposed_cycles,
        "proposed_reduction_vs_optimistic_percent": 100.0
        * (1.0 - proposed_cycles / optimistic_cycles),
        "proposed_reduction_vs_serial_projection_percent": 100.0
        * (1.0 - proposed_cycles / serialized_cycles),
        "evidence_boundary": (
            "The canonical independent-tile comparison is a complete physical full-frame "
            "capture. Exact halo geometry and the two cycle estimates are retained only "
            "to explain duplicated work and to bracket implementation behavior; they are "
            "not substituted for the physical headline result."
        ),
    }


# Fit a measured cycle model using only the physical 16-pattern suite.
def fit_physical_cycle_model(suite: dict[str, object]) -> dict[str, float]:
    """Fit cycles as a function of physically counted active layer positions."""

    patterns = suite.get("patterns")
    if not isinstance(patterns, list) or len(patterns) < 2:
        raise ValueError("physical mask suite is missing patterns")
    active = np.asarray(
        [float(row["active_layer_positions"]) for row in patterns], dtype=np.float64
    )
    cycles = np.asarray(
        [float(row["average_fpga_cycles"]) for row in patterns], dtype=np.float64
    )
    slope, intercept = np.polyfit(active, cycles, 1)
    predicted = slope * active + intercept
    residual = float(np.sum((cycles - predicted) ** 2))
    total = float(np.sum((cycles - cycles.mean()) ** 2))
    return {
        "cycles_per_active_position": float(slope),
        "fixed_cycles": float(intercept),
        "r_squared": 1.0 - residual / total,
    }


# Generate spatial sensitivity rows without presenting them as board captures.
def build_shape_sweep(
    config: dict[str, object],
    cycle_model: dict[str, float],
) -> list[dict[str, object]]:
    """Evaluate controlled density and shape masks with a calibrated cycle model."""

    geometry = config["geometry"]
    sweep = config["sweep"]
    encoding = config["mask_encoding"]
    rng = np.random.default_rng(int(sweep["random_seed"]))
    rows: list[dict[str, object]] = []
    for count in sweep["selected_tile_counts"]:
        for shape in sweep["shapes"]:
            grid = make_shape_grid(
                str(shape),
                rows=int(geometry["tile_rows"]),
                columns=int(geometry["tile_columns"]),
                count=int(count),
                rng=rng,
            )
            metrics = mask_metrics(
                grid,
                tile_width=int(geometry["tile_width"]),
                tile_height=int(geometry["tile_height"]),
                scale=int(geometry["scale"]),
                layer_radii=[int(value) for value in geometry["layer_radii"]],
                input_radius=int(geometry["input_radius"]),
                bitmap_bytes=int(encoding["bitmap_bytes"]),
                row_span_descriptor_bytes=int(encoding["row_span_descriptor_bytes"]),
            )
            predicted_cycles = (
                cycle_model["fixed_cycles"]
                + cycle_model["cycles_per_active_position"]
                * float(metrics["total_active_layer_positions"])
            )
            rows.append(
                {
                    "shape": shape,
                    **metrics,
                    "predicted_cycles_from_physical_fit": int(round(predicted_cycles)),
                    "measurement_class": "calibrated_projection",
                }
            )
    return rows


# Move one compact cluster horizontally to expose temporal mask churn.
def build_motion_sweep(config: dict[str, object]) -> list[dict[str, object]]:
    """Create a deterministic moving-cluster sequence and record mask changes."""

    geometry = config["geometry"]
    sweep = config["sweep"]
    encoding = config["mask_encoding"]
    rows = int(geometry["tile_rows"])
    columns = int(geometry["tile_columns"])
    cluster_width = int(sweep["moving_cluster_width_tiles"])
    cluster_height = int(sweep["moving_cluster_height_tiles"])
    start_row = (rows - cluster_height) // 2
    previous = np.zeros((rows, columns), dtype=bool)
    result: list[dict[str, object]] = []
    for frame_id, start_column in enumerate(range(columns - cluster_width + 1)):
        grid = np.zeros((rows, columns), dtype=bool)
        grid[
            start_row : start_row + cluster_height,
            start_column : start_column + cluster_width,
        ] = True
        metrics = mask_metrics(
            grid,
            tile_width=int(geometry["tile_width"]),
            tile_height=int(geometry["tile_height"]),
            scale=int(geometry["scale"]),
            layer_radii=[int(value) for value in geometry["layer_radii"]],
            input_radius=int(geometry["input_radius"]),
            bitmap_bytes=int(encoding["bitmap_bytes"]),
            row_span_descriptor_bytes=int(encoding["row_span_descriptor_bytes"]),
        )
        result.append(
            {
                "frame_id": frame_id,
                "changed_tiles": int(np.logical_xor(grid, previous).sum()),
                **metrics,
            }
        )
        previous = grid
    return result


# Convert the ARM report's packet and RGB-byte counters into total AXI bytes.
def physical_axis_bytes(measurement: dict[str, object]) -> int:
    """Return MM2S plus S2MM traffic for one physical organization replay."""

    rgb_output_bytes = int(measurement["rgb_output_bytes"])
    if rgb_output_bytes % 3 != 0:
        raise ValueError("physical RGB output byte count is not pixel aligned")
    output_words = rgb_output_bytes // 3
    return int(measurement["packet_words"]) * 4 + output_words * 4


# Align all physically measured organizations for the canonical 17-tile mask.
def build_canonical_comparison(
    reports: dict[str, dict[str, object]],
) -> list[dict[str, object]]:
    """Build dense, tiled, region, and hierarchical rows with evidence labels."""

    hierarchical = reports["hierarchical"]
    suite = reports["hierarchical_suite"]
    balanced = reports["balanced_pipeline"]
    selected_tiles = int(hierarchical["physical_counters"]["conv3_active"]) // (64 * 60)
    dense_control = suite["control"]
    physical_frame = balanced["physical_organizations"]["frame"]
    independent = physical_frame["independent"]
    region = physical_frame["rectangle"]
    hierarchical_cycles = int(hierarchical["physical_performance"]["average_fpga_cycles"])
    hierarchical_bytes = int(
        hierarchical["architecture_delta"]["persistent_sparse_axis_bytes"]
    )
    expected_rgb_output_bytes = int(hierarchical["physical_counters"]["output_words"]) * 3
    if int(independent["rgb_output_bytes"]) != expected_rgb_output_bytes:
        raise ValueError("independent baseline does not cover the canonical output mask")
    if int(region["rgb_output_bytes"]) != expected_rgb_output_bytes:
        raise ValueError("rectangle baseline does not cover the canonical output mask")
    if int(independent["accepted_regions"]) != int(region["accepted_regions"]):
        raise ValueError("physical organizations did not accept the same work list")
    rows = [
        {
            "organization": "dense_same_bitstream",
            "cycles": int(dense_control["average_fpga_cycles"]),
            "axis_bytes": int(dense_control["axis_bytes"]),
            "evidence": "physical_same_bitstream_control",
            "bit_exact": bool(dense_control["exact"]),
        },
        {
            "organization": "independent_halo_tiles",
            "cycles": int(independent["average_compute_cycles"]),
            "axis_bytes": physical_axis_bytes(independent),
            "evidence": "physical_balanced_independent_job_engine",
            "bit_exact": bool(physical_frame["application_exact"]),
            "accepted_descriptors": int(independent["accepted_regions"]),
            "issued_jobs": int(independent["issued_regions"]),
            "selected_tile_equivalents": selected_tiles,
        },
        {
            "organization": "rectangle_compaction",
            "cycles": int(region["average_compute_cycles"]),
            "axis_bytes": physical_axis_bytes(region),
            "evidence": "physical_balanced_region_engine",
            "bit_exact": bool(physical_frame["application_exact"]),
            "accepted_descriptors": int(region["accepted_regions"]),
            "issued_jobs": int(region["issued_regions"]),
            "selected_tile_equivalents": selected_tiles,
        },
        {
            "organization": "persistent_hierarchical_mask",
            "cycles": hierarchical_cycles,
            "axis_bytes": hierarchical_bytes,
            "evidence": "physical_proposed_engine",
            "bit_exact": bool(hierarchical["correctness"]["bit_exact"]),
        },
    ]
    proposed = rows[-1]
    for row in rows:
        row["proposed_cycle_reduction_percent"] = 100.0 * (
            1.0 - proposed["cycles"] / row["cycles"]
        )
        row["proposed_axis_reduction_percent"] = 100.0 * (
            1.0 - proposed["axis_bytes"] / row["axis_bytes"]
        )
    return rows


# Characterize whether row-span descriptors justify replacing the tiny bitmap.
def summarize_mask_encoding(
    shape_sweep: list[dict[str, object]],
) -> dict[str, object]:
    """Summarize fixed-bitmap and variable row-span descriptor costs."""

    bitmap_bytes = int(shape_sweep[0]["bitmap_mask_bytes"])
    span_bytes = [int(row["row_span_mask_bytes"]) for row in shape_sweep]
    return {
        "bitmap_bytes": bitmap_bytes,
        "minimum_row_span_bytes": min(span_bytes),
        "median_row_span_bytes": float(np.median(span_bytes)),
        "maximum_row_span_bytes": max(span_bytes),
        "cases_row_span_no_larger_than_bitmap": sum(
            value <= bitmap_bytes for value in span_bytes
        ),
        "case_count": len(span_bytes),
        "decision": "retain_fixed_64bit_bitmap_and_bounded_local_decoder",
        "reason": (
            "The bitmap is always eight bytes; row spans save at most a few bytes "
            "for compact masks but grow with fragmentation and add descriptor control."
        ),
    }


# Separate the small decoder change from the broader commit/instrumentation cost.
def summarize_control_overhead(
    reports: dict[str, dict[str, object]],
    comparison: list[dict[str, object]],
) -> dict[str, object]:
    """Report isolated decoder deltas and a conservative wrapper upper bound."""

    lookup = reports["mask_lookup_route"]
    mask_only = lookup["candidate"]
    physical_route = reports["independent_worklists_physical"]["route"]
    proposed = next(
        row for row in comparison if row["organization"] == "persistent_hierarchical_mask"
    )
    bitmap_bytes = 8
    return {
        "bitmap_bytes_per_request": bitmap_bytes,
        "bitmap_percent_of_canonical_axis_bytes": 100.0
        * bitmap_bytes
        / int(proposed["axis_bytes"]),
        "isolated_bounded_decoder": {
            "logic_lut_delta": int(lookup["candidate_minus_baseline"]["logic_luts"]),
            "register_delta": int(lookup["candidate_minus_baseline"]["registers"]),
            "dsp_delta": 0,
            "bram_delta": 0.0,
            "evidence": "physical_routed_control_comparison",
        },
        "complete_commit_instrumentation_upper_bound": {
            "slice_lut_delta": int(physical_route["slice_luts"])
            - int(mask_only["slice_luts"]),
            "register_delta": int(physical_route["registers"])
            - int(mask_only["registers"]),
            "bram_tile_delta": float(physical_route["bram_tiles"])
            - float(mask_only["bram_tiles"]),
            "dsp_delta": int(physical_route["dsps"]) - int(mask_only["dsps"]),
            "evidence": "nonisolated_conservative_upper_bound",
        },
        "claim_boundary": (
            "The complete-route delta includes private commit storage, counters, and "
            "other integration changes; only the decoder delta is an isolated comparison."
        ),
    }


# Assemble the complete architecture result while preserving claim boundaries.
def analyze(config: dict[str, object]) -> dict[str, object]:
    """Build the canonical comparison, physical breadth, and sensitivity sweeps."""

    evidence = config["evidence"]
    reports = {name: _load_report(str(path)) for name, path in evidence.items()}
    suite = reports["hierarchical_suite"]
    hierarchical = reports["hierarchical"]
    mask_lookup_route = reports["mask_lookup_route"]
    independent = reports["independent_worklists"]
    multicontext = reports["multicontext_issue"]
    comparison = build_canonical_comparison(reports)
    cycle_model = fit_physical_cycle_model(suite)
    independent_tile_bounds = build_independent_tile_bounds(config, reports, cycle_model)
    shape_sweep = build_shape_sweep(config, cycle_model)
    motion_sweep = build_motion_sweep(config)
    mask_encoding = summarize_mask_encoding(shape_sweep)
    control_overhead = summarize_control_overhead(reports, comparison)
    acceptance = config["acceptance"]
    region_row = next(row for row in comparison if row["organization"] == "rectangle_compaction")
    exact = verify_hierarchical_exactness_suite(trials=96)
    gates = {
        "selected_output_exact": exact and all(row["bit_exact"] for row in comparison),
        "cycles_vs_region": (
            region_row["proposed_cycle_reduction_percent"]
            >= float(acceptance["minimum_cycles_vs_region_percent"])
        ),
        "axis_bytes_vs_region": (
            region_row["proposed_axis_reduction_percent"]
            >= float(acceptance["minimum_axis_bytes_vs_region_percent"])
        ),
        "physical_pattern_breadth": (
            int(suite["summary"]["pattern_count"])
            >= int(acceptance["minimum_physical_mask_patterns"])
        ),
        "physical_source_breadth": (
            int(suite["summary"]["engine_count_excluding_control"])
            >= int(acceptance["minimum_physical_sources"])
        ),
        "bounded_decoder_resource_and_timing": (
            bool(mask_lookup_route["gates"]["accepted"])
            and float(mask_lookup_route["candidate_reduction"]["logic_luts_percent"])
            >= float(acceptance["minimum_decoder_logic_lut_reduction_percent"])
        ),
        "independent_worklist_scaling": bool(independent["architecture_accepted"]),
        "independent_selector_generalization": bool(independent["selector_accepted"]),
        "realtime_720p": (
            float(hierarchical["physical_performance"]["service_fps"])
            >= float(acceptance["realtime_fps"])
        ),
    }
    # Selector generalization and real-time service are explicitly excluded from
    # the architecture gate. They remain visible failures rather than being
    # silently removed from the result package.
    mechanism_pass = all(
        value
        for key, value in gates.items()
        if key not in {"realtime_720p", "independent_selector_generalization"}
    )
    return {
        "schema_version": 1,
        "artifact": "sparse_accelerator_paper_v1",
        "experiment_id": config["experiment_id"],
        "decision": "retain_hierarchical_mask_dataflow_as_hardware_paper_candidate",
        "canonical_comparison": comparison,
        "physical_mask_breadth": suite["summary"],
        "physical_cycle_model": cycle_model,
        "independent_tile_bounds": independent_tile_bounds,
        "shape_density_sweep": shape_sweep,
        "moving_mask_sweep": motion_sweep,
        "mask_encoding": mask_encoding,
        "control_overhead": control_overhead,
        "mask_lookup_route": mask_lookup_route,
        "independent_worklists": independent,
        "optimization_ablation": multicontext,
        "gates": {**gates, "mechanism_pass": mechanism_pass},
        "claim_boundary": {
            "primary": (
                "Externally supplied output masks are propagated backward through "
                "the SR receptive field and executed persistently with exact selected residuals."
            ),
            "excluded": list(config["excluded_claims"]),
            "selector_generalization_claimed": False,
            "energy_claimed": False,
            "synthetic_sweeps_are_physical": False,
            "independent_worklists_are_architecture_only": True,
            "independent_tile_full_frame_is_physical": True,
            "rejected_optimizations_retained": True,
        },
    }


# Render the principal architecture comparison and gate outcomes for reviewers.
def render_markdown(result: dict[str, object]) -> str:
    """Render the paper evidence as a compact Markdown report."""

    comparison_rows = []
    for row in result["canonical_comparison"]:
        comparison_rows.append(
            f"| {row['organization']} | {row['cycles']:,} | {row['axis_bytes']:,} | "
            f"{row['proposed_cycle_reduction_percent']:.2f}% | "
            f"{row['proposed_axis_reduction_percent']:.2f}% | {row['evidence']} |"
        )
    gate_rows = [f"| {name} | `{value}` |" for name, value in result["gates"].items()]
    model = result["physical_cycle_model"]
    shape_rows = []
    for row in result["shape_density_sweep"]:
        shape_rows.append(
            f"| {row['selected_tiles']} | {row['shape']} | {row['tile_row_spans']} | "
            f"{row['total_active_layer_positions']:,} | {row['axis_bytes']:,} | "
            f"{row['predicted_cycles_from_physical_fit']:,} |"
        )
    motion = result["moving_mask_sweep"]
    encoding = result["mask_encoding"]
    control = result["control_overhead"]
    independent = result["independent_worklists"]
    independent_hardware = independent["hardware_summary"]
    independent_quality = independent["quality_summary"]
    ablation = result["optimization_ablation"]
    ablation_summary = ablation["summary"]
    return "\n".join(
        [
            "# Sparse SR Accelerator Paper Evidence",
            "",
            "## Canonical 17-Tile Workload",
            "",
            "| Organization | Cycles | AXI bytes | Proposed cycle delta | Proposed AXI delta | Evidence |",
            "|---|---:|---:|---:|---:|---|",
            *comparison_rows,
            "",
            "Negative deltas in the proposed columns mean the proposed engine is larger/slower for that comparison.",
            "All four canonical organization rows are physical Zybo measurements. "
            "The independent and rectangle rows replay the identical 17-tile mask "
            "through the same balanced engine, DMA path, and ARM timing method.",
            f"Exact halo geometry adds {result['independent_tile_bounds']['halo_duplication_percent']:.2f}% "
            "active positions. The proposed engine is "
            f"{result['independent_tile_bounds']['proposed_reduction_vs_optimistic_percent']:.2f}% "
            "below an optimistic one-traversal calibration and "
            f"{result['independent_tile_bounds']['proposed_reduction_vs_serial_projection_percent']:.2f}% "
            "below the serialized physical-tile projection.",
            "",
            "## Physical Breadth",
            "",
            f"The same bitstream passed {result['physical_mask_breadth']['pattern_count']} patterns "
            f"from {result['physical_mask_breadth']['engine_count_excluding_control']} sources. "
            f"Measured cycles track active layer positions with R^2={model['r_squared']:.5f}.",
            "",
            "## Independent Temporal Worklists",
            "",
            f"A separate one-shot capture used {independent_hardware['sparse_pattern_count']} "
            f"sparse masks from five unseen 300-frame Godot sequences. All physical "
            f"outputs and counters were exact. Cycle reductions ranged from "
            f"{independent_hardware['minimum_cycle_reduction_percent']:.2f}% to "
            f"{independent_hardware['maximum_cycle_reduction_percent']:.2f}% with a "
            f"{independent_hardware['median_cycle_reduction_percent']:.2f}% median; "
            f"AXI-byte reductions ranged from "
            f"{independent_hardware['minimum_axis_byte_reduction_percent']:.2f}% to "
            f"{independent_hardware['maximum_axis_byte_reduction_percent']:.2f}%.",
            "",
            f"This accepts architecture scaling, not selector generalization. The "
            f"frozen policy's worst scene lost "
            f"{independent_quality['maximum_scene_psnr_drop_db']:.4f} dB, exceeding "
            f"its {independent_quality['selector_quality_tolerance_db']:.2f}-dB limit.",
            "",
            "## Shape And Density Sensitivity",
            "",
            "These rows are calibrated projections from the physical 16-pattern cycle fit, not board captures.",
            "",
            "| Tiles | Shape | Row spans | Active layer positions | AXI bytes | Predicted cycles |",
            "|---:|---|---:|---:|---:|---:|",
            *shape_rows,
            "",
            "## Moving-Mask And Encoding Checks",
            "",
            f"A {len(motion)}-frame horizontal motion sweep changes "
            f"{np.mean([row['changed_tiles'] for row in motion]):.2f} tiles/frame on average. "
            "Dependency closures and transport are recomputed exactly for every position.",
            "",
            f"The fixed request bitmap costs {encoding['bitmap_bytes']} bytes. Across the "
            f"{encoding['case_count']} controlled masks, row-span descriptors range from "
            f"{encoding['minimum_row_span_bytes']} to {encoding['maximum_row_span_bytes']} bytes "
            f"with a {encoding['median_row_span_bytes']:.1f}-byte median. Only "
            f"{encoding['cases_row_span_no_larger_than_bitmap']} cases are no larger than the bitmap. "
            "The default therefore remains the fixed bitmap with bounded local decoding.",
            "",
            "## Controller And Mask Overhead",
            "",
            f"The eight-byte bitmap is {control['bitmap_percent_of_canonical_axis_bytes']:.5f}% "
            "of canonical AXI traffic. The isolated bounded decoder changes logic LUTs by "
            f"{control['isolated_bounded_decoder']['logic_lut_delta']} and registers by "
            f"+{control['isolated_bounded_decoder']['register_delta']}. The complete "
            "commit/instrumentation route is retained only as a non-isolated upper bound.",
            "",
            "## Gates",
            "",
            "| Gate | Pass |",
            "|---|---:|",
            *gate_rows,
            "",
            "The architecture mechanism passes, while the 720p 30-FPS application target remains failed. "
            "No deployable selector or physical-energy claim is made.",
            "",
            "## Rejected Throughput Ablation",
            "",
            f"The preregistered two-context grouped-issue engine is retained as "
            f"`{ablation['decision']}`. It preserved exactness and added no DSP/BRAM, "
            f"but changed dense cycles by "
            f"{ablation_summary['dense_cycle_reduction_percent']:.3f}% and median "
            f"sparse cycles by "
            f"{ablation_summary['median_sparse_cycle_reduction_percent']:.3f}%. "
            "It is therefore not part of the accepted architecture.",
            "",
        ]
    )


# Render a LaTeX table that can be included without copying values by hand.
def render_latex(result: dict[str, object]) -> str:
    """Render the canonical comparison as an IEEE-compatible LaTeX table."""

    labels = {
        "dense_same_bitstream": "Dense same-bitstream",
        "independent_halo_tiles": "Independent halo tiles",
        "rectangle_compaction": "Rectangle compaction",
        "persistent_hierarchical_mask": "Persistent hierarchy",
    }
    rows = []
    for row in result["canonical_comparison"]:
        rows.append(
            f"{labels[row['organization']]} & {row['cycles'] / 1e6:.3f} & "
            f"{row['axis_bytes'] / 1e6:.3f} & "
            f"{row['proposed_cycle_reduction_percent']:.2f}\\% & "
            f"{row['proposed_axis_reduction_percent']:.2f}\\% \\\\"
        )
    return "\n".join(
        [
            "% Generated by analyze_sparse_accelerator_paper.py.",
            "\\begin{table}[t]",
            "\\centering",
            "\\caption{Controlled sparse-accelerator organization comparison on the frozen 17-tile workload.}",
            "\\label{tab:sparse-accelerator-organizations}",
            "\\begin{tabular}{lrrrr}",
            "\\hline",
            "Organization & Mcycles & MB & Cycle $\\Delta$ & AXI $\\Delta$ \\\\ \\hline",
            *rows,
            "\\hline",
            "\\end{tabular}",
            "\\end{table}",
            "",
        ]
    )


# Define reproducible config and output paths for command-line automation.
def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse the paper comparison configuration and artifact destinations."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--output-markdown", type=Path, default=DEFAULT_MARKDOWN)
    parser.add_argument("--output-latex", type=Path, default=DEFAULT_LATEX)
    return parser.parse_args(argv)


# Execute the locked analysis and fail if the architecture mechanism regresses.
def main(argv: Sequence[str] | None = None) -> int:
    """Write JSON, Markdown, and LaTeX evidence from tracked physical reports."""

    args = parse_args(argv)
    config = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    if not isinstance(config, dict) or int(config.get("schema_version", -1)) != 1:
        raise ValueError("sparse accelerator paper config must be schema version 1")
    result = analyze(config)
    for path in (args.output_json, args.output_markdown, args.output_latex):
        path.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="ascii"
    )
    args.output_markdown.write_text(render_markdown(result), encoding="ascii")
    args.output_latex.write_text(render_latex(result), encoding="ascii")
    if not result["gates"]["mechanism_pass"]:
        raise RuntimeError("sparse accelerator paper mechanism gate failed")
    print(
        "SPARSE_ACCELERATOR_PAPER_PASS "
        f"patterns={result['physical_mask_breadth']['pattern_count']} "
        f"sources={result['physical_mask_breadth']['engine_count_excluding_control']} "
        f"realtime={int(result['gates']['realtime_720p'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
