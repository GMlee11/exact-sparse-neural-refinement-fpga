"""Tests for the joined independent-worklist architecture decision."""

import pytest

from src.hardware.analyze_sparse_independent_worklists import (
    analyze,
    maximum_scene_psnr_drop,
    sha256_jsonl_canonical_lf,
)


# Build a compact contract with the same evidence boundaries as the real run.
def _contract() -> dict[str, object]:
    """Return a minimal frozen independent-worklist contract."""

    return {
        "source": {
            "observations": "results/analysis/observations.jsonl",
            "observations_sha256": "abc123",
            "frame_count": 100,
            "sequence_count": 2,
            "used_for_fpga_design_or_tuning": False,
        },
        "selection": {"expected_pattern_count": 3},
        "acceptance": {"minimum_cycles_vs_active_positions_r_squared": 0.99},
        "evidence_boundary": {"scope": "architecture_only"},
    }


# Build one dense control and two sparse physical rows with passing savings.
def _physical(*, exact: bool = True) -> dict[str, object]:
    """Return an analyzer-compatible physical architecture result."""

    return {
        "gates": {
            "all_masks_bit_and_counter_exact": exact,
            "all_commit_outcomes_exact": exact,
        },
        "summary": {
            "cycles_vs_active_positions_r_squared": 0.999,
            "control_service_fps": 4.2,
        },
        "route": {
            "timing_closed": True,
            "wns_ns": 2.0,
            "target_mhz": 58.824,
            "dsps": 180,
            "bram_tiles": 3.5,
        },
        "patterns": [
            {"selected_tiles": 60},
            {
                "selected_tiles": 20,
                "cycle_reduction_percent": 50.0,
                "axis_byte_reduction_percent": 60.0,
            },
            {
                "selected_tiles": 40,
                "cycle_reduction_percent": 25.0,
                "axis_byte_reduction_percent": 30.0,
            },
        ],
    }


# Keep quality fixtures scene-aware so averaging cannot hide a scene failure.
def _quality(*, selector_passed: bool = False) -> dict[str, object]:
    """Return a frozen quality result with one 0.143 dB scene regression."""

    return {
        "gates": {
            "overall_passed": selector_passed,
            "quality_within_tolerance_each_scene": selector_passed,
        },
        "methods": {
            "always_neural": {"scene_equal_psnr": 30.12},
            "semantic_sparse": {"scene_equal_psnr": 30.27},
        },
        "quality_by_scene": {
            "scene_a": {"drop_vs_always_neural_db": 0.02},
            "scene_b": {"drop_vs_always_neural_db": 0.143},
        },
    }


# Accept the hardware while keeping the independently failed policy rejected.
def test_accepts_architecture_without_accepting_selector() -> None:
    """Separate bit-exact architecture scaling from selector generalization."""

    result = analyze(
        _physical(), _quality(), _contract(), observed_source_sha256="abc123"
    )

    assert result["decision"] == "accept_independent_architecture_scaling_not_selector"
    assert result["architecture_accepted"] is True
    assert result["selector_accepted"] is False
    assert result["hardware_summary"]["median_cycle_reduction_percent"] == 37.5  # type: ignore[index]
    assert result["quality_summary"]["maximum_scene_psnr_drop_db"] == pytest.approx(0.143)  # type: ignore[index]


# Reject altered evidence before any performance result can be published.
def test_rejects_source_hash_mismatch() -> None:
    """Refuse to join a worklist source not named by the frozen contract."""

    with pytest.raises(ValueError, match="hash"):
        analyze(
            _physical(),
            _quality(),
            _contract(),
            observed_source_sha256="different",
        )


# Confirm per-scene loss uses the worst scene rather than the favorable mean.
def test_maximum_scene_psnr_drop_is_scene_worst_case() -> None:
    """Return the largest positive scene regression."""

    assert maximum_scene_psnr_drop(_quality()) == pytest.approx(0.143)


def test_observation_hash_canonicalizes_only_crlf(tmp_path) -> None:
    """Accept Git EOL materialization without weakening payload identity."""

    lf = tmp_path / "lf.jsonl"
    crlf = tmp_path / "crlf.jsonl"
    changed = tmp_path / "changed.jsonl"
    bare_cr = tmp_path / "bare-cr.jsonl"
    lf.write_bytes(b'{"mask":1}\n{"mask":2}\n')
    crlf.write_bytes(b'{"mask":1}\r\n{"mask":2}\r\n')
    changed.write_bytes(b'{"mask":1}\n{"mask":3}\n')
    bare_cr.write_bytes(b'{"mask":1}\r{"mask":2}\n')

    expected = sha256_jsonl_canonical_lf(lf)
    assert sha256_jsonl_canonical_lf(crlf) == expected
    assert sha256_jsonl_canonical_lf(changed) != expected
    with pytest.raises(ValueError, match="bare CR"):
        sha256_jsonl_canonical_lf(bare_cr)
