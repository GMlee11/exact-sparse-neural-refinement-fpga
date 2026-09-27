"""Create provisional workload-aware estimates from a routed Vivado report.

This intentionally does not turn Vivado's vectorless estimate into a physical
power claim. The script records the report hash and confidence limitations,
then scales only the accelerator hierarchy by each physically measured sparse
workload's active-cycle duty. Board input power and joules/frame remain pending.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Sequence


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_WORKLOADS = ROOT / "results/tables/sparse_independent_worklists_physical.json"
DEFAULT_VIVADO_REPORT = (
    ROOT / "results/hardware/sparse_dma_wrapper_power_routed_58mhz.rpt"
)
DEFAULT_CONTROLLER_SAIF = ROOT / "results/hardware/sparse_commit_controller_activity.saif"
DEFAULT_JSON = ROOT / "results/tables/sparse_postroute_power_estimate.json"
DEFAULT_MARKDOWN = ROOT / "results/tables/sparse_postroute_power_estimate.md"
DEFAULT_LATEX = ROOT / "docs/paper/generated/sparse_postroute_power_estimate.tex"


# Extract one unambiguous numeric field from the human-readable Vivado report.
def _match_float(source: str, pattern: str, field: str) -> float:
    """Return a required floating-point report field."""

    match = re.search(pattern, source, flags=re.MULTILINE)
    if match is None:
        raise ValueError(f"Vivado power report is missing {field}")
    return float(match.group(1))


# Parse only fields used by the estimate and preserve the report provenance.
def parse_vivado_power_report(path: Path) -> dict[str, object]:
    """Read routed power totals, confidence, and accelerator hierarchy power."""

    source = path.read_text(encoding="utf-8", errors="replace")
    return {
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "tool_version": re.search(r"Tool Version\s+:\s+([^\r\n]+)", source).group(1).strip(),
        "design_state": re.search(r"Design State\s+:\s+([^\r\n]+)", source).group(1).strip(),
        "total_onchip_w": _match_float(
            source, r"\| Total On-Chip Power \(W\)\s+\|\s+([0-9.]+)", "total power"
        ),
        "dynamic_w": _match_float(source, r"\| Dynamic \(W\)\s+\|\s+([0-9.]+)", "dynamic power"),
        "static_w": _match_float(
            source, r"\| Device Static \(W\)\s+\|\s+([0-9.]+)", "static power"
        ),
        "accelerator_hierarchy_w": _match_float(
            source, r"\|\s+e\s+\|\s+([0-9.]+)\s+\|", "accelerator hierarchy power"
        ),
        "confidence": re.search(r"\| Overall confidence level\s+\|\s+([^|]+)", source)
        .group(1)
        .strip(),
        "simulation_activity_file": "none",
    }


# Preserve representative controller switching without overstating its coverage.
def parse_controller_saif(path: Path) -> dict[str, object]:
    """Return provenance and basic coverage facts for the commit-controller SAIF."""

    source = path.read_text(encoding="utf-8", errors="replace")
    duration = re.search(r"\(DURATION\s+([0-9]+)\)", source)
    timescale = re.search(r"\(TIMESCALE\s+([^\)]+)\)", source)
    toggles = [int(value) for value in re.findall(r"\(TC\s+([0-9]+)\)", source)]
    if duration is None or timescale is None or not toggles:
        raise ValueError(f"controller SAIF is malformed: {path}")
    return {
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "duration": int(duration.group(1)),
        "timescale": timescale.group(1).strip(),
        "annotated_signal_count": len(toggles),
        "total_toggle_count": sum(toggles),
        "scope": "sparse_hierarchical_commit_controller_only",
        "full_routed_datapath_annotated": False,
    }


# Apply physical workload duty only to the accelerator hierarchy contribution.
def analyze(
    power: dict[str, object],
    workloads: dict[str, object],
    controller_activity: dict[str, object] | None = None,
) -> dict[str, object]:
    """Generate conservative design estimates for dense and sparse worklists."""

    patterns = workloads["patterns"]
    dense = next(row for row in patterns if int(row["selected_tiles"]) == 60)
    dense_cycles = int(dense["average_fpga_cycles"])
    accelerator_w = float(power["accelerator_hierarchy_w"])
    fixed_w = float(power["total_onchip_w"]) - accelerator_w
    rows = []
    for row in patterns:
        cycles = int(row["average_fpga_cycles"])
        duty = min(1.0, cycles / dense_cycles)
        estimate_w = fixed_w + accelerator_w * duty
        service_s = float(row["average_service_ms"]) / 1000.0
        rows.append(
            {
                "pattern_id": int(row["pattern_id"]),
                "label": str(row["label"]),
                "selected_tiles": int(row["selected_tiles"]),
                "accelerator_cycle_duty": duty,
                "estimated_onchip_w": estimate_w,
                "estimated_onchip_j_per_service": estimate_w * service_s,
                "measurement_class": "provisional_postroute_duty_estimate",
            }
        )
    return {
        "schema_version": 1,
        "artifact": "sparse_postroute_power_estimate_v1",
        "decision": "report_as_provisional_design_estimate_only",
        "vivado_report": power,
        "activity_model": {
            "fixed_onchip_w": fixed_w,
            "scalable_accelerator_hierarchy_w": accelerator_w,
            "duty_source": "physical_58p824mhz_service_cycles_relative_to_dense",
            "internal_net_activity_coverage": "less_than_25_percent_in_source_report",
            "representative_controller_saif": controller_activity,
        },
        "workloads": rows,
        "claim_boundary": {
            "physical_wall_power_claimed": False,
            "physical_energy_claimed": False,
            "board_regulators_and_external_memory_included": False,
            "simulation_activity_file_used": False,
            "representative_controller_saif_generated": controller_activity is not None,
            "full_routed_datapath_saif_annotated": False,
            "journal_measurement_deferred": True,
        },
    }


# Explain the estimate in language that prevents accidental physical claims.
def render_markdown(result: dict[str, object]) -> str:
    """Render selected design-estimate rows and explicit exclusions."""

    rows = [
        f"| {row['label']} | {row['selected_tiles']} | "
        f"{row['accelerator_cycle_duty']:.4f} | {row['estimated_onchip_w']:.3f} | "
        f"{row['estimated_onchip_j_per_service']:.4f} |"
        for row in result["workloads"]
    ]
    return "\n".join(
        [
            "# Sparse Accelerator Post-Route Power Estimate",
            "",
            "| Workload | Tiles | Cycle duty | Est. on-chip W | Est. J/service |",
            "|---|---:|---:|---:|---:|",
            *rows,
            "",
            "These are medium-confidence routed-design estimates. A representative SAIF "
            "covers the commit controller, but the routed neural datapath report used no "
            "simulation activity file and covered less than 25% of internal-node activity. "
            "They exclude board regulators and are not wall-power or physical energy results.",
            "",
        ]
    )


# Render only estimate provenance for the paper; do not imply measured energy.
def render_latex(result: dict[str, object]) -> str:
    """Render a short estimate disclaimer and dense/sparse range."""

    values = [float(row["estimated_onchip_w"]) for row in result["workloads"]]
    report = result["vivado_report"]
    return "\n".join(
        [
            "% Generated by analyze_sparse_postroute_power.py.",
            "\\noindent\\textbf{Post-route estimate only:} "
            f"Vivado reports {report['total_onchip_w']:.3f} W for the routed dense design "
            f"at {report['confidence']} confidence. A cycle-duty sensitivity model spans "
            f"{min(values):.3f}--{max(values):.3f} W across measured worklists. "
            "A representative controller SAIF was generated, but the full routed datapath "
            "was not activity-annotated. Board regulators and external-memory power are not "
            "included; therefore no physical power or energy claim is made.",
            "",
        ]
    )


# Require the routed report explicitly because generated project names vary.
def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse the Vivado report, physical workloads, and output destinations."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vivado-report", type=Path, default=DEFAULT_VIVADO_REPORT)
    parser.add_argument("--controller-saif", type=Path, default=DEFAULT_CONTROLLER_SAIF)
    parser.add_argument("--workloads", type=Path, default=DEFAULT_WORKLOADS)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--output-markdown", type=Path, default=DEFAULT_MARKDOWN)
    parser.add_argument("--output-latex", type=Path, default=DEFAULT_LATEX)
    return parser.parse_args(argv)


# Write the provisional estimate while retaining hard false claim flags.
def main(argv: Sequence[str] | None = None) -> int:
    """Generate JSON, Markdown, and LaTeX from routed and physical evidence."""

    args = parse_args(argv)
    power = parse_vivado_power_report(args.vivado_report)
    controller_activity = parse_controller_saif(args.controller_saif)
    workloads = json.loads(args.workloads.read_text(encoding="utf-8"))
    result = analyze(power, workloads, controller_activity)
    for path in (args.output_json, args.output_markdown, args.output_latex):
        path.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(result, indent=2) + "\n", encoding="ascii")
    args.output_markdown.write_text(render_markdown(result), encoding="ascii")
    args.output_latex.write_text(render_latex(result), encoding="ascii")
    print("SPARSE_POSTROUTE_POWER_ESTIMATE_PASS physical_energy_claimed=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
