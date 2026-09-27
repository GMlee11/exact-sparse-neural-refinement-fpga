"""Tests for long-form sparse accelerator deadline traces."""

from __future__ import annotations

import json

from src.hardware.analyze_sparse_deadline_traces import (
    DEFAULT_INPUT,
    TraceFrame,
    analyze,
    build_trace,
    simulate_trace,
)


def test_trace_builder_is_deterministic_and_bounded() -> None:
    """Repeated generation must preserve the exact publication workload."""

    first = build_trace("jittered_30", [10.0, 20.0], frame_count=20, seed=7)
    second = build_trace("jittered_30", [10.0, 20.0], frame_count=20, seed=7)
    assert first == second
    assert all(b.arrival_ms > a.arrival_ms for a, b in zip(first, first[1:]))


def test_latest_frame_cancellation_never_exposes_partial_output() -> None:
    """A superseding frame may cancel work but cannot create a visible commit."""

    frames = [
        TraceFrame(0, 0.0, 33.0, 20.0, 20.0),
        TraceFrame(1, 10.0, 43.0, 10.0, 10.0),
    ]
    result = simulate_trace(frames)
    assert result["in_flight_cancellations"] == 1
    assert result["useful_commits"] == 1
    assert result["partial_or_stale_visible_commits"] == 0


def test_tracked_physical_services_cover_all_temporal_outcomes() -> None:
    """The five stress traces must account for every frame exactly once."""

    report = json.loads(DEFAULT_INPUT.read_text(encoding="utf-8"))
    result = analyze(report)
    assert len(result["traces"]) == 5
    assert all(result["gates"].values())
    assert any(row["deadline_skips"] > 0 for row in result["traces"])
    assert any(row["in_flight_cancellations"] > 0 for row in result["traces"])
    assert any(row["late_discards"] > 0 for row in result["traces"])
    assert any(row["useful_commits"] > 0 for row in result["traces"])
