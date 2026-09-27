"""Tests for physical commit-safe sparse-accelerator analysis."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.hardware.analyze_sparse_hierarchical_commit_physical import (
    extract_stage_waits,
    parse_capture,
    parse_route,
    pearson_r_squared,
    percent_reduction,
    stage_wait_profile_is_valid,
)


# Keep the version-four telemetry parser strict and order-independent.
def test_extract_stage_waits_accepts_complete_profile() -> None:
    """All seven counters should be converted to integers as one profile."""

    row = {
        "raw_input_wait": "100",
        "conv1_window_wait": "90",
        "conv1_output_wait": "80",
        "conv2_window_wait": "70",
        "conv2_output_wait": "60",
        "conv3_window_wait": "50",
        "conv3_output_wait": "40",
    }
    waits = extract_stage_waits(row)
    assert waits is not None
    assert waits["conv2_window_wait"] == 70


# Partial telemetry would make bottleneck attribution misleading and is fatal.
def test_extract_stage_waits_rejects_partial_profile() -> None:
    """A capture must contain either all stage counters or none of them."""

    with pytest.raises(ValueError, match="incomplete"):
        extract_stage_waits({"raw_input_wait": "10"})


# Mailbox sentinels must never be rendered as impossible wait percentages.
def test_stage_wait_profile_rejects_words_larger_than_service() -> None:
    """A stale magic word cannot be interpreted as a physical cycle count."""

    assert stage_wait_profile_is_valid({"raw": 99}, compute_cycles=100)
    assert not stage_wait_profile_is_valid({"raw": 0x53484332}, compute_cycles=100)


# Ensure reordered machine-readable fields remain parseable.
def test_parse_capture_finds_required_rows() -> None:
    """Capture parsing should recover status, patterns, and outcomes."""

    text = "\n".join(
        [
            "SPARSE_HIERARCHICAL_SUITE_STATUS pattern_count=1 completed_count=1 overall_status=0x1",
            "SPARSE_HIERARCHICAL_COMMIT_PHYSICAL pattern_id=0 selected_tiles=60",
            "SPARSE_HIERARCHICAL_COMMIT_OUTCOMES frame_launches=4 useful_commits=1",
        ]
    )
    status, rows, outcome = parse_capture(text)
    assert status["pattern_count"] == "1"
    assert rows[0]["selected_tiles"] == "60"
    assert outcome["frame_launches"] == "4"


# Reject incomplete physical evidence rather than silently emitting a report.
def test_parse_capture_rejects_missing_outcome() -> None:
    """The atomic-commit outcome row is mandatory evidence."""

    with pytest.raises(ValueError, match="outcome"):
        parse_capture(
            "SPARSE_HIERARCHICAL_SUITE_STATUS pattern_count=1\n"
            "SPARSE_HIERARCHICAL_COMMIT_PHYSICAL pattern_id=0\n"
        )


# Check percentage and correlation helpers at exact boundaries.
def test_numeric_helpers() -> None:
    """Savings and perfect linear correlation should be exact."""

    assert percent_reduction(75.0, 100.0) == pytest.approx(25.0)
    assert pearson_r_squared([1.0, 2.0, 3.0], [4.0, 6.0, 8.0]) == pytest.approx(1.0)


# Parse the stable report rows used by the physical analyzer.
def test_parse_route_extracts_resources() -> None:
    """Timing closure and principal resource counts should be retained."""

    timing = """
      3.573        0.000                      0               232084
All user specified timing constraints are met.
clk_fpga_0  {0.000 10.000}     20.000          50.000
"""
    utilization = """
| Slice LUTs | 45046 | 0 | 53200 | 84.67 |
| Slice Registers | 26648 | 0 | 106400 | 25.05 |
| Block RAM Tile | 3.5 | 0 | 140 | 2.50 |
| DSPs | 180 | 0 | 220 | 81.82 |
"""
    result = parse_route(timing, utilization)
    assert result["timing_closed"] is True
    assert result["wns_ns"] == pytest.approx(3.573)
    assert result["dsps"] == 180
    assert result["slice_luts"] == 45046


# The tracked physical capture should remain analyzable after future refactors.
def test_tracked_capture_contains_version_three_stall_counters() -> None:
    """The physical artifact must include the causal instrumentation fields."""

    root = Path(__file__).resolve().parents[1]
    capture = root / "fpga/docs/captures/sparse_refinement_accelerator_v2/hierarchical_commit_suite_physical/physical_zybo_sparse_hierarchical_commit_suite.txt"
    _, rows, _ = parse_capture(capture.read_text(encoding="utf-8"))
    assert len(rows) == 16
    assert int(rows[0]["input_stalls"]) > 0
    assert int(rows[0]["output_stalls"]) == 0
