"""Tests for reviewer-facing Paper 2 physical evidence traceability."""

from __future__ import annotations

import re

import pytest

from src.hardware.audit_sparse_accelerator_evidence import (
    build_report,
    render_markdown,
    sha256_file,
)


# Every paper headline must carry an explicit evidence class and source path so
# physical board claims cannot drift into projections or provisional estimates.
def test_tracked_paper2_claims_are_traceable() -> None:
    """Require every indexed claim to identify its analyzer and JSON fields."""

    report = build_report()
    assert report["decision"] == "all_claims_traceable_with_evidence_class_boundaries"
    boundary = report["physical_output_verification"]
    assert boundary["full_physical_output_byte_streams_archived"] is False
    assert boundary["bytewise_physical_replay_claimed"] is False
    assert boundary["software_rtl_selected_bytes_compared_directly"] is True
    assert all(report["gates"].values())
    assert len(report["claims"]) >= 10
    for claim in report["claims"]:
        assert claim["evidence_class"]
        assert claim["analyzer"].startswith("src/")
        assert claim["result_path"].endswith(".json")
        assert claim["json_fields"]
    operating = {
        claim["claim_id"]: claim for claim in report["claims"]
    }["persistent_vs_independent"]["value"]["operating_points"]
    assert operating["independent_cycles"] == 9_857_730
    assert operating["independent_clock_mhz"] == 100.0
    assert operating["independent_cycle_derived_compute_ms"] == pytest.approx(98.57730)
    assert operating["persistent_cycles"] == 4_922_897
    assert operating["persistent_clock_mhz"] == 50.0
    assert operating["persistent_cycle_derived_compute_ms"] == pytest.approx(98.45794)
    assert operating["cycle_derived_elapsed_delta_ms"] == pytest.approx(-0.11936)
    assert operating["wall_time_speedup_claimed"] is False
    markdown = render_markdown(report)
    assert "not an observed wall-time speedup" in markdown


# Physical source hashes and PASS markers are the last link between paper JSON
# and raw board output. Keep both mandatory for the primary Zybo captures.
def test_raw_physical_sources_are_hash_pinned() -> None:
    """Validate stable identities and PASS-marker coverage for raw evidence."""

    report = build_report()
    assert len(report["raw_evidence"]) >= 9
    for source in report["raw_evidence"]:
        assert re.fullmatch(r"[0-9a-f]{64}", source["sha256"])
        assert source["size_bytes"] > 0
        assert source["hash_normalization"] in {
            "crlf_to_lf_fail_closed",
            "raw_bytes",
        }
    b030_uart = next(
        source
        for source in report["raw_evidence"]
        if source["evidence_id"] == "b030_uart"
    )
    assert b030_uart["hash_normalization"] == "raw_bytes"
    assert b030_uart["sha256"] == (
        "ee6da3a171ea6f01f55732fbbe571f78ebe48aa156c39dfb994ab25006c724b8"
    )
    zybo_sources = [
        source
        for source in report["raw_evidence"]
        if source["evidence_id"].startswith("zybo_")
        and source["path"].endswith(".txt")
        and "timing" not in source["evidence_id"]
        and "utilization" not in source["evidence_id"]
    ]
    assert all(source["required_marker"] for source in zybo_sources)


def test_raw_evidence_hash_canonicalizes_only_crlf(tmp_path) -> None:
    """Keep Git EOL conversion portable without accepting payload drift."""

    lf = tmp_path / "lf.txt"
    crlf = tmp_path / "crlf.txt"
    changed = tmp_path / "changed.txt"
    bare_cr = tmp_path / "bare-cr.txt"
    lf.write_bytes(b"header\nPASS value=1\n")
    crlf.write_bytes(b"header\r\nPASS value=1\r\n")
    changed.write_bytes(b"header\nPASS value=2\n")
    bare_cr.write_bytes(b"header\rPASS value=1\n")

    assert sha256_file(lf) == sha256_file(crlf)
    assert sha256_file(changed) != sha256_file(lf)
    with pytest.raises(ValueError, match="bare CR"):
        sha256_file(bare_cr)


def test_independent_worklist_headline_and_route_identities_are_explicit() -> None:
    """Pin the median reductions and keep the two 58.824-MHz images separate."""

    report = build_report()
    claims = {claim["claim_id"]: claim for claim in report["claims"]}
    worklists = claims["independent_worklist_scaling"]
    images = claims["distinct_58p824_bitstream_identities"]["value"]

    assert worklists["value"]["median_cycle_reduction_percent"] == 57.413560036678305
    assert worklists["value"]["median_axis_byte_reduction_percent"] == 64.66927083333334
    assert worklists["value"]["cycles_vs_active_positions_r_squared"] == 0.9999042175199727
    assert worklists["value"]["selector_accepted"] is False
    assert images["controlled_mask_image"]["wns_ns"] == 1.363
    assert images["controlled_mask_image"]["slice_luts"] == 45048
    assert images["independent_worklist_image"]["wns_ns"] == 2.368
    assert images["independent_worklist_image"]["slice_luts"] == 45160


def test_sparse_worklist_service_rate_is_not_labeled_dense_fps() -> None:
    """Keep different work definitions and routed clocks visibly separate."""

    report = build_report()
    claims = {claim["claim_id"]: claim for claim in report["claims"]}
    rates = claims["worklist_service_rate_not_dense_fps"]["value"]

    assert rates["sparse_worklist_services_per_second"] == 9.739270285195044
    assert rates["sparse_worklist_definition"] == "canonical_17_tile_request"
    assert rates["sparse_worklist_clock_mhz"] == 50.0
    assert rates["dense_frames_per_second"] == 4.1712035970923775
    assert rates["dense_frame_definition"] == "dense_360p_to_720p_all_outputs"
    assert rates["dense_frame_clock_mhz"] == 58.824
    assert rates["ratio_claimed"] is False
    markdown = render_markdown(report)
    assert "9.739 services/s" in markdown
    assert "It is not dense-frame FPS" in markdown
    assert "no ratio between these rates" in markdown
    assert "Historical physical-output boundary" in markdown
    assert "those historical output streams are not archived" in markdown
    assert "This limitation does not describe P003/P005" in markdown


def test_b030_same_bitstream_control_is_checksum_length_verified_and_conditionally_scoped() -> None:
    """Bind the 480-row control without overstating its retained board evidence."""

    report = build_report()
    claims = {claim["claim_id"]: claim for claim in report["claims"]}
    b030 = claims["same_bitstream_closure_retention_b030"]["value"]

    assert report["gates"][
        "b030_same_bitstream_480_rows_checksum_length_verified"
    ] is True
    assert "b030_same_bitstream_480_rows_exact" not in report["gates"]
    assert b030["clock_mhz"] == 10.0
    assert b030["rows"] == 480
    assert b030["aggregate_cycle_raw"] == {
        "coverage": 0.0,
        "retention": 0.0,
        "interaction": 0.0,
    }
    assert b030["aggregate_cycle_fractional"] == b030["aggregate_cycle_raw"]
    assert b030["opportunity_masks"] == {
        "coverage": 4,
        "retention": 5,
        "total": 12,
    }
    conditional = b030["conditional_reductions_percent"]
    assert conditional["closure_0x810081"] == pytest.approx(65.38, abs=0.01)
    assert conditional["closure_0x000081"] == pytest.approx(59.64, abs=0.01)
    assert conditional["retention_0xFFFFFF"] == pytest.approx(8.16, abs=0.01)
    assert b030["publication_safety_rows_run"] == 0
    markdown = render_markdown(report)
    assert "opportunity-dependent same-build evidence" in markdown
    assert "not universal acceleration" in markdown
