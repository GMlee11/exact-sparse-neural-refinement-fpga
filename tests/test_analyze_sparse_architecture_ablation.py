"""Tests for descriptive sparse-architecture operating points."""

from __future__ import annotations

import pytest

from src.hardware.analyze_sparse_architecture_ablation import (
    DEFAULT_BALANCED,
    DEFAULT_COMMIT,
    DEFAULT_COMMIT_MANIFEST,
    DEFAULT_CONTROLLED,
    DEFAULT_HIERARCHICAL,
    DEFAULT_PAPER,
    analyze,
    cycle_derived_elapsed_ms,
    find_physical_mask_result,
    load_report,
    reduction_percent,
    render_geometry_latex,
    render_latex,
)


# Percentage arithmetic must use the baseline as the denominator.
def test_reduction_percent() -> None:
    """Report a reduction from 100 to 75 as exactly 25 percent."""

    assert reduction_percent(100.0, 75.0) == pytest.approx(25.0)


def test_cycle_counter_conversion_uses_each_realized_clock() -> None:
    """Prevent a counter reduction from being presented as elapsed-time speedup."""

    assert cycle_derived_elapsed_ms(9_857_730, 100.0) == pytest.approx(98.57730)
    assert cycle_derived_elapsed_ms(4_922_897, 50.0) == pytest.approx(98.45794)


# Mask joins must fail if a manifest does not contain one unique row.
def test_find_physical_mask_result_rejects_missing_mask() -> None:
    """Prevent density-only matches from replacing exact mask identity."""

    with pytest.raises(ValueError, match="expected one manifest row"):
        find_physical_mask_result({"patterns": []}, {"patterns": []}, "0x1")


# Tracked board evidence must pass all organization, resource, and safety gates.
def test_tracked_architecture_ablation_passes() -> None:
    """Recompute descriptive operating points from tracked result artifacts."""

    result = analyze(
        load_report(DEFAULT_PAPER),
        load_report(DEFAULT_HIERARCHICAL),
        load_report(DEFAULT_BALANCED),
        load_report(DEFAULT_COMMIT),
        load_report(DEFAULT_COMMIT_MANIFEST),
        load_report(DEFAULT_CONTROLLED),
    )
    assert result["gates"]["all_pass"] is True
    assert result["canonical_mask_hex"] == "0x0000C03F0FE03000"
    assert result["mechanism_effects"]["global_closure_and_persistent_reuse"][
        "cycle_reduction_percent"
    ] > 30.0
    commit = result["mechanism_effects"]["private_atomic_commit"]
    assert commit["dsp_delta"] == 0
    assert commit["bram_delta"] == 0.0
    assert abs(commit["service_overhead_percent"]) < 0.01
    assert len(result["controlled_geometry_families"]) == 5
    assert all(row["all_exact"] for row in result["controlled_geometry_families"])
    geometry_table = render_geometry_latex(result)
    assert "Checkerboard" in geometry_table
    assert "Clustered" in geometry_table
    assert "Motion band" in geometry_table
    assert "percent saved" in geometry_table
    operating_table = render_latex(result)
    assert "Coupled routed operating points" in operating_table
    assert "prevent isolated marginal attribution" in operating_table
    assert "Physical mechanism ablation" not in operating_table
    headline = result["headline_operating_point_comparison"]
    assert headline["independent_cycles"] == 9_857_730
    assert headline["independent_clock_mhz"] == pytest.approx(100.0)
    assert headline["independent_cycle_derived_compute_ms"] == pytest.approx(98.57730)
    assert headline["persistent_cycles"] == 4_922_897
    assert headline["persistent_clock_mhz"] == pytest.approx(50.0)
    assert headline["persistent_cycle_derived_compute_ms"] == pytest.approx(98.45794)
    assert headline["cycle_derived_elapsed_delta_ms"] == pytest.approx(-0.11936)
    assert headline["wall_time_speedup_claimed"] is False
    assert headline["clock_normalized_acceleration_claimed"] is False
    assert headline["causal_mechanism_isolated"] is False
    assert "cycles divided by each row's realized clock" in operating_table
