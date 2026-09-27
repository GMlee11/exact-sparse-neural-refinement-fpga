"""Report the measured and calibrated real-time envelope of the Zybo design.

Physical 720p sparse masks define the observed deadline boundary. A linear
cycle model, fitted only to board captures, estimates the lower-resolution
320x180-to-640x360 dense case and explicitly labels it as a projection.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Sequence


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PAPER = ROOT / "results/tables/sparse_accelerator_paper_v1.json"
DEFAULT_PHYSICAL = ROOT / "results/tables/sparse_independent_worklists_physical.json"
DEFAULT_JSON = ROOT / "results/tables/sparse_realtime_envelope_v1.json"
DEFAULT_MARKDOWN = ROOT / "results/tables/sparse_realtime_envelope_v1.md"
DEFAULT_LATEX = ROOT / "docs/paper/generated/sparse_realtime_envelope_v1.tex"


# Load one tracked analysis artifact as a JSON object.
def load_report(path: Path) -> dict[str, object]:
    """Return one validated evidence report."""

    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"report is not a JSON object: {path}")
    return payload


# Convert a frame-rate requirement into one service deadline.
def deadline_ms(fps: float) -> float:
    """Return the maximum milliseconds per frame for a positive FPS target."""

    if fps <= 0.0:
        raise ValueError("FPS must be positive")
    return 1000.0 / fps


# Predict cycles from the physical active-position regression.
def predicted_cycles(model: dict[str, object], active_positions: int) -> int:
    """Return calibrated cycles for a nonnegative active-position count."""

    if active_positions < 0:
        raise ValueError("active positions must be nonnegative")
    return int(
        round(
            float(model["fixed_cycles"])
            + float(model["cycles_per_active_position"]) * active_positions
        )
    )


# Assemble observed deadline passes and the lower-resolution scaling projection.
def analyze(paper: dict[str, object], physical: dict[str, object]) -> dict[str, object]:
    """Return physical 720p and calibrated 360p real-time boundaries."""

    route = physical["route"]
    clock_hz = float(route["target_mhz"]) * 1_000_000.0
    patterns = physical["patterns"]
    sparse = [row for row in patterns if int(row["selected_tiles"]) < 60]
    observed: dict[str, object] = {}
    for target_fps in (30.0, 60.0):
        limit = deadline_ms(target_fps)
        passing = [row for row in sparse if float(row["average_service_ms"]) <= limit]
        observed[str(int(target_fps))] = {
            "deadline_ms": limit,
            "passing_sparse_patterns": len(passing),
            "tested_sparse_patterns": len(sparse),
            "maximum_observed_selected_tiles": max(
                (int(row["selected_tiles"]) for row in passing), default=0
            ),
            "maximum_observed_selected_fraction": max(
                (float(row["selected_fraction"]) for row in passing), default=0.0
            ),
            "measurement_class": "physical_zybo",
        }

    cycle_model = paper["physical_cycle_model"]
    lower_lr_width = 320
    lower_lr_height = 180
    dense_active_positions = lower_lr_width * lower_lr_height * 3
    lower_cycles = predicted_cycles(cycle_model, dense_active_positions)
    lower_ms = 1000.0 * lower_cycles / clock_hz
    lower_fps = 1000.0 / lower_ms

    calibrated_deadlines: dict[str, object] = {}
    for target_fps in (30.0, 60.0):
        cycle_budget = clock_hz / target_fps
        remaining = cycle_budget - float(cycle_model["fixed_cycles"])
        maximum_active = max(
            0,
            math.floor(remaining / float(cycle_model["cycles_per_active_position"])),
        )
        calibrated_deadlines[str(int(target_fps))] = {
            "cycle_budget": int(math.floor(cycle_budget)),
            "maximum_modeled_active_layer_positions": maximum_active,
            "fraction_of_lower_dense_active_positions": maximum_active
            / dense_active_positions,
            "measurement_class": "projection_from_physical_cycle_fit",
        }

    return {
        "schema_version": 1,
        "artifact": "sparse_realtime_envelope_v1",
        "decision": "report_architecture_efficiency_without_realtime_720p_claim",
        "route": {
            "clock_mhz": float(route["target_mhz"]),
            "timing_closed": bool(route["timing_closed"]),
        },
        "physical_640x360_to_1280x720": {
            "dense_service_ms": float(physical["control"]["average_service_ms"]),
            "dense_fps": 1000.0 / float(physical["control"]["average_service_ms"]),
            "deadline_results": observed,
        },
        "calibrated_320x180_to_640x360": {
            "dense_active_layer_positions": dense_active_positions,
            "predicted_dense_cycles": lower_cycles,
            "predicted_dense_service_ms": lower_ms,
            "predicted_dense_fps": lower_fps,
            "deadline_results": calibrated_deadlines,
            "measurement_class": "projection_from_physical_cycle_fit",
            "cycle_model_r_squared": float(cycle_model["r_squared"]),
        },
        "claim_boundary": {
            "physical_720p_realtime_claimed": False,
            "physical_lower_resolution_realtime_claimed": False,
            "calibrated_projection_clearly_labeled": True,
            "interpretation": (
                "The current Zynq-7020 implementation scales with requested work but "
                "does not reach dense 30-FPS service at either operating point."
            ),
        },
    }


# Render observed and projected deadlines without blending evidence classes.
def render_markdown(result: dict[str, object]) -> str:
    """Return a concise Markdown real-time envelope report."""

    physical = result["physical_640x360_to_1280x720"]
    lower = result["calibrated_320x180_to_640x360"]
    rows = []
    for fps, row in physical["deadline_results"].items():
        rows.append(
            f"| 640x360 to 1280x720 | {fps} | physical | "
            f"{row['passing_sparse_patterns']}/{row['tested_sparse_patterns']} | "
            f"{row['maximum_observed_selected_tiles']} |"
        )
    for fps, row in lower["deadline_results"].items():
        rows.append(
            f"| 320x180 to 640x360 | {fps} | calibrated projection | n/a | "
            f"{100.0 * row['fraction_of_lower_dense_active_positions']:.2f}% active work |"
        )
    return "\n".join(
        [
            "# Sparse Accelerator Real-Time Envelope",
            "",
            "| Mode | Target FPS | Evidence | Passing masks | Maximum work |",
            "|---|---:|---|---:|---:|",
            *rows,
            "",
            f"Physical dense 720p service is {physical['dense_fps']:.3f} FPS. "
            f"The physically calibrated lower-resolution dense projection is "
            f"{lower['predicted_dense_fps']:.3f} FPS (R^2={lower['cycle_model_r_squared']:.4f}).",
            "",
            f"**Boundary:** {result['claim_boundary']['interpretation']}",
            "",
        ]
    )


# Emit one small deadline table for the limitations and evaluation sections.
def render_latex(result: dict[str, object]) -> str:
    """Return the measured/projection distinction as publication-ready LaTeX."""

    physical = result["physical_640x360_to_1280x720"]
    lower = result["calibrated_320x180_to_640x360"]
    pass30 = physical["deadline_results"]["30"]
    return "\n".join(
        [
            "% Generated by analyze_sparse_realtime_envelope.py.",
            "\\begin{table}[t]",
            "\\centering",
            "\\caption{Zybo real-time boundary (P denotes calibrated projection).}",
            "\\label{tab:realtime-envelope}",
            "\\begin{tabular}{lrrr}",
            "\\toprule",
            "Mode & Dense FPS & 30-FPS sparse pass & Class \\\\ \\midrule",
            f"360p$\\rightarrow$720p & {physical['dense_fps']:.3f} & "
            f"{pass30['passing_sparse_patterns']}/{pass30['tested_sparse_patterns']} & Physical \\\\",
            f"180p$\\rightarrow$360p & {lower['predicted_dense_fps']:.3f} & -- & P \\\\",
            "\\bottomrule",
            "\\end{tabular}",
            "\\end{table}",
            "",
        ]
    )


# Make the physical source and generated views reproducible from the command line.
def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse evidence inputs and report destinations."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--paper", type=Path, default=DEFAULT_PAPER)
    parser.add_argument("--physical", type=Path, default=DEFAULT_PHYSICAL)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--output-markdown", type=Path, default=DEFAULT_MARKDOWN)
    parser.add_argument("--output-latex", type=Path, default=DEFAULT_LATEX)
    return parser.parse_args(argv)


# Write the report and preserve negative real-time findings as first-class data.
def main(argv: Sequence[str] | None = None) -> int:
    """Generate JSON, Markdown, and LaTeX real-time evidence."""

    args = parse_args(argv)
    result = analyze(load_report(args.paper), load_report(args.physical))
    for path in (args.output_json, args.output_markdown, args.output_latex):
        path.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(result, indent=2) + "\n", encoding="ascii")
    args.output_markdown.write_text(render_markdown(result), encoding="ascii")
    args.output_latex.write_text(render_latex(result), encoding="ascii")
    print("SPARSE_REALTIME_ENVELOPE_PASS realtime_720p=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
