"""Tests for the board-ready Tang sparse-control analysis."""

from __future__ import annotations

import hashlib

from src.hardware.analyze_tang_sparse_commit_candidate import (
    build_report,
    render_markdown,
)


# Minimal fixtures mirror nextpnr's nested utilization/fmax structure while
# keeping the test independent of a particular routed net name.
def fixture_route() -> dict[str, object]:
    """Return a passing one-clock Tang route fixture."""

    return {
        "fmax": {"core.clk": {"achieved": 141.824, "constraint": 27.0}},
        "utilization": {
            "LUT4": {"used": 463, "available": 20736},
            "DFF": {"used": 422, "available": 15552},
            "BSRAM": {"used": 0, "available": 46},
            "MULT9X9": {"used": 0, "available": 96},
            "MULT18X18": {"used": 0, "available": 48},
        },
    }


# Keep the four required simulator markers identical across the preflight and
# physical-acceptance tests so each test varies only the board evidence.
def fixture_simulation() -> str:
    """Return the complete Tang sparse-contract simulation transcript."""

    return "\n".join(
        [
            "PASS: Tang sparse contract mask_checks=576 outcomes=4",
            "PASS: Tang sparse-control top checks=576 outcomes=4",
            "PASS: Tang combined neural and sparse-commit contract checks=576",
            "TANG_SPARSE_COMMIT_SIM_PASS mask_checks=576 outcomes=4 neural_modes=4 packaging=two_image",
        ]
    )


# The physical record must identify the exact image and preserve the narrow
# control-only evidence boundary used by the two-image Tang package.
def fixture_control_capture(bitstream: bytes) -> dict[str, object]:
    """Return a hash-bound passing sparse-control board capture."""

    return {
        "experiment": "tang_sparse_commit_candidate_v1",
        "bitstream_sha256": hashlib.sha256(bitstream).hexdigest(),
        "programmer_reached_percent": 100,
        "status_register": "0x00006020",
        "led_pass": True,
        "led_fail": False,
        "sparse_mask_checks": 576,
        "commit_outcome_checks": 4,
        "full_frame_sparse_throughput_claimed": False,
    }


# A board-ready result requires all simulation markers, the prior neural
# physical PASS, and the complete sparse-control route gates.
def test_build_report_accepts_complete_two_image_preflight() -> None:
    """Accept the prepared bitstream while keeping physical control pending."""

    report = build_report(
        {"expected_mask_checks": 576},
        fixture_simulation(),
        fixture_route(),
        {"led_pass": True, "led_fail": False, "bitstream_sha256": "neural"},
        b"bitstream",
    )
    assert report["board_ready"] is True
    assert report["sparse_control_image"]["physical_pass"] is False
    assert report["sparse_control_image"]["bitstream_sha256"] == hashlib.sha256(
        b"bitstream"
    ).hexdigest()
    assert report["packaging"]["integrated_full_frame_sparse_throughput_claimed"] is False


# A physical claim is accepted only when the capture is tied to the routed
# bitstream and every autonomous board self-test field agrees.
def test_build_report_accepts_hash_bound_physical_control_capture() -> None:
    """Promote a complete two-image package to physical cross-vendor PASS."""

    bitstream = b"bitstream"
    report = build_report(
        {"expected_mask_checks": 576},
        fixture_simulation(),
        fixture_route(),
        {"led_pass": True, "led_fail": False, "bitstream_sha256": "neural"},
        bitstream,
        fixture_control_capture(bitstream),
    )
    assert report["decision"] == "physical_cross_vendor_sparse_control_pass"
    assert report["physical_pass"] is True
    assert report["sparse_control_image"]["physical_pass"] is True
    assert all(report["physical_gates"].values())


# A stale or unrelated board capture must not be allowed to certify a newly
# rebuilt bitstream, even when the LEDs and status fields otherwise look valid.
def test_build_report_rejects_mismatched_physical_bitstream_hash() -> None:
    """Keep physical status pending when the capture belongs to another image."""

    capture = fixture_control_capture(b"different")
    report = build_report(
        {"expected_mask_checks": 576},
        fixture_simulation(),
        fixture_route(),
        {"led_pass": True, "led_fail": False, "bitstream_sha256": "neural"},
        b"bitstream",
        capture,
    )
    assert report["board_ready"] is True
    assert report["physical_pass"] is False
    assert report["physical_gates"]["bitstream_hash_matches"] is False


# Missing prior physical arithmetic evidence means the two-image portability
# package is incomplete even when the new control bitstream routes.
def test_build_report_rejects_missing_neural_physical_pass() -> None:
    """Reject a control-only result presented as complete portability."""

    report = build_report(
        {"expected_mask_checks": 576},
        "TANG_SPARSE_COMMIT_SIM_PASS mask_checks=576 outcomes=4 neural_modes=4 packaging=two_image",
        fixture_route(),
        {"led_pass": False, "led_fail": True, "bitstream_sha256": "neural"},
        b"bitstream",
    )
    assert report["board_ready"] is False


# The handoff must state the physical blocker and avoid an integrated Tang
# throughput claim.
def test_markdown_keeps_two_image_scope_and_physical_stopping_point() -> None:
    """Render the exact next command and cross-vendor claim boundary."""

    report = build_report(
        {"expected_mask_checks": 576},
        fixture_simulation(),
        fixture_route(),
        {"led_pass": True, "led_fail": False, "bitstream_sha256": "neural"},
        b"bitstream",
    )
    summary = render_markdown(report)
    assert "two physical images" in summary
    assert "Connect the Tang Primer 20K" in summary
    assert "does not claim integrated Tang full-frame sparse throughput" in summary


# Once physical validation passes, the same summary should remove the stale
# hookup instructions while retaining the narrow two-image evidence scope.
def test_markdown_reports_physical_pass_without_stopping_point() -> None:
    """Render the accepted Tang physical state and its remaining limitations."""

    bitstream = b"bitstream"
    report = build_report(
        {"expected_mask_checks": 576},
        fixture_simulation(),
        fixture_route(),
        {"led_pass": True, "led_fail": False, "bitstream_sha256": "neural"},
        bitstream,
        fixture_control_capture(bitstream),
    )
    summary = render_markdown(report)
    assert "Physical sparse-control PASS | Yes" in summary
    assert "configuration status was `0x00006020`" in summary
    assert "Physical Stopping Point" not in summary
