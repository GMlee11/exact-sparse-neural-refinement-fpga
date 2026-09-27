"""Summarize the physical Zybo trained sparse-tile capture.

The parser deliberately distinguishes the measured single-tile datapath from
full-frame projections.  It binds the UART-independent mailbox capture to the
routed timing/resource reports and emits compact JSON, Markdown, and LaTeX
artifacts for the publication evidence trail.
"""

from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path
from typing import Sequence


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CAPTURE = (
    ROOT
    / "fpga"
    / "docs"
    / "captures"
    / "sparse_refinement_accelerator_v1"
    / "physical_zybo_trained_tile.txt"
)
DEFAULT_BOARD_MANIFEST = (
    ROOT / "results" / "tables" / "sparse_refinement_trained_tile_board_ready.json"
)
DEFAULT_TIMING = (
    ROOT / "fpga" / "build" / "sparse_trained_tile_zybo" / "reports" / "timing_summary.txt"
)
DEFAULT_UTILIZATION = (
    ROOT / "fpga" / "build" / "sparse_trained_tile_zybo" / "reports" / "utilization.txt"
)
DEFAULT_JSON = ROOT / "results" / "tables" / "sparse_refinement_trained_tile_physical.json"
DEFAULT_MARKDOWN = ROOT / "results" / "tables" / "sparse_refinement_trained_tile_physical.md"
DEFAULT_LATEX = ROOT / "docs" / "paper" / "generated" / "sparse_refinement_trained_tile_physical.tex"


# Parse machine-readable ``key=value`` fields without depending on their order.
def parse_fields(line: str) -> dict[str, str]:
    """Return key/value tokens from one physical-capture line."""

    return dict(re.findall(r"([A-Za-z_][A-Za-z0-9_]*)=([^\s]+)", line))


# Require exactly one line for each named mailbox result to avoid stale merges.
def find_result_line(text: str, prefix: str) -> dict[str, str]:
    """Find and parse one machine-readable capture row."""

    matches = [line for line in text.splitlines() if line.startswith(prefix)]
    if len(matches) != 1:
        raise ValueError(f"expected one {prefix!r} row, found {len(matches)}")
    return parse_fields(matches[0])


# Extract the first design-level WNS from Vivado's timing summary table.
def parse_wns_ns(text: str) -> float:
    """Return routed worst negative slack in nanoseconds."""

    header = text.find("WNS(ns)")
    if header < 0:
        raise ValueError("timing report does not contain WNS(ns)")
    match = re.search(r"^\s*(-?\d+\.\d+)\s+", text[header:], re.MULTILINE)
    if match is None:
        raise ValueError("timing report does not contain a design WNS value")
    return float(match.group(1))


# Extract one named resource from Vivado's pipe-delimited utilization report.
def parse_resource(text: str, name: str) -> float:
    """Return the used count for a named utilization row."""

    match = re.search(
        rf"^\|\s*{re.escape(name)}\s*\|\s*([0-9.]+)\s*\|",
        text,
        re.MULTILINE,
    )
    if match is None:
        raise ValueError(f"utilization report does not contain {name!r}")
    return float(match.group(1))


# Validate the immutable mailbox facts before calculating any derived values.
def analyze_capture(
    capture_text: str,
    board_manifest: dict[str, object],
    timing_text: str,
    utilization_text: str,
) -> dict[str, object]:
    """Return a publication-scoped summary of one physical capture."""

    header = find_result_line(capture_text, "SPARSE_TRAINED_MAILBOX ")
    tile = find_result_line(capture_text, "SPARSE_TRAINED_TILE ")
    deadline = find_result_line(capture_text, "SPARSE_TRAINED_DEADLINE ")
    cancel = find_result_line(capture_text, "SPARSE_TRAINED_CANCEL ")
    completion = find_result_line(
        capture_text, "SPARSE_TRAINED_BOARD_COMPLETE "
    )
    if (
        header.get("magic", "").lower() != "0x5352544e"
        or int(header.get("version", "-1")) != 1
        or int(header.get("result", "-1")) != 0
        or completion.get("neural_datapath") != "1"
    ):
        raise ValueError("physical trained-tile mailbox did not pass")
    expected_checksum = str(board_manifest["expected_residual_checksum"]).lower()
    if tile.get("checksum", "").lower() != expected_checksum:
        raise ValueError("physical residual checksum differs from frozen manifest")
    if (
        int(tile["accepted"]) != 1
        or int(tile["issued"]) != 1
        or int(tile["commits"]) != 1
        or int(tile["late"]) != 0
        or int(deadline["skips"]) != 1
        or int(cancel["canceled"]) != 1
        or int(cancel["commits"]) != 0
        or int(cancel["output_bytes"]) != 0
        or int(cancel["protocol_errors"]) != 0
    ):
        raise ValueError("physical causal counters failed their locked contract")

    fabric_hz = int(tile["fabric_clock_hz"])
    arm_timer_hz = int(tile["arm_timer_hz"])
    neural_cycles = int(tile["neural_cycles"])
    arm_ticks = int(tile["arm_ticks"])
    neural_ms = neural_cycles * 1000.0 / fabric_hz
    service_ms = arm_ticks * 1000.0 / arm_timer_hz
    full_grid_tiles = math.ceil(640 / 64) * math.ceil(360 / 60)
    projected_full_grid_ms = neural_ms * full_grid_tiles

    return {
        "schema_version": 1,
        "artifact": "sparse_refinement_trained_tile_physical_v1",
        "decision": "accept_trained_tile_datapath_continue_sparse_architecture",
        "model": {
            "id": board_manifest["model_id"],
            "checkpoint_sha256": board_manifest["model_checkpoint_sha256"],
            "residual_checksum": tile["checksum"],
        },
        "physical": {
            "board": "Zybo Z7-20",
            "fabric_clock_hz": fabric_hz,
            "arm_timer_hz": arm_timer_hz,
            "neural_cycles": neural_cycles,
            "scheduler_cycles": int(tile["scheduler_cycles"]),
            "neural_ms": neural_ms,
            "tile_dma_service_ms": service_ms,
            "input_words": int(tile["input_words"]),
            "output_words": int(tile["output_words"]),
            "accounted_input_bytes": int(tile["input_bytes"]),
            "accounted_output_bytes": int(tile["output_bytes"]),
            "deadline_skips": int(deadline["skips"]),
            "canceled_regions": int(cancel["canceled"]),
            "canceled_commits": int(cancel["commits"]),
            "protocol_errors": int(cancel["protocol_errors"]),
        },
        "implementation": {
            "timing_closed": "All user specified timing constraints are met"
            in timing_text,
            "wns_ns": parse_wns_ns(timing_text),
            "slice_luts": int(parse_resource(utilization_text, "Slice LUTs")),
            "slice_registers": int(
                parse_resource(utilization_text, "Slice Registers")
            ),
            "bram_tiles": parse_resource(utilization_text, "Block RAM Tile"),
            "dsp48e1": int(parse_resource(utilization_text, "DSPs")),
        },
        "non_measured_projection": {
            "fixed_tiles_per_640x360_frame": full_grid_tiles,
            "serialized_compute_only_ms": projected_full_grid_ms,
            "serialized_compute_only_fps": 1000.0 / projected_full_grid_ms,
            "warning": (
                "This is a fixed-tile compute-only extrapolation, not measured "
                "full-frame sparse throughput; it excludes edge handling, "
                "descriptor/tile dispatch, reconstruction, and composition."
            ),
        },
        "evidence_boundary": (
            "A frozen trained INT8 tile is bit-exact in physical PL, and true "
            "deadline bypass/cancellation prevent useless commits. Variable-size "
            "compaction, halo reuse across regions, fused reconstruction, "
            "full-frame throughput, and wall energy remain unproven."
        ),
        "provenance": {
            "bitstream_sha256": board_manifest["bitstream_sha256"],
            "xsa_sha256": board_manifest["xsa_sha256"],
            "elf_sha256": board_manifest["elf_sha256"],
        },
    }


# Keep the advisor-facing table compact while retaining the caveat beside it.
def render_markdown(result: dict[str, object]) -> str:
    """Return a human-readable Markdown result table."""

    physical = result["physical"]
    implementation = result["implementation"]
    projection = result["non_measured_projection"]
    assert isinstance(physical, dict)
    assert isinstance(implementation, dict)
    assert isinstance(projection, dict)
    return f"""# Physical Trained Sparse-Refinement Tile

| Measurement | Result |
|---|---:|
| Model/checksum | `{result['model']['id']}` / `{result['model']['residual_checksum']}` |
| Physical neural cycles | {physical['neural_cycles']:,} |
| Physical neural time | {physical['neural_ms']:.3f} ms at {physical['fabric_clock_hz'] / 1e6:.0f} MHz |
| Tile-DMA service interval | {physical['tile_dma_service_ms']:.3f} ms |
| Residual words checked | {physical['output_words']:,} |
| Deadline bypass | {physical['deadline_skips']} region, zero neural issue |
| In-flight cancellation | {physical['canceled_regions']} region, zero commits |
| Routed resources | {implementation['slice_luts']:,} LUTs, {implementation['slice_registers']:,} registers, {implementation['dsp48e1']}/220 DSP48s, {implementation['bram_tiles']:g} BRAM tiles |
| Routed timing | {implementation['wns_ns']:+.3f} ns WNS; closed |

The exact signed-Q7 residual checksum matches the independent Python integer
model. ELI5: real trained neural arithmetic ran on the FPGA and produced every
checked correction correctly. A job that was already too late was skipped, and
a canceled job was prevented from changing the output.

**Boundary:** {result['evidence_boundary']}

The {projection['serialized_compute_only_fps']:.3f}-FPS 640x360 fixed-grid value
is only a {projection['fixed_tiles_per_640x360_frame']}-tile arithmetic
extrapolation. {projection['warning']}
"""


# Generate a self-contained table that the IEEE source can include directly.
def render_latex(result: dict[str, object]) -> str:
    """Return a compact IEEE-style LaTeX table."""

    physical = result["physical"]
    implementation = result["implementation"]
    assert isinstance(physical, dict)
    assert isinstance(implementation, dict)
    return rf"""% Generated by analyze_sparse_trained_tile_capture.py.
\begin{{table}}[t]
\centering
\caption{{Physical trained sparse-refinement tile on Zybo Z7-20.}}
\label{{tab:sparse-trained-tile-physical}}
\begin{{tabular}}{{lr}}
\hline
Measurement & Result \\
\hline
Residual words checked & {physical['output_words']:,} \\
Neural cycles & {physical['neural_cycles']:,} \\
Neural time at 100 MHz & {physical['neural_ms']:.3f} ms \\
Tile-DMA service interval & {physical['tile_dma_service_ms']:.3f} ms \\
Deadline skips / canceled commits & {physical['deadline_skips']} / {physical['canceled_commits']} \\
LUTs / registers / DSP48s & {implementation['slice_luts']:,} / {implementation['slice_registers']:,} / {implementation['dsp48e1']} \\
Routed WNS & {implementation['wns_ns']:+.3f} ns \\
\hline
\end{{tabular}}
\end{{table}}
"""


# Write all publication artifacts in one deterministic operation.
def write_outputs(
    result: dict[str, object],
    json_path: Path,
    markdown_path: Path,
    latex_path: Path,
) -> None:
    """Write JSON, Markdown, and LaTeX summaries."""

    for path in (json_path, markdown_path, latex_path):
        path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="ascii"
    )
    markdown_path.write_text(render_markdown(result), encoding="ascii")
    latex_path.write_text(render_latex(result), encoding="ascii")


# Keep path overrides available for tests and regenerated build locations.
def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse capture/report and output paths."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", type=Path, default=DEFAULT_CAPTURE)
    parser.add_argument("--board-manifest", type=Path, default=DEFAULT_BOARD_MANIFEST)
    parser.add_argument("--timing-report", type=Path, default=DEFAULT_TIMING)
    parser.add_argument("--utilization-report", type=Path, default=DEFAULT_UTILIZATION)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--output-markdown", type=Path, default=DEFAULT_MARKDOWN)
    parser.add_argument("--output-latex", type=Path, default=DEFAULT_LATEX)
    return parser.parse_args(argv)


# Validate physical evidence first, then publish only a passing summary.
def main(argv: Sequence[str] | None = None) -> int:
    """Analyze the capture and emit all compact evidence artifacts."""

    args = parse_args(argv)
    result = analyze_capture(
        args.capture.read_text(encoding="utf-8"),
        json.loads(args.board_manifest.read_text(encoding="utf-8")),
        args.timing_report.read_text(encoding="utf-8", errors="replace"),
        args.utilization_report.read_text(encoding="utf-8", errors="replace"),
    )
    write_outputs(result, args.output_json, args.output_markdown, args.output_latex)
    physical = result["physical"]
    assert isinstance(physical, dict)
    print(
        "SPARSE_TRAINED_PHYSICAL_ANALYSIS_PASS "
        f"cycles={physical['neural_cycles']} "
        f"neural_ms={physical['neural_ms']:.6f} "
        f"checksum={result['model']['residual_checksum']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
