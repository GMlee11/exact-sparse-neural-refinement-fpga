"""Analyze the board-ready Tang sparse-control portability candidate."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Mapping, Sequence

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.utils.research_db import publish_record_set  # noqa: E402


DEFAULT_CONTRACT = Path("fpga/generated/tang_sparse_commit_v1/manifest.json")
DEFAULT_SIMULATION = Path(
    "fpga/docs/captures/paper2/tang_sparse_commit_candidate_v1/simulation.txt"
)
DEFAULT_ROUTE = Path(
    "fpga/docs/captures/paper2/tang_sparse_commit_candidate_v1/nextpnr_report.json"
)
DEFAULT_BITSTREAM = Path("fpga/build/tang_sparse_commit/tang_sparse_commit.fs")
DEFAULT_NEURAL_CAPTURE = Path(
    "fpga/docs/captures/phase8/tang_progressive_v1/physical_capture.json"
)
DEFAULT_CONTROL_CAPTURE = Path(
    "fpga/docs/captures/paper2/tang_sparse_commit_candidate_v1/physical_capture.json"
)
DEFAULT_OUTPUT = Path("results/tables/tang_sparse_commit_candidate_v1.json")
DEFAULT_MARKDOWN = Path("results/tables/tang_sparse_commit_candidate_v1.md")
DEFAULT_LATEX = Path("docs/paper/generated/tang_sparse_commit_candidate_v1.tex")
DEFAULT_DATABASE = Path("data/research.sqlite3")
RECORD_SET = "results.fpga.tang_sparse_commit_candidate_v1"


# Read one object with a useful path-specific failure rather than allowing a
# later nested-key error to obscure a missing or malformed source artifact.
def read_json_object(path: Path) -> Mapping[str, object]:
    """Load one JSON object from disk."""

    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected an object in {path}")
    return value


# nextpnr names the clock by hierarchy, so select its single achieved result
# instead of hard-coding a tool-generated path.
def routed_clock(route: Mapping[str, object]) -> tuple[str, float, float]:
    """Return clock name, achieved MHz, and constrained MHz."""

    clocks = route.get("fmax", {})
    if not isinstance(clocks, dict) or len(clocks) != 1:
        raise ValueError("expected exactly one routed Tang clock")
    name, values = next(iter(clocks.items()))
    return str(name), float(values["achieved"]), float(values["constraint"])


# Build one explicit gate report. The existing neural physical capture and the
# new sparse-control route are kept separate to preserve the two-image scope.
def build_report(
    contract: Mapping[str, object],
    simulation_text: str,
    route: Mapping[str, object],
    neural_capture: Mapping[str, object],
    bitstream_bytes: bytes,
    control_capture: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Build the preflight or physically accepted Tang portability report."""

    clock_name, achieved_mhz, target_mhz = routed_clock(route)
    utilization = route["utilization"]
    expected_checks = int(contract["expected_mask_checks"])
    simulation_gates = {
        "sparse_core_exact": (
            f"PASS: Tang sparse contract mask_checks={expected_checks} outcomes=4"
            in simulation_text
        ),
        "sparse_pin_top_exact": (
            f"PASS: Tang sparse-control top checks={expected_checks} outcomes=4"
            in simulation_text
        ),
        "combined_neural_control_simulation": (
            "PASS: Tang combined neural and sparse-commit contract" in simulation_text
        ),
        "final_marker_exact": (
            "TANG_SPARSE_COMMIT_SIM_PASS mask_checks=576 outcomes=4 "
            "neural_modes=4 packaging=two_image" in simulation_text
        ),
    }
    route_gates = {
        "target_clock_met": achieved_mhz >= target_mhz,
        "control_plane_has_no_neural_dsps": (
            int(utilization["MULT9X9"]["used"]) == 0
            and int(utilization["MULT18X18"]["used"]) == 0
        ),
        "control_plane_has_no_bram": int(utilization["BSRAM"]["used"]) == 0,
    }
    neural_gate = bool(neural_capture.get("led_pass")) and not bool(
        neural_capture.get("led_fail")
    )
    bitstream_hash = hashlib.sha256(bitstream_bytes).hexdigest()
    board_ready = all(simulation_gates.values()) and all(route_gates.values()) and neural_gate

    # A programmer transcript alone is not enough to claim a physical PASS.
    # Bind the board observation to this exact bitstream, expected test counts,
    # valid configuration status, and the mutually exclusive PASS/FAIL LEDs.
    physical_gates = {
        "capture_available": control_capture is not None,
        "artifact_matches": bool(control_capture)
        and control_capture.get("experiment") == "tang_sparse_commit_candidate_v1",
        "bitstream_hash_matches": bool(control_capture)
        and control_capture.get("bitstream_sha256") == bitstream_hash,
        "program_reached_100_percent": bool(control_capture)
        and int(control_capture.get("programmer_reached_percent", 0)) == 100,
        "configuration_status_valid": bool(control_capture)
        and str(control_capture.get("status_register", "")).lower() == "0x00006020",
        "pass_led_asserted": bool(control_capture)
        and bool(control_capture.get("led_pass")),
        "fail_led_clear": bool(control_capture)
        and not bool(control_capture.get("led_fail", True)),
        "mask_check_count_matches": bool(control_capture)
        and int(control_capture.get("sparse_mask_checks", -1)) == expected_checks,
        "commit_outcome_count_matches": bool(control_capture)
        and int(control_capture.get("commit_outcome_checks", -1)) == 4,
        "scope_remains_control_only": bool(control_capture)
        and not bool(control_capture.get("full_frame_sparse_throughput_claimed", True)),
    }
    physical_pass = board_ready and all(physical_gates.values())
    return {
        "schema_version": 1,
        "artifact": "tang_sparse_commit_candidate_v1",
        "decision": (
            "physical_cross_vendor_sparse_control_pass"
            if physical_pass
            else (
                "board_ready_pending_tang_sparse_control_physical_pass"
                if board_ready
                else "reject_tang_sparse_control_preflight"
            )
        ),
        "board_ready": board_ready,
        "physical_pass": physical_pass,
        "packaging": {
            "strategy": "two_image_resource_scaled_portability",
            "reason": (
                "the combined neural-plus-control image passed simulation but did "
                "not route reliably at the Tang placement limit"
            ),
            "integrated_full_frame_sparse_throughput_claimed": False,
        },
        "neural_image": {
            "physical_pass": neural_gate,
            "bitstream_sha256": neural_capture["bitstream_sha256"],
            "mode_checks": 4,
            "evidence": DEFAULT_NEURAL_CAPTURE.as_posix(),
        },
        "sparse_control_image": {
            "physical_pass": physical_pass,
            "physical_status": (
                "accepted_status_0x00006020_led_pass"
                if physical_pass
                else "pending_connected_tang_primer20k"
            ),
            "physical_evidence": (
                DEFAULT_CONTROL_CAPTURE.as_posix() if control_capture else None
            ),
            "mask_checks": expected_checks,
            "commit_outcome_checks": 4,
            "bitstream_sha256": bitstream_hash,
            "clock_name": clock_name,
            "target_mhz": target_mhz,
            "achieved_mhz": achieved_mhz,
            "utilization": {
                "lut4_used": int(utilization["LUT4"]["used"]),
                "lut4_available": int(utilization["LUT4"]["available"]),
                "dff_used": int(utilization["DFF"]["used"]),
                "dff_available": int(utilization["DFF"]["available"]),
                "bram_used": int(utilization["BSRAM"]["used"]),
                "dsp9_used": int(utilization["MULT9X9"]["used"]),
            },
        },
        "simulation_gates": simulation_gates,
        "route_gates": route_gates,
        "physical_gates": physical_gates,
        "evidence_boundary": {
            "proves_after_physical_pass": (
                "cross-vendor neural numerical plus exact sparse-control semantics"
            ),
            "does_not_prove": [
                "integrated full-frame Tang sparse throughput",
                "Zybo-equivalent parallelism",
                "physical energy efficiency",
            ],
        },
    }


# Markdown is both an experiment summary and the exact handoff when the Tang is
# later connected.
def render_markdown(report: Mapping[str, object]) -> str:
    """Render the Tang candidate or accepted physical summary."""

    control = report["sparse_control_image"]
    utilization = control["utilization"]
    lines = [
        "# Tang Sparse-Commit Candidate V1",
        "",
        f"**Decision:** `{report['decision']}`",
        "",
        "| Measurement | Result |",
        "|---|---:|",
        f"| Generated mask checks | {control['mask_checks']} |",
        f"| Commit outcomes | {control['commit_outcome_checks']} |",
        f"| Routed clock target / achieved | {control['target_mhz']:.3f} / {control['achieved_mhz']:.3f} MHz |",
        f"| LUT4 | {utilization['lut4_used']}/{utilization['lut4_available']} |",
        f"| DFF | {utilization['dff_used']}/{utilization['dff_available']} |",
        f"| BSRAM / DSP9 | {utilization['bram_used']} / {utilization['dsp9_used']} |",
        f"| Physical sparse-control PASS | {'Yes' if control['physical_pass'] else 'Pending'} |",
        f"| Sparse-control bitstream SHA256 | `{control['bitstream_sha256']}` |",
        "",
        "The accepted Tang packaging uses two physical images. The previously captured progressive image proves the neural A/B/C numerical contract. The new image proves exact radius-0/1/2 mask closure and useful/skip/cancel/late commit semantics. Their combined top passes simulation but is retained only as a placement-limit result.",
        "",
        "This does not claim integrated Tang full-frame sparse throughput, Zybo-equivalent parallelism, or energy efficiency.",
        "",
    ]
    if control["physical_pass"]:
        lines.extend(
            [
                "## Physical Validation",
                "",
                "The Tang SRAM programmer reached 100%, configuration status was `0x00006020`, and the bitstream-specific self-test asserted LED2 PASS while the mutually exclusive LED3 FAIL output remained clear.",
                "",
            ]
        )
    else:
        lines.extend(
            [
                "## Physical Stopping Point",
                "",
                "Connect the Tang Primer 20K over JTAG and run:",
                "",
                "```powershell",
                "powershell -ExecutionPolicy Bypass -File fpga/scripts/run_tang_sparse_commit_physical.ps1",
                "```",
                "",
                "After LED2 is on and LED3 is off, rerun with `-ConfirmLedPass`.",
                "",
            ]
        )
    return "\n".join(lines)


# The focused paper gets one compact row whose status follows the hash-bound
# physical capture rather than a hand-edited publication claim.
def render_latex(report: Mapping[str, object]) -> str:
    """Render a compact LaTeX table for the Paper 2 appendix."""

    control = report["sparse_control_image"]
    utilization = control["utilization"]
    physical_label = "PASS" if control["physical_pass"] else "Pending"
    caption = (
        "Physically validated resource-scaled Tang sparse-control port."
        if control["physical_pass"]
        else "Board-ready resource-scaled Tang sparse-control port."
    )
    return "\n".join(
        [
            "% Generated by analyze_tang_sparse_commit_candidate.py.",
            "\\begin{table}[t]",
            "\\centering",
            f"\\caption{{{caption}}}",
            "\\label{tab:tang-sparse-control-candidate}",
            "\\begin{tabular}{lr}",
            "\\hline",
            "Measurement & Result \\\\",
            "\\hline",
            f"Mask closure checks & {control['mask_checks']} \\\\",
            f"Commit outcome checks & {control['commit_outcome_checks']} \\\\",
            f"Target / achieved clock & {control['target_mhz']:.1f} / {control['achieved_mhz']:.1f} MHz \\\\",
            f"LUT4 / DFF & {utilization['lut4_used']} / {utilization['dff_used']} \\\\",
            f"Physical sparse-control PASS & {physical_label} \\\\",
            "\\hline",
            "\\end{tabular}",
            "\\end{table}",
            "",
        ]
    )


# Flatten one summary row for the dashboard without duplicating the raw route
# report's nested vendor-specific structure.
def database_rows(report: Mapping[str, object]) -> list[dict[str, object]]:
    """Return the canonical database row for this candidate."""

    control = report["sparse_control_image"]
    utilization = control["utilization"]
    return [
        {
            "artifact": report["artifact"],
            "decision": report["decision"],
            "board_ready": report["board_ready"],
            "physical_pass": control["physical_pass"],
            "mask_checks": control["mask_checks"],
            "commit_outcome_checks": control["commit_outcome_checks"],
            "target_mhz": control["target_mhz"],
            "achieved_mhz": control["achieved_mhz"],
            "lut4_used": utilization["lut4_used"],
            "dff_used": utilization["dff_used"],
            "bitstream_sha256": control["bitstream_sha256"],
        }
    ]


def build_parser() -> argparse.ArgumentParser:
    """Build the Tang candidate analysis command line."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--simulation", type=Path, default=DEFAULT_SIMULATION)
    parser.add_argument("--route", type=Path, default=DEFAULT_ROUTE)
    parser.add_argument("--bitstream", type=Path, default=DEFAULT_BITSTREAM)
    parser.add_argument("--neural-capture", type=Path, default=DEFAULT_NEURAL_CAPTURE)
    parser.add_argument("--control-capture", type=Path, default=DEFAULT_CONTROL_CAPTURE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--markdown", type=Path, default=DEFAULT_MARKDOWN)
    parser.add_argument("--latex", type=Path, default=DEFAULT_LATEX)
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Analyze and publish the Tang sparse-control candidate."""

    args = build_parser().parse_args(argv)
    try:
        # Keep preflight analysis usable before board access, then promote it
        # automatically when the hash-bound physical capture appears.
        control_capture = (
            read_json_object(args.control_capture)
            if args.control_capture.is_file()
            else None
        )
        report = build_report(
            read_json_object(args.contract),
            args.simulation.read_text(encoding="utf-8"),
            read_json_object(args.route),
            read_json_object(args.neural_capture),
            args.bitstream.read_bytes(),
            control_capture,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.markdown.parent.mkdir(parents=True, exist_ok=True)
        args.latex.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        args.markdown.write_text(render_markdown(report), encoding="utf-8")
        args.latex.write_text(render_latex(report), encoding="utf-8")
        publish_record_set(
            args.database,
            RECORD_SET,
            database_rows(report),
            overwrite=True,
            source_path=args.output.as_posix(),
        )
    except (FileNotFoundError, KeyError, OSError, TypeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(
        "TANG_SPARSE_COMMIT_ANALYSIS "
        f"decision={report['decision']} "
        f"sha256={report['sparse_control_image']['bitstream_sha256']}"
    )
    return 0 if report["board_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
