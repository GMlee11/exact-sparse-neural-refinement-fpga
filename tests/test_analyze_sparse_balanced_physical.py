"""Unit tests for balanced sparse-pipeline physical capture parsing."""

from __future__ import annotations

import pytest

from src.hardware.analyze_sparse_balanced_physical import (
    parse_scenario,
    reduction_percent,
)


SAMPLE_CAPTURE = """
SPARSE_FRAME_NAIVE compute_cycles=150 scheduler_cycles=2 service_ms=1.5 packet_words=2 accepted=2 issued=2 coalesced=0 commits=2 lr_input_bytes=6 output_bytes=8 halo_bytes_saved=0 checksum=0x12345678
SPARSE_FRAME_NAIVE_DISTRIBUTION repetitions=10 average_ms=1.500 median_ms=1.500 p95_ms=1.600 p99_ms=1.600 min_ms=1.400 max_ms=1.600 average_compute_cycles=150
SPARSE_FRAME_COMPACT compute_cycles=100 scheduler_cycles=1 service_ms=1.0 packet_words=1 accepted=2 issued=1 coalesced=1 commits=1 lr_input_bytes=3 output_bytes=4 halo_bytes_saved=1 checksum=0xABCDEF01
SPARSE_FRAME_COMPACT_DISTRIBUTION repetitions=10 average_ms=1.000 median_ms=1.000 p95_ms=1.100 p99_ms=1.100 min_ms=0.900 max_ms=1.100 average_compute_cycles=100
"""


# Parsing must preserve the exact output identity and repeated timing fields.
def test_parse_scenario_extracts_required_physical_fields() -> None:
    """Read one compact work-list scenario from machine-readable capture text."""

    result = parse_scenario(SAMPLE_CAPTURE, "FRAME")
    assert result["checksum"] == "0xabcdef01"
    assert result["issued_regions"] == 1
    assert result["repetitions"] == 10
    assert result["average_compute_cycles"] == 100
    assert result["packet_words"] == 1
    assert result["lr_input_bytes"] == 3
    assert result["rgb_output_bytes"] == 4


# The independent organization must remain separately available as physical data.
def test_parse_scenario_extracts_independent_job_measurement() -> None:
    """Read the complete independent-job replay without projecting one tile."""

    result = parse_scenario(SAMPLE_CAPTURE, "FRAME", "NAIVE")
    assert result["organization"] == "independent_jobs"
    assert result["issued_regions"] == 2
    assert result["coalesced_regions"] == 0
    assert result["average_compute_cycles"] == 150


# Reject misspelled organizations rather than silently selecting a baseline.
def test_parse_scenario_rejects_unknown_organization() -> None:
    """Keep independent and rectangle evidence labels unambiguous."""

    with pytest.raises(ValueError, match="NAIVE or COMPACT"):
        parse_scenario(SAMPLE_CAPTURE, "FRAME", "projected")


# A drop from 100 to 60 units is an unambiguous 40% physical reduction.
def test_reduction_percent_reports_positive_savings() -> None:
    """Calculate candidate savings using the uniform design as denominator."""

    assert reduction_percent(100.0, 60.0) == pytest.approx(40.0)


# Missing or zero baselines cannot silently create an infinite speedup claim.
def test_reduction_percent_rejects_invalid_baseline() -> None:
    """Reject nonpositive physical baselines before publication arithmetic."""

    with pytest.raises(ValueError, match="nonnegative"):
        reduction_percent(0.0, 1.0)
