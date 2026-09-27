"""Compare uniform and layer-balanced sparse-refinement Zybo captures.

The two bitstreams execute identical fixed and frozen-renderer work lists with
the same width-24 INT8 checkpoint.  This analyzer accepts the balanced design
only when checksums agree, timing closes, DSP use fits, and both selected and
full-grid service times improve by the preregistered amount.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

import yaml

from src.hardware.analyze_sparse_trained_tile_capture import (
    find_result_line,
    parse_resource,
    parse_wns_ns,
)


ROOT = Path(__file__).resolve().parents[2]
CAPTURE_ROOT = ROOT / "fpga" / "docs" / "captures" / "sparse_refinement_accelerator_v1"
DEFAULT_CONFIG = ROOT / "configs" / "sparse_refinement_balanced_pipeline_v1.yaml"
DEFAULT_UNIFORM_CAPTURE = CAPTURE_ROOT / "physical_zybo_variable_region.txt"
DEFAULT_BALANCED_CAPTURE = CAPTURE_ROOT / "physical_zybo_balanced_region.txt"
DEFAULT_BALANCED_MANIFEST = ROOT / "results" / "tables" / "sparse_refinement_balanced_region_board_ready.json"
DEFAULT_BALANCED_TIMING = CAPTURE_ROOT / "balanced_region_route" / "timing_summary.txt"
DEFAULT_BALANCED_UTILIZATION = CAPTURE_ROOT / "balanced_region_route" / "utilization.txt"
DEFAULT_JSON = ROOT / "results" / "tables" / "sparse_refinement_balanced_pipeline_physical.json"
DEFAULT_MARKDOWN = ROOT / "results" / "tables" / "sparse_refinement_balanced_pipeline_physical.md"
DEFAULT_LATEX = ROOT / "docs" / "paper" / "generated" / "sparse_refinement_balanced_pipeline_physical.tex"


# Extract one repeated schedule measurement and its exact workload counters.
def parse_scenario(
    capture_text: str,
    name: str,
    organization: str = "COMPACT",
) -> dict[str, float | int | str]:
    """Return one validated independent or rectangle-compacted measurement."""

    organization = organization.upper()
    if organization not in {"NAIVE", "COMPACT"}:
        raise ValueError("organization must be NAIVE or COMPACT")
    value = find_result_line(capture_text, f"SPARSE_{name}_{organization} ")
    distribution = find_result_line(
        capture_text, f"SPARSE_{name}_{organization}_DISTRIBUTION "
    )
    repetitions = int(distribution["repetitions"])
    if repetitions <= 0:
        raise ValueError(f"{name} capture has no repetitions")
    checksum = value.get("checksum", value.get("checksums"))
    if checksum is None:
        raise ValueError(f"{name} {organization} capture has no checksum")
    return {
        "organization": (
            "independent_jobs" if organization == "NAIVE" else "rectangle_compaction"
        ),
        "accepted_regions": int(value["accepted"]),
        "issued_regions": int(value["issued"]),
        "coalesced_regions": int(value["coalesced"]),
        "committed_regions": int(value["commits"]),
        "packet_words": int(value["packet_words"]),
        "lr_input_bytes": int(value["lr_input_bytes"]),
        "rgb_output_bytes": int(value["output_bytes"]),
        "halo_bytes_saved": int(value["halo_bytes_saved"]),
        "checksum": checksum.lower(),
        "repetitions": repetitions,
        "average_service_ms": float(distribution["average_ms"]),
        "p95_service_ms": float(distribution["p95_ms"]),
        "average_compute_cycles": int(distribution["average_compute_cycles"]),
    }


# Report positive savings and reject nonsensical zero or negative baselines.
def reduction_percent(baseline: float, candidate: float) -> float:
    """Return the percentage reduction from baseline to candidate."""

    if baseline <= 0.0 or candidate < 0.0:
        raise ValueError("physical timing values must be nonnegative")
    return 100.0 * (1.0 - candidate / baseline)


# Bind exactness, route evidence, and both preregistered service comparisons.
def analyze_captures(
    uniform_text: str,
    balanced_text: str,
    config: dict[str, object],
    balanced_manifest: dict[str, object],
    timing_text: str,
    utilization_text: str,
) -> dict[str, object]:
    """Return the publication-scoped balanced sparse-pipeline decision."""

    completion = find_result_line(
        balanced_text, "SPARSE_VARIABLE_BOARD_COMPLETE "
    )
    mailbox = find_result_line(balanced_text, "SPARSE_VARIABLE_MAILBOX ")
    application_exact = int(mailbox["result"]) == 0
    if completion.get("model") != config["model"]["id"]:
        raise ValueError("balanced board capture used the wrong model")
    if balanced_manifest.get("engine_variant") != "balanced":
        raise ValueError("board manifest is not the balanced engine")

    scenarios: dict[str, object] = {}
    physical_organizations: dict[str, object] = {}
    exact = True
    for name in ("VARIABLE", "FRAME", "FULL"):
        uniform = parse_scenario(uniform_text, name)
        balanced = parse_scenario(balanced_text, name)
        independent = parse_scenario(balanced_text, name, "NAIVE")
        checksum_match = uniform["checksum"] == balanced["checksum"]
        exact = exact and checksum_match
        scenarios[name.lower()] = {
            "uniform": uniform,
            "balanced": balanced,
            "checksum_match": checksum_match,
            "service_reduction_percent": reduction_percent(
                float(uniform["average_service_ms"]),
                float(balanced["average_service_ms"]),
            ),
            "p95_service_reduction_percent": reduction_percent(
                float(uniform["p95_service_ms"]),
                float(balanced["p95_service_ms"]),
            ),
            "compute_cycle_reduction_percent": reduction_percent(
                float(uniform["average_compute_cycles"]),
                float(balanced["average_compute_cycles"]),
            ),
        }
        # The independent and compact organizations use different output
        # checksum accumulation orders. Each constituent service is checked by
        # the ARM application, so result=0 plus its preserved counters is the
        # physical exactness criterion; the two aggregate checksums need not
        # be identical to each other.
        physical_organizations[name.lower()] = {
            "independent": independent,
            "rectangle": balanced,
            "independent_vs_rectangle": {
                "compute_cycle_reduction_percent": reduction_percent(
                    float(independent["average_compute_cycles"]),
                    float(balanced["average_compute_cycles"]),
                ),
                "service_reduction_percent": reduction_percent(
                    float(independent["average_service_ms"]),
                    float(balanced["average_service_ms"]),
                ),
                "lr_input_reduction_percent": reduction_percent(
                    float(independent["lr_input_bytes"]),
                    float(balanced["lr_input_bytes"]),
                ),
                "issued_job_reduction_percent": reduction_percent(
                    float(independent["issued_regions"]),
                    float(balanced["issued_regions"]),
                ),
            },
            "physical_full_workload": name in {"FRAME", "FULL"},
            "application_exact": application_exact,
        }

    physical_gate = config["physical_gate"]
    assert isinstance(physical_gate, dict)
    dsp = int(parse_resource(utilization_text, "DSPs"))
    timing_closed = "All user specified timing constraints are met" in timing_text
    selected = scenarios["frame"]
    full = scenarios["full"]
    assert isinstance(selected, dict) and isinstance(full, dict)
    passed = (
        exact
        and timing_closed
        and dsp <= int(physical_gate["maximum_dsp"])
        and float(selected["service_reduction_percent"])
        >= float(physical_gate["minimum_selected_worklist_service_reduction_percent"])
        and float(full["service_reduction_percent"])
        >= float(physical_gate["minimum_full_grid_service_reduction_percent"])
    )
    return {
        "schema_version": 1,
        "artifact": "sparse_refinement_balanced_pipeline_physical_v1",
        "decision": "accept_balanced_sparse_pipeline" if passed else "reject_balanced_sparse_pipeline",
        "model_id": config["model"]["id"],
        "layer_output_lanes": balanced_manifest["layer_output_lanes"],
        "scenarios": scenarios,
        "physical_organizations": physical_organizations,
        "implementation": {
            "fabric_clock_hz": int(completion["fabric_clock_hz"]),
            "timing_closed": timing_closed,
            "wns_ns": parse_wns_ns(timing_text),
            "slice_luts": int(parse_resource(utilization_text, "Slice LUTs")),
            "slice_registers": int(parse_resource(utilization_text, "Slice Registers")),
            "bram_tiles": parse_resource(utilization_text, "Block RAM Tile"),
            "dsp48e1": dsp,
        },
        "physical_gate": {"passed": passed, **physical_gate},
        "provenance": {
            "bitstream_sha256": balanced_manifest["bitstream_sha256"],
            "xsa_sha256": balanced_manifest["xsa_sha256"],
            "elf_sha256": balanced_manifest["elf_sha256"],
        },
        "evidence_boundary": (
            "The comparison uses fixed and frozen renderer work lists because "
            "the deployable selector did not generalize. It proves only the "
            "effect of physical execution organization and balanced layer "
            "throughput; it does not revive the rejected selector or establish "
            "energy savings. The FRAME and FULL NAIVE rows are complete physical "
            "independent-job replays, not single-tile projections."
        ),
    }


# Keep the readable report centered on the causal uniform-versus-balanced test.
def render_markdown(result: dict[str, object]) -> str:
    """Return a concise publication-facing physical comparison."""

    scenarios = result["scenarios"]
    implementation = result["implementation"]
    assert isinstance(scenarios, dict) and isinstance(implementation, dict)
    rows = []
    for key, label in (("variable", "One 256x60 region"), ("frame", "Frozen sparse work list"), ("full", "Full neural grid")):
        row = scenarios[key]
        assert isinstance(row, dict)
        old = row["uniform"]
        new = row["balanced"]
        assert isinstance(old, dict) and isinstance(new, dict)
        rows.append(
            f"| {label} | {old['average_service_ms']:.3f} | "
            f"{new['average_service_ms']:.3f} | {row['service_reduction_percent']:.2f}% | "
            f"{row['compute_cycle_reduction_percent']:.2f}% |"
        )
    return f"""# Physical Layer-Balanced Sparse Refinement

| Workload | Uniform 6/6/6 (ms) | Balanced 2/12/6 (ms) | Service reduction | Compute reduction |
|---|---:|---:|---:|---:|
{chr(10).join(rows)}

The balanced design uses {implementation['dsp48e1']}/220 DSP48s and
{implementation['slice_luts']:,} LUTs, with routed WNS of
{implementation['wns_ns']:+.3f} ns. Decision: `{result['decision']}`.

**Boundary:** {result['evidence_boundary']}
"""


# Emit a compact table that the IEEE source can include directly.
def render_latex(result: dict[str, object]) -> str:
    """Return the physical balance comparison as LaTeX."""

    scenarios = result["scenarios"]
    assert isinstance(scenarios, dict)
    rows = []
    for key, label in (("variable", "256x60 region"), ("frame", "Sparse list"), ("full", "Full grid")):
        row = scenarios[key]
        assert isinstance(row, dict)
        old = row["uniform"]
        new = row["balanced"]
        assert isinstance(old, dict) and isinstance(new, dict)
        rows.append(
            rf"{label} & {old['average_service_ms']:.3f} & {new['average_service_ms']:.3f} & {row['service_reduction_percent']:.2f}\% \\"
        )
    return """% Generated by analyze_sparse_balanced_physical.py.
\\begin{table}[t]
\\centering
\\caption{Physical layer-balanced sparse refinement on Zybo Z7-20.}
\\label{tab:sparse-balanced-physical}
\\begin{tabular}{lrrr}
\\hline
Workload & Uniform (ms) & Balanced (ms) & Reduction \\\\
\\hline
""" + "\n".join(rows) + """
\\hline
\\end{tabular}
\\end{table}
"""


# Expose every physical input so frozen captures remain independently replayable.
def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse physical capture, route, and output paths."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--uniform-capture", type=Path, default=DEFAULT_UNIFORM_CAPTURE)
    parser.add_argument("--balanced-capture", type=Path, default=DEFAULT_BALANCED_CAPTURE)
    parser.add_argument("--balanced-manifest", type=Path, default=DEFAULT_BALANCED_MANIFEST)
    parser.add_argument("--balanced-timing", type=Path, default=DEFAULT_BALANCED_TIMING)
    parser.add_argument("--balanced-utilization", type=Path, default=DEFAULT_BALANCED_UTILIZATION)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--output-markdown", type=Path, default=DEFAULT_MARKDOWN)
    parser.add_argument("--output-latex", type=Path, default=DEFAULT_LATEX)
    return parser.parse_args(argv)


# Publish the result only after all captured and routed evidence validates.
def main(argv: Sequence[str] | None = None) -> int:
    """Analyze physical evidence and write JSON, Markdown, and LaTeX together."""

    args = parse_args(argv)
    result = analyze_captures(
        args.uniform_capture.read_text(encoding="utf-8"),
        args.balanced_capture.read_text(encoding="utf-8"),
        yaml.safe_load(args.config.read_text(encoding="utf-8")),
        json.loads(args.balanced_manifest.read_text(encoding="utf-8")),
        args.balanced_timing.read_text(encoding="utf-8", errors="replace"),
        args.balanced_utilization.read_text(encoding="utf-8", errors="replace"),
    )
    for path in (args.output_json, args.output_markdown, args.output_latex):
        path.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="ascii")
    args.output_markdown.write_text(render_markdown(result), encoding="ascii")
    args.output_latex.write_text(render_latex(result), encoding="ascii")
    print(f"SPARSE_BALANCED_PHYSICAL_ANALYSIS_{'PASS' if result['physical_gate']['passed'] else 'FAIL'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
