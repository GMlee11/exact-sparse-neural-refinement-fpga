"""Tests for measured and calibrated sparse real-time boundaries."""

from __future__ import annotations

import pytest

from src.hardware.analyze_sparse_realtime_envelope import (
    DEFAULT_PAPER,
    DEFAULT_PHYSICAL,
    analyze,
    deadline_ms,
    load_report,
    predicted_cycles,
)


# Frame deadlines must use the complete render-to-present budget convention.
def test_deadline_ms() -> None:
    """Map 30 and 60 FPS to their standard millisecond budgets."""

    assert deadline_ms(30.0) == pytest.approx(33.3333333333)
    assert deadline_ms(60.0) == pytest.approx(16.6666666667)
    with pytest.raises(ValueError, match="positive"):
        deadline_ms(0.0)


# The calibrated model must retain both fixed and active-position terms.
def test_predicted_cycles() -> None:
    """Evaluate a small deterministic cycle model."""

    model = {"fixed_cycles": 100.0, "cycles_per_active_position": 2.0}
    assert predicted_cycles(model, 25) == 150
    with pytest.raises(ValueError, match="nonnegative"):
        predicted_cycles(model, -1)


# Tracked physical evidence must preserve the negative dense real-time result.
def test_tracked_realtime_envelope_is_honest() -> None:
    """Keep physical and projected operating points explicitly separate."""

    result = analyze(load_report(DEFAULT_PAPER), load_report(DEFAULT_PHYSICAL))
    physical = result["physical_640x360_to_1280x720"]
    lower = result["calibrated_320x180_to_640x360"]
    assert physical["dense_fps"] < 5.0
    assert physical["deadline_results"]["30"]["passing_sparse_patterns"] >= 1
    assert physical["deadline_results"]["60"]["passing_sparse_patterns"] == 0
    assert lower["predicted_dense_fps"] < 30.0
    assert result["claim_boundary"]["physical_lower_resolution_realtime_claimed"] is False
