"""Tests for provisional sparse accelerator post-route power analysis."""

from __future__ import annotations

from pathlib import Path

from src.hardware.analyze_sparse_postroute_power import (
    analyze,
    parse_controller_saif,
    parse_vivado_power_report,
)


def test_vivado_parser_requires_routed_summary_and_accelerator_hierarchy(tmp_path: Path) -> None:
    """Parse only the fields needed by the explicitly provisional estimate."""

    report = tmp_path / "power.rpt"
    report.write_text(
        """Tool Version     : Vivado v.2020.2
Design State     : routed
| Total On-Chip Power (W)  | 1.630 |
| Dynamic (W)              | 1.490 |
| Device Static (W)        | 0.140 |
| Overall confidence level | Medium | note |
|     e              |     0.080 |
""",
        encoding="utf-8",
    )
    parsed = parse_vivado_power_report(report)
    assert parsed["total_onchip_w"] == 1.630
    assert parsed["accelerator_hierarchy_w"] == 0.080
    assert parsed["simulation_activity_file"] == "none"


def test_activity_scaling_never_becomes_a_physical_claim() -> None:
    """Duty estimates may vary, but all physical power claim flags stay false."""

    power = {
        "total_onchip_w": 1.63,
        "accelerator_hierarchy_w": 0.08,
    }
    workloads = {
        "patterns": [
            {
                "pattern_id": 0,
                "label": "dense",
                "selected_tiles": 60,
                "average_fpga_cycles": 100,
                "average_service_ms": 10.0,
            },
            {
                "pattern_id": 1,
                "label": "sparse",
                "selected_tiles": 10,
                "average_fpga_cycles": 40,
                "average_service_ms": 4.0,
            },
        ]
    }
    result = analyze(power, workloads)
    assert result["workloads"][1]["estimated_onchip_w"] < 1.63
    assert result["claim_boundary"]["physical_wall_power_claimed"] is False
    assert result["claim_boundary"]["physical_energy_claimed"] is False


# A controller-only SAIF must be retained as provenance, not promoted to full coverage.
def test_controller_saif_parser_records_limited_scope(tmp_path: Path) -> None:
    """Parse signal activity while keeping the full-datapath coverage flag false."""

    saif = tmp_path / "controller.saif"
    saif.write_text(
        "(SAIFILE (TIMESCALE 1 ps) (DURATION 1000) "
        "(INSTANCE dut (NET (clk (TC 20)) (start (TC 2)))))\n",
        encoding="ascii",
    )
    activity = parse_controller_saif(saif)
    assert activity["annotated_signal_count"] == 2
    assert activity["total_toggle_count"] == 22
    assert activity["full_routed_datapath_annotated"] is False
