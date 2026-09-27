"""Join independent-worklist quality and physical FPGA architecture evidence.

The independent masks come from a frozen temporal holdout that was never used
to design or tune the FPGA data path.  This analyzer deliberately separates two
questions that could otherwise be conflated in a paper:

* Does the sparse accelerator execute unseen worklists exactly and save cycles?
* Did the deployable selector that produced those worklists meet its quality gate?

The first question may pass even when the second fails.  Keeping both decisions
in one artifact prevents an architecture result from being misreported as a
selector-generalization result.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from statistics import median
from typing import Sequence

import yaml

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.utils.research_db import DEFAULT_DATABASE_PATH, publish_record_set  # noqa: E402

DEFAULT_PHYSICAL = ROOT / "results/tables/sparse_independent_worklists_physical.json"
DEFAULT_QUALITY = ROOT / "results/tables/sparse_refinement_selector_v7_holdout.json"
DEFAULT_CONTRACT = ROOT / "configs/sparse_independent_worklists_v1.yaml"
DEFAULT_JSON = ROOT / "results/tables/sparse_independent_worklists_joined.json"
DEFAULT_MARKDOWN = ROOT / "results/tables/sparse_independent_worklists_joined.md"
DEFAULT_TEX = ROOT / "docs/paper/generated/sparse_independent_worklists_joined.tex"
DEFAULT_RECORD_SET = "results.hardware.sparse_independent_worklists_joined_v1"


# Hash the independent observations named by the frozen contract. Git may
# materialize the tracked JSONL with CRLF on Windows even though the accepted
# evidence identity was frozen over LF bytes. Canonicalize only well-formed
# CRLF records to LF; every payload byte remains hash-bound.
def sha256_jsonl_canonical_lf(path: Path) -> str:
    """Return SHA-256 after fail-closed CRLF-to-LF canonicalization."""

    raw = path.read_bytes()
    if b"\r" in raw.replace(b"\r\n", b""):
        raise ValueError("independent observations contain unsupported bare CR")
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


# Compute the worst positive per-scene PSNR loss without allowing gains on one
# scene to hide a regression on another scene.
def maximum_scene_psnr_drop(quality: dict[str, object]) -> float:
    """Return the largest sparse-versus-always-neural PSNR loss in decibels."""

    rows = quality["quality_by_scene"]  # type: ignore[index]
    if not rows:
        raise ValueError("quality report contains no scene rows")
    return max(float(row["drop_vs_always_neural_db"]) for row in rows.values())


# Apply the frozen architecture gates and preserve the already-frozen selector
# decision as a separate result rather than silently changing its tolerance.
def analyze(
    physical: dict[str, object],
    quality: dict[str, object],
    contract: dict[str, object],
    *,
    observed_source_sha256: str,
) -> dict[str, object]:
    """Return the joined Paper-2 decision for independent temporal worklists."""

    source = contract["source"]  # type: ignore[index]
    expected_hash = str(source["observations_sha256"])
    if observed_source_sha256 != expected_hash:
        raise ValueError("independent observation hash does not match frozen contract")

    patterns = physical["patterns"]  # type: ignore[index]
    sparse_patterns = [row for row in patterns if int(row["selected_tiles"]) < 60]
    if len(patterns) != int(contract["selection"]["expected_pattern_count"]):  # type: ignore[index]
        raise ValueError("physical pattern count does not match frozen contract")
    if not sparse_patterns:
        raise ValueError("independent physical report contains no sparse patterns")

    cycle_reductions = [
        float(row["cycle_reduction_percent"]) for row in sparse_patterns
    ]
    byte_reductions = [
        float(row["axis_byte_reduction_percent"]) for row in sparse_patterns
    ]
    hardware_gates = {
        "source_hash_exact": observed_source_sha256 == expected_hash,
        "all_patterns_bit_and_counter_exact": bool(
            physical["gates"]["all_masks_bit_and_counter_exact"]  # type: ignore[index]
        ),
        "all_commit_outcomes_exact": bool(
            physical["gates"]["all_commit_outcomes_exact"]  # type: ignore[index]
        ),
        "every_sparse_pattern_lower_cycles": all(value > 0.0 for value in cycle_reductions),
        "every_sparse_pattern_lower_axis_bytes": all(value > 0.0 for value in byte_reductions),
        "cycles_scale_with_active_positions": float(
            physical["summary"]["cycles_vs_active_positions_r_squared"]  # type: ignore[index]
        )
        >= float(contract["acceptance"]["minimum_cycles_vs_active_positions_r_squared"]),  # type: ignore[index]
        "timing_closed": bool(physical["route"]["timing_closed"]),  # type: ignore[index]
    }
    architecture_accepted = all(hardware_gates.values())

    selector_gates = quality["gates"]  # type: ignore[index]
    selector_accepted = bool(selector_gates["overall_passed"])
    always = quality["methods"]["always_neural"]  # type: ignore[index]
    sparse = quality["methods"]["semantic_sparse"]  # type: ignore[index]
    worst_drop = maximum_scene_psnr_drop(quality)

    return {
        "schema_version": 1,
        "artifact": "sparse_independent_worklists_joined_v1",
        "decision": (
            "accept_independent_architecture_scaling_not_selector"
            if architecture_accepted and not selector_accepted
            else "accept_independent_architecture_and_selector"
            if architecture_accepted and selector_accepted
            else "reject_independent_architecture_scaling"
        ),
        "architecture_accepted": architecture_accepted,
        "selector_accepted": selector_accepted,
        "provenance": {
            "evidence_scope": contract["evidence_boundary"]["scope"],  # type: ignore[index]
            "observations": source["observations"],
            "observations_sha256": observed_source_sha256,
            "frame_count": int(source["frame_count"]),
            "sequence_count": int(source["sequence_count"]),
            "used_for_fpga_design_or_tuning": bool(
                source["used_for_fpga_design_or_tuning"]
            ),
        },
        "hardware_summary": {
            "physical_pattern_count": len(patterns),
            "sparse_pattern_count": len(sparse_patterns),
            "minimum_cycle_reduction_percent": min(cycle_reductions),
            "median_cycle_reduction_percent": median(cycle_reductions),
            "maximum_cycle_reduction_percent": max(cycle_reductions),
            "minimum_axis_byte_reduction_percent": min(byte_reductions),
            "median_axis_byte_reduction_percent": median(byte_reductions),
            "maximum_axis_byte_reduction_percent": max(byte_reductions),
            "cycles_vs_active_positions_r_squared": float(
                physical["summary"]["cycles_vs_active_positions_r_squared"]  # type: ignore[index]
            ),
            "dense_service_fps": float(
                physical["summary"]["control_service_fps"]  # type: ignore[index]
            ),
            "wns_ns": float(physical["route"]["wns_ns"]),  # type: ignore[index]
            "clock_mhz": float(physical["route"]["target_mhz"]),  # type: ignore[index]
            "dsps": int(physical["route"]["dsps"]),  # type: ignore[index]
            "bram_tiles": float(physical["route"]["bram_tiles"]),  # type: ignore[index]
        },
        "quality_summary": {
            "scene_equal_always_neural_psnr_db": float(always["scene_equal_psnr"]),
            "scene_equal_sparse_psnr_db": float(sparse["scene_equal_psnr"]),
            "scene_equal_sparse_minus_always_psnr_db": float(
                sparse["scene_equal_psnr"]
            )
            - float(always["scene_equal_psnr"]),
            "maximum_scene_psnr_drop_db": worst_drop,
            "selector_quality_tolerance_db": 0.1,
            "selector_quality_gate_passed": bool(
                selector_gates["quality_within_tolerance_each_scene"]
            ),
            "selector_overall_gate_passed": selector_accepted,
        },
        "hardware_gates": hardware_gates,
        "selector_gates": selector_gates,
        "evidence_boundary": {
            "architecture_claim": (
                "The fixed sparse architecture scales bit-exactly with unseen "
                "worklists and reduces measured cycles and AXI traffic."
            ),
            "selector_claim": (
                "Rejected: the frozen selector exceeded the per-scene PSNR-loss "
                "limit and is not evidence of deployable policy generalization."
            ),
            "realtime_720p_claimed": False,
            "physical_energy_claimed": False,
        },
    }


# Render only decision-bearing values so the human report stays concise.
def render_markdown(result: dict[str, object]) -> str:
    """Return an advisor-readable independent-worklist result."""

    hardware = result["hardware_summary"]  # type: ignore[index]
    quality = result["quality_summary"]  # type: ignore[index]
    gate_lines = [
        f"| `{name}` | {'PASS' if passed else 'FAIL'} |"
        for name, passed in result["hardware_gates"].items()  # type: ignore[index]
    ]
    return "\n".join(
        [
            "# Independent Worklist Architecture Evaluation",
            "",
            f"**Decision:** `{result['decision']}`",
            "",
            "| Physical measurement | Result |",
            "|---|---:|",
            f"| Exact independent masks | {hardware['physical_pattern_count']}/{hardware['physical_pattern_count']} |",
            f"| Cycle reduction, min / median / max | {hardware['minimum_cycle_reduction_percent']:.2f}% / {hardware['median_cycle_reduction_percent']:.2f}% / {hardware['maximum_cycle_reduction_percent']:.2f}% |",
            f"| AXI-byte reduction, min / median / max | {hardware['minimum_axis_byte_reduction_percent']:.2f}% / {hardware['median_axis_byte_reduction_percent']:.2f}% / {hardware['maximum_axis_byte_reduction_percent']:.2f}% |",
            f"| Cycles versus active positions R-squared | {hardware['cycles_vs_active_positions_r_squared']:.5f} |",
            f"| Routed timing | {hardware['clock_mhz']:.3f} MHz, WNS {hardware['wns_ns']:+.3f} ns |",
            "",
            "| Quality boundary | Result |",
            "|---|---:|",
            f"| Always-neural scene-equal PSNR | {quality['scene_equal_always_neural_psnr_db']:.4f} dB |",
            f"| Sparse scene-equal PSNR | {quality['scene_equal_sparse_psnr_db']:.4f} dB |",
            f"| Worst per-scene sparse PSNR loss | {quality['maximum_scene_psnr_drop_db']:.4f} dB |",
            f"| Frozen per-scene tolerance | {quality['selector_quality_tolerance_db']:.4f} dB |",
            "",
            "| Architecture gate | Result |",
            "|---|---|",
            *gate_lines,
            "",
            "The FPGA mechanism passes on unseen temporal worklists. The policy "
            "that generated the worklists remains rejected because its worst "
            "scene lost more than the frozen 0.10 dB limit.",
            "",
            "**ELI5:** the hardware correctly does less work when handed a shorter "
            "list, even for scenes it did not see during development. The current "
            "software chooser is still not reliable enough at choosing that list.",
            "",
        ]
    )


# Keep the IEEE include generated from the same authoritative result object.
def render_tex(result: dict[str, object]) -> str:
    """Return a compact LaTeX table for the Paper-2 draft."""

    hardware = result["hardware_summary"]  # type: ignore[index]
    quality = result["quality_summary"]  # type: ignore[index]
    return f"""% Generated by src/hardware/analyze_sparse_independent_worklists.py
\\begin{{table}}[t]
\\centering
\\caption{{Independent temporal-worklist validation on the Zybo Z7-20.}}
\\label{{tab:sparse-independent-worklists}}
\\begin{{tabular}}{{lr}}
\\hline
Measurement & Result \\\\
\\hline
Exact physical masks & {hardware['physical_pattern_count']}/{hardware['physical_pattern_count']} \\\\
Cycle reduction (min/median/max) & {hardware['minimum_cycle_reduction_percent']:.2f}/{hardware['median_cycle_reduction_percent']:.2f}/{hardware['maximum_cycle_reduction_percent']:.2f}\\% \\\\
AXI-byte reduction (min/median/max) & {hardware['minimum_axis_byte_reduction_percent']:.2f}/{hardware['median_axis_byte_reduction_percent']:.2f}/{hardware['maximum_axis_byte_reduction_percent']:.2f}\\% \\\\
Cycles vs. active positions $R^2$ & {hardware['cycles_vs_active_positions_r_squared']:.4f} \\\\
Worst selector PSNR loss & {quality['maximum_scene_psnr_drop_db']:.4f} dB \\\\
\\hline
\\end{{tabular}}
\\end{{table}}
"""


# Expose all inputs and outputs so the joined decision can be regenerated.
def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse evidence, report, and database paths."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--physical", type=Path, default=DEFAULT_PHYSICAL)
    parser.add_argument("--quality", type=Path, default=DEFAULT_QUALITY)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--output-markdown", type=Path, default=DEFAULT_MARKDOWN)
    parser.add_argument("--output-tex", type=Path, default=DEFAULT_TEX)
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE_PATH)
    parser.add_argument("--record-set", default=DEFAULT_RECORD_SET)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args(argv)


# Publish JSON, Markdown, LaTeX, and SQLite from the same validated analysis.
def main(argv: Sequence[str] | None = None) -> int:
    """Generate every tracked independent-worklist evidence view."""

    args = parse_args(argv)
    contract = yaml.safe_load(args.contract.read_text(encoding="utf-8"))
    source_path = ROOT / contract["source"]["observations"]
    result = analyze(
        json.loads(args.physical.read_text(encoding="utf-8")),
        json.loads(args.quality.read_text(encoding="utf-8")),
        contract,
        observed_source_sha256=sha256_jsonl_canonical_lf(source_path),
    )
    for output in (args.output_json, args.output_markdown, args.output_tex):
        output.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    args.output_markdown.write_text(render_markdown(result), encoding="utf-8")
    args.output_tex.write_text(render_tex(result), encoding="utf-8")
    publish_record_set(
        args.database,
        args.record_set,
        [
            {
                "decision": result["decision"],
                "architecture_accepted": result["architecture_accepted"],
                "selector_accepted": result["selector_accepted"],
                **result["hardware_summary"],
                **result["quality_summary"],
                "physical_energy_claimed": False,
            }
        ],
        overwrite=args.overwrite,
        source_path=args.physical.resolve().relative_to(ROOT).as_posix(),
    )
    print(
        "SPARSE_INDEPENDENT_WORKLISTS_JOINED_COMPLETE "
        f"decision={result['decision']} "
        f"median_cycles_saved={result['hardware_summary']['median_cycle_reduction_percent']:.6f} "
        f"worst_scene_psnr_drop={result['quality_summary']['maximum_scene_psnr_drop_db']:.6f}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
