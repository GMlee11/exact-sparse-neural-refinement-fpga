"""Audit Paper 2 headline claims against physical evidence and claim limits.

The manuscript deliberately mixes physical board measurements, deterministic
trace replay, exact geometry accounting, and provisional tool estimates. This
module keeps those evidence classes separate and emits a reviewer-facing index
that maps each headline result to its raw capture, analyzer, and JSON fields.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_JSON = ROOT / "results/tables/paper2_physical_evidence_index.json"
DEFAULT_OUTPUT_MARKDOWN = ROOT / "artifact/paper2_arc/PHYSICAL_EVIDENCE_INDEX.md"


@dataclass(frozen=True)
class RawEvidence:
    """Describe one immutable physical source and its required PASS marker."""

    evidence_id: str
    path: str
    required_marker: str | None = None
    hash_mode: str = "crlf_to_lf_fail_closed"


# These are the raw sources behind every physical headline in the paper. Route
# reports have no UART PASS marker, so their existence and digest are audited
# while their parsed timing/resource gates remain in the canonical JSON.
RAW_EVIDENCE = (
    RawEvidence(
        "zybo_independent_rectangle",
        "fpga/docs/captures/sparse_refinement_accelerator_v1/physical_zybo_balanced_region.txt",
        "SPARSE_VARIABLE_BOARD_COMPLETE PASS",
    ),
    RawEvidence(
        "zybo_persistent",
        "fpga/docs/captures/sparse_refinement_accelerator_v1/hierarchical_mask_physical/physical_zybo_sparse_hierarchical.txt",
        "SPARSE_HIERARCHICAL_BOARD_COMPLETE correctness=bit_exact",
    ),
    RawEvidence(
        "zybo_controlled_masks_commit",
        "fpga/docs/captures/sparse_refinement_accelerator_v2/hierarchical_commit_suite_controlled_masks_physical/physical_zybo_sparse_hierarchical_commit_suite.txt",
        "SPARSE_HIERARCHICAL_COMMIT_SUITE_BOARD_COMPLETE correctness=bit_exact",
    ),
    RawEvidence(
        "zybo_controlled_masks_timing",
        "fpga/docs/captures/sparse_refinement_accelerator_v2/hierarchical_commit_suite_controlled_masks_physical/route/timing_summary.txt",
    ),
    RawEvidence(
        "zybo_controlled_masks_utilization",
        "fpga/docs/captures/sparse_refinement_accelerator_v2/hierarchical_commit_suite_controlled_masks_physical/route/utilization.txt",
    ),
    RawEvidence(
        "zybo_independent_worklists_commit",
        "fpga/docs/captures/sparse_refinement_accelerator_v2/hierarchical_commit_suite_independent_holdout_v1_physical/physical_zybo_sparse_hierarchical_commit_suite.txt",
        "SPARSE_HIERARCHICAL_COMMIT_SUITE_BOARD_COMPLETE correctness=bit_exact",
    ),
    RawEvidence(
        "zybo_independent_worklists_timing",
        "fpga/docs/captures/sparse_refinement_accelerator_v2/hierarchical_commit_suite_independent_holdout_v1_physical/route/timing_summary.txt",
    ),
    RawEvidence(
        "zybo_independent_worklists_utilization",
        "fpga/docs/captures/sparse_refinement_accelerator_v2/hierarchical_commit_suite_independent_holdout_v1_physical/route/utilization.txt",
    ),
    RawEvidence(
        "tang_sparse_control",
        "fpga/docs/captures/paper2/tang_sparse_commit_candidate_v1/physical_capture.json",
    ),
    RawEvidence(
        "b030_uart",
        "fpga/docs/captures/paper2/experiment134/E134-B030/physical/uart_b030_raw.bin",
        "E134_B029_EXECUTION_PASS rows=480",
        "raw_bytes",
    ),
    RawEvidence(
        "b030_timing",
        "fpga/docs/captures/paper2/experiment134/E134-B030/failure/reports/timing_summary_post_route.rpt",
    ),
    RawEvidence(
        "b030_utilization",
        "fpga/docs/captures/paper2/experiment134/E134-B030/failure/reports/utilization_post_route.rpt",
    ),
    RawEvidence(
        "b030_drc",
        "fpga/docs/captures/paper2/experiment134/E134-B030/failure/reports/drc_post_route.rpt",
    ),
)


# Git can materialize tracked text captures with CRLF, LF, or mixed line endings.
# The evidence index binds the platform-independent LF form while rejecting bare
# carriage returns; every non-line-ending byte remains covered.
def canonical_lf_bytes(path: Path) -> bytes:
    """Return one text evidence source with only CRLF normalized to LF."""

    raw = path.read_bytes()
    if b"\r" in raw.replace(b"\r\n", b""):
        raise ValueError(f"evidence source contains unsupported bare CR: {path}")
    return raw.replace(b"\r\n", b"\n")


def sha256_file(path: Path) -> str:
    """Return the lowercase SHA-256 digest of canonical LF text evidence."""

    return hashlib.sha256(canonical_lf_bytes(path)).hexdigest()


# Structured reports are parsed as JSON so a prose match cannot accidentally
# substitute for a validated counter or exactness gate.
def load_json(path: Path) -> Mapping[str, object]:
    """Read one JSON object with a path-specific validation error."""

    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected a JSON object: {path}")
    return value


# Verify that every physical source exists, contains its terminal marker when
# applicable, and receives a stable identity in the reviewer evidence index.
def audit_raw_evidence() -> list[dict[str, object]]:
    """Return hash-pinned physical sources after validating PASS markers."""

    rows = []
    for source in RAW_EVIDENCE:
        path = ROOT / source.path
        if not path.is_file():
            raise FileNotFoundError(f"missing physical evidence: {source.path}")
        if source.required_marker is not None:
            text = path.read_text(encoding="utf-8", errors="replace")
            if source.required_marker not in text:
                raise ValueError(
                    f"missing PASS marker in {source.path}: {source.required_marker}"
                )
        if source.hash_mode == "raw_bytes":
            canonical = path.read_bytes()
        elif source.hash_mode == "crlf_to_lf_fail_closed":
            canonical = canonical_lf_bytes(path)
        else:
            raise ValueError(f"unsupported evidence hash mode: {source.hash_mode}")
        rows.append(
            {
                "evidence_id": source.evidence_id,
                "path": source.path,
                "sha256": hashlib.sha256(canonical).hexdigest(),
                "size_bytes": len(canonical),
                "hash_normalization": source.hash_mode,
                "required_marker": source.required_marker,
            }
        )
    return rows


# Build the claim map from canonical machine-readable results. The explicit
# evidence class prevents simulated deadlines or power estimates from being
# presented beside board measurements without qualification.
def build_report() -> dict[str, object]:
    """Return all headline claims and the gates that authorize them."""

    paper = load_json(ROOT / "results/tables/sparse_accelerator_paper_v1.json")
    ablation = load_json(ROOT / "results/tables/sparse_architecture_ablation_v1.json")
    controlled = load_json(
        ROOT / "results/tables/sparse_hierarchical_commit_controlled_masks_physical.json"
    )
    deadline = load_json(ROOT / "results/tables/sparse_deadline_trace_analysis.json")
    independent = load_json(
        ROOT / "results/tables/sparse_independent_worklists_joined.json"
    )
    hierarchical = load_json(
        ROOT / "results/tables/sparse_refinement_hierarchical_physical.json"
    )
    independent_physical = load_json(
        ROOT / "results/tables/sparse_independent_worklists_physical.json"
    )
    tang = load_json(ROOT / "results/tables/tang_sparse_commit_candidate_v1.json")
    power = load_json(ROOT / "results/tables/sparse_postroute_power_estimate.json")
    b030 = load_json(
        ROOT / "results/preflight/experiment134/E134-B030_physical_result.json"
    )
    b030_analysis = load_json(
        ROOT
        / "results/analysis/sparse_distilled_same_bitstream_b030_execution_factorial.json"
    )

    organizations = {
        str(row["organization"]): row for row in paper["canonical_comparison"]
    }
    effects = ablation["mechanism_effects"]
    summary = controlled["summary"]
    independent_summary = independent["hardware_summary"]
    controlled_route = controlled["route"]
    independent_route = independent_physical["route"]
    commit = effects["private_atomic_commit"]
    headline = ablation["headline_operating_point_comparison"]
    b030_physical = b030["physical"]
    b030_cycle_aggregate = b030_analysis["aggregate"]["cycles"]
    b030_masks = {
        str(row["mask_hex"]).upper(): row for row in b030_analysis["per_mask"]
    }

    def b030_reduction(mask: str, baseline: str, comparison: str) -> float:
        cells = b030_masks[mask]["cells"]
        baseline_cycles = float(cells[baseline]["cycles"])
        comparison_cycles = float(cells[comparison]["cycles"])
        return 100.0 * (baseline_cycles - comparison_cycles) / baseline_cycles

    gates = {
        "canonical_physical_checksum_length_counter_records_match": all(
            bool(row["bit_exact"]) for row in organizations.values()
        ),
        "organization_operating_points_passed": bool(ablation["gates"]["all_pass"]),
        "controlled_masks_checksum_length_counters_match": bool(
            controlled["gates"]["all_masks_bit_and_counter_exact"]
        ),
        "physical_commit_outcomes_exact": bool(
            controlled["gates"]["all_commit_outcomes_exact"]
        ),
        "independent_worklists_checksum_length_counters_match": bool(
            independent["hardware_gates"]["all_patterns_bit_and_counter_exact"]
            and independent["hardware_gates"]["all_commit_outcomes_exact"]
        ),
        "independent_architecture_not_selector": bool(
            independent["architecture_accepted"]
            and not independent["selector_accepted"]
        ),
        "distinct_58p824_bitstreams_identified": bool(
            controlled_route["target_mhz"] == independent_route["target_mhz"]
            and (
                controlled_route["wns_ns"] != independent_route["wns_ns"]
                or controlled_route["slice_luts"]
                != independent_route["slice_luts"]
            )
        ),
        "worklist_service_rate_not_dense_fps": bool(
            hierarchical["physical_performance"]["service_fps"]
            != independent["hardware_summary"]["dense_service_fps"]
            and not hierarchical["evidence_boundary"]["absolute_realtime_claimed"]
        ),
        "deadline_replay_safe": all(bool(value) for value in deadline["gates"].values()),
        "tang_control_physically_passed": bool(tang["physical_pass"]),
        "physical_energy_not_claimed": not bool(
            power["claim_boundary"]["physical_energy_claimed"]
        ),
        "headline_counter_time_boundary_explicit": bool(
            headline["independent_cycles"] == 9_857_730
            and headline["independent_clock_mhz"] == 100.0
            and headline["persistent_cycles"] == 4_922_897
            and headline["persistent_clock_mhz"] == 50.0
            and headline["wall_time_speedup_claimed"] is False
            and headline["clock_normalized_acceleration_claimed"] is False
            and headline["causal_mechanism_isolated"] is False
        ),
        "b030_same_bitstream_480_rows_checksum_length_verified": bool(
            b030["disposition"] == "PHYSICAL_EXECUTION_PASS"
            and b030_physical["rows"] == 480
            and b030_physical["masks"] == 12
            and b030_physical["modes"] == 4
            and b030_physical["repetitions_per_cell"] == 10
            and b030_physical["checksum_mismatches"] == 0
            and b030_physical["nonzero_adapter_errors"] == 0
            and b030_physical["incomplete_status_rows"] == 0
            and b030_physical["word_count_invariant_failures"] == 0
        ),
        "b030_zero_aggregate_and_conditional_effects_disclosed": bool(
            all(value == 0.0 for value in b030_cycle_aggregate["raw"].values())
            and all(
                value == 0.0
                for value in b030_cycle_aggregate["fractional"].values()
            )
            and b030["analysis"]["opportunity_masks"]
            == {"coverage": 4, "retention": 5, "total": 12}
        ),
    }
    if not all(gates.values()):
        failed = ", ".join(name for name, passed in gates.items() if not passed)
        raise RuntimeError(f"Paper 2 evidence gates failed: {failed}")

    claims = [
        {
            "claim_id": "persistent_vs_independent",
            "evidence_class": "physical_zybo_checksum_length_counters",
            "value": {
                "cycle_reduction_percent": organizations["independent_halo_tiles"][
                    "proposed_cycle_reduction_percent"
                ],
                "axis_byte_reduction_percent": organizations[
                    "independent_halo_tiles"
                ]["proposed_axis_reduction_percent"],
                "operating_points": headline,
            },
            "raw_evidence_ids": ["zybo_independent_rectangle", "zybo_persistent"],
            "analyzer": "src/hardware/analyze_sparse_accelerator_paper.py",
            "result_path": "results/tables/sparse_accelerator_paper_v1.json",
            "json_fields": [
                "canonical_comparison[independent_halo_tiles]",
                "canonical_comparison[persistent_hierarchical_mask]",
                "headline_operating_point_comparison",
            ],
        },
        {
            "claim_id": "persistent_vs_rectangle",
            "evidence_class": "physical_zybo_checksum_length_counters",
            "value": {
                "cycle_reduction_percent": organizations["rectangle_compaction"][
                    "proposed_cycle_reduction_percent"
                ],
                "axis_byte_reduction_percent": organizations[
                    "rectangle_compaction"
                ]["proposed_axis_reduction_percent"],
            },
            "raw_evidence_ids": ["zybo_independent_rectangle", "zybo_persistent"],
            "analyzer": "src/hardware/analyze_sparse_architecture_ablation.py",
            "result_path": "results/tables/sparse_architecture_ablation_v1.json",
            "json_fields": [
                "mechanism_effects.global_closure_and_persistent_reuse"
            ],
        },
        {
            "claim_id": "same_bitstream_closure_retention_b030",
            "evidence_class": "physical_zybo_same_routed_build_checksum_length_counters",
            "value": {
                "clock_mhz": b030["build"]["clock_mhz"],
                "rows": b030_physical["rows"],
                "masks": b030_physical["masks"],
                "modes": b030_physical["modes"],
                "repetitions_per_cell": b030_physical["repetitions_per_cell"],
                "aggregate_cycle_raw": b030_cycle_aggregate["raw"],
                "aggregate_cycle_fractional": b030_cycle_aggregate["fractional"],
                "opportunity_masks": b030["analysis"]["opportunity_masks"],
                "conditional_reductions_percent": {
                    "closure_0x810081": b030_reduction("0X810081", "A", "B"),
                    "closure_0x000081": b030_reduction("0X000081", "A", "B"),
                    "retention_0xFFFFFF": b030_reduction("0XFFFFFF", "A", "C"),
                },
                "publication_safety_rows_run": b030_physical[
                    "publication_safety_rows_run"
                ],
            },
            "raw_evidence_ids": [
                "b030_uart",
                "b030_timing",
                "b030_utilization",
                "b030_drc",
            ],
            "analyzer": "src/hardware/audit_sparse_accelerator_evidence.py",
            "result_path": "results/analysis/sparse_distilled_same_bitstream_b030_execution_factorial.json",
            "json_fields": [
                "validation",
                "aggregate.cycles",
                "per_mask",
                "claim_firewall",
                "results/preflight/experiment134/E134-B030_physical_result.json",
            ],
        },
        {
            "claim_id": "exact_dependency_closure_geometry",
            "evidence_class": "exact_geometry_not_board_cycles",
            "value": effects["exact_union_geometry"],
            "raw_evidence_ids": [],
            "analyzer": "src/hardware/analyze_sparse_architecture_ablation.py",
            "result_path": "results/tables/sparse_architecture_ablation_v1.json",
            "json_fields": ["mechanism_effects.exact_union_geometry"],
        },
        {
            "claim_id": "controlled_mask_geometry",
            "evidence_class": "physical_zybo_checksum_length_counters",
            "value": {
                "exact_masks": len(controlled["patterns"]),
                "minimum_cycle_reduction_percent": summary[
                    "minimum_cycle_reduction_percent"
                ],
                "maximum_cycle_reduction_percent": summary[
                    "maximum_cycle_reduction_percent"
                ],
                "minimum_axis_byte_reduction_percent": summary[
                    "minimum_axis_byte_reduction_percent"
                ],
                "maximum_axis_byte_reduction_percent": summary[
                    "maximum_axis_byte_reduction_percent"
                ],
            },
            "raw_evidence_ids": [
                "zybo_controlled_masks_commit",
                "zybo_controlled_masks_timing",
                "zybo_controlled_masks_utilization",
            ],
            "analyzer": "src/hardware/analyze_sparse_hierarchical_commit_physical.py",
            "result_path": "results/tables/sparse_hierarchical_commit_controlled_masks_physical.json",
            "json_fields": ["patterns", "summary", "route", "gates"],
        },
        {
            "claim_id": "private_atomic_commit",
            "evidence_class": "physical_zybo_same_clock_counters",
            "value": {
                "service_overhead_percent": commit["service_overhead_percent"],
                "lut_delta": commit["logic_lut_delta"],
                "register_delta": commit["register_delta"],
                "dsp_delta": commit["dsp_delta"],
                "bram_delta": commit["bram_delta"],
                "all_four_outcomes_exact": commit["all_four_outcomes_exact"],
            },
            "raw_evidence_ids": ["zybo_controlled_masks_commit"],
            "analyzer": "src/hardware/analyze_sparse_architecture_ablation.py",
            "result_path": "results/tables/sparse_architecture_ablation_v1.json",
            "json_fields": ["mechanism_effects.private_atomic_commit"],
        },
        {
            "claim_id": "independent_worklist_scaling",
            "evidence_class": "physical_zybo_checksum_length_counters_architecture_only",
            "value": {
                "sparse_masks": independent_summary["sparse_pattern_count"],
                "median_cycle_reduction_percent": independent_summary[
                    "median_cycle_reduction_percent"
                ],
                "median_axis_byte_reduction_percent": independent_summary[
                    "median_axis_byte_reduction_percent"
                ],
                "cycles_vs_active_positions_r_squared": independent_summary[
                    "cycles_vs_active_positions_r_squared"
                ],
                "selector_accepted": independent["selector_accepted"],
            },
            "raw_evidence_ids": [
                "zybo_independent_worklists_commit",
                "zybo_independent_worklists_timing",
                "zybo_independent_worklists_utilization",
            ],
            "analyzer": "src/hardware/analyze_sparse_independent_worklists.py",
            "result_path": "results/tables/sparse_independent_worklists_joined.json",
            "json_fields": [
                "hardware_summary.median_cycle_reduction_percent",
                "hardware_summary.median_axis_byte_reduction_percent",
                "hardware_summary.cycles_vs_active_positions_r_squared",
                "quality_summary.selector_quality_gate_passed",
            ],
        },
        {
            "claim_id": "distinct_58p824_bitstream_identities",
            "evidence_class": "physical_zybo_route_reports",
            "value": {
                "controlled_mask_image": {
                    "purpose": "controlled_geometry_and_commit_suite",
                    "clock_mhz": controlled_route["target_mhz"],
                    "wns_ns": controlled_route["wns_ns"],
                    "slice_luts": controlled_route["slice_luts"],
                    "registers": controlled_route["registers"],
                    "bram_tiles": controlled_route["bram_tiles"],
                    "dsps": controlled_route["dsps"],
                },
                "independent_worklist_image": {
                    "purpose": "independent_temporal_worklists_and_stage_counters",
                    "clock_mhz": independent_route["target_mhz"],
                    "wns_ns": independent_route["wns_ns"],
                    "slice_luts": independent_route["slice_luts"],
                    "registers": independent_route["registers"],
                    "bram_tiles": independent_route["bram_tiles"],
                    "dsps": independent_route["dsps"],
                },
            },
            "raw_evidence_ids": [
                "zybo_controlled_masks_timing",
                "zybo_controlled_masks_utilization",
                "zybo_independent_worklists_timing",
                "zybo_independent_worklists_utilization",
            ],
            "analyzer": "src/hardware/audit_sparse_accelerator_evidence.py",
            "result_path": "results/tables/paper2_physical_evidence_index.json",
            "json_fields": [
                "claims[distinct_58p824_bitstream_identities].value"
            ],
        },
        {
            "claim_id": "worklist_service_rate_not_dense_fps",
            "evidence_class": "physical_zybo_distinct_work_definitions",
            "value": {
                "sparse_worklist_services_per_second": hierarchical[
                    "physical_performance"
                ]["service_fps"],
                "sparse_worklist_definition": "canonical_17_tile_request",
                "sparse_worklist_clock_mhz": (
                    hierarchical["physical_performance"]["fabric_clock_hz"]
                    / 1_000_000
                ),
                "dense_frames_per_second": independent_summary[
                    "dense_service_fps"
                ],
                "dense_frame_definition": "dense_360p_to_720p_all_outputs",
                "dense_frame_clock_mhz": independent_summary["clock_mhz"],
                "ratio_claimed": False,
            },
            "raw_evidence_ids": [
                "zybo_persistent",
                "zybo_independent_worklists_commit",
            ],
            "analyzer": "src/hardware/audit_sparse_accelerator_evidence.py",
            "result_path": "results/tables/paper2_physical_evidence_index.json",
            "json_fields": [
                "results/tables/sparse_refinement_hierarchical_physical.json:physical_performance.service_fps",
                "results/tables/sparse_independent_worklists_joined.json:hardware_summary.dense_service_fps",
            ],
        },
        {
            "claim_id": "deadline_trace_safety",
            "evidence_class": "deterministic_replay_from_physical_service_times",
            "value": {"traces": len(deadline["traces"]), "gates": deadline["gates"]},
            "raw_evidence_ids": ["zybo_controlled_masks_commit"],
            "analyzer": "src/hardware/analyze_sparse_deadline_traces.py",
            "result_path": "results/tables/sparse_deadline_trace_analysis.json",
            "json_fields": ["traces", "gates", "claim_boundary"],
        },
        {
            "claim_id": "tang_control_portability",
            "evidence_class": "physical_tang_resource_scaled_control",
            "value": {
                "mask_checks": tang["sparse_control_image"]["mask_checks"],
                "commit_outcome_checks": tang["sparse_control_image"][
                    "commit_outcome_checks"
                ],
                "physical_pass": tang["physical_pass"],
            },
            "raw_evidence_ids": ["tang_sparse_control"],
            "analyzer": "src/hardware/analyze_tang_sparse_commit_candidate.py",
            "result_path": "results/tables/tang_sparse_commit_candidate_v1.json",
            "json_fields": ["sparse_control_image", "physical_gates"],
        },
        {
            "claim_id": "power_boundary",
            "evidence_class": "provisional_post_route_estimate",
            "value": {
                "physical_energy_claimed": False,
                "full_datapath_saif_annotated": power["claim_boundary"][
                    "full_routed_datapath_saif_annotated"
                ],
            },
            "raw_evidence_ids": [],
            "analyzer": "src/hardware/analyze_sparse_postroute_power.py",
            "result_path": "results/tables/sparse_postroute_power_estimate.json",
            "json_fields": ["vivado_report", "claim_boundary"],
        },
    ]
    return {
        "schema_version": 2,
        "artifact": "paper2_physical_evidence_index_v1",
        "decision": "all_claims_traceable_with_evidence_class_boundaries",
        "physical_output_verification": {
            "method": "expected_checksum_selected_length_counters_and_terminal_conditions",
            "full_physical_output_byte_streams_archived": False,
            "bytewise_physical_replay_claimed": False,
            "software_rtl_selected_bytes_compared_directly": True,
        },
        "raw_evidence": audit_raw_evidence(),
        "claims": claims,
        "gates": gates,
    }


# Render paths and JSON fields in plain Markdown so reviewers can follow a
# headline value without reading the Python implementation first.
def render_markdown(report: Mapping[str, object]) -> str:
    """Return a reviewer-readable physical evidence map."""

    raw_by_id = {
        str(row["evidence_id"]): row for row in report["raw_evidence"]
    }
    lines = [
        "# Historical Paper 2 Physical Evidence Index",
        "",
        "This file maps the historical campaigns below to their evidence classes, raw captures, analyzers, and canonical JSON fields. The later P003/P005 same-image ROI confirmation and physical safety checks are separately indexed in artifact/paper2_arc/ROI_REPLAY.md. Physical, replayed, exact-geometry, and provisional estimates remain separate.",
        "",
        "**Historical physical-output boundary.** The board rows indexed below verify checksums, selected-output lengths, counters, and terminal conditions; those historical output streams are not archived for independent bytewise replay. This limitation does not describe P003/P005: their predeclared selected-output byte samples and independent numerical replay are included separately. Software and RTL tests also compare selected bytes directly against the dense integer reference.",
        "",
        "| Claim | Evidence class | Canonical result | Raw evidence |",
        "|---|---|---|---|",
    ]
    for claim in report["claims"]:
        raw_paths = [
            f"`{raw_by_id[evidence_id]['path']}`"
            for evidence_id in claim["raw_evidence_ids"]
        ]
        lines.append(
            f"| `{claim['claim_id']}` | `{claim['evidence_class']}` | "
            f"`{claim['result_path']}` | {'<br>'.join(raw_paths) if raw_paths else 'N/A'} |"
        )
    claims_by_id = {str(claim["claim_id"]): claim for claim in report["claims"]}
    operating = claims_by_id["persistent_vs_independent"]["value"][
        "operating_points"
    ]
    b030 = claims_by_id["same_bitstream_closure_retention_b030"]["value"]
    independent = claims_by_id["independent_worklist_scaling"]["value"]
    bitstreams = claims_by_id["distinct_58p824_bitstream_identities"]["value"]
    rate_boundary = claims_by_id["worklist_service_rate_not_dense_fps"]["value"]
    controlled_image = bitstreams["controlled_mask_image"]
    independent_image = bitstreams["independent_worklist_image"]
    lines.extend(
        [
            "",
            "## Canonical Coupled Operating Points",
            "",
            "| Organization | Cycles | Realized clock | Cycles/clock elapsed | LUT | FF | BRAM | DSP | AXI bytes |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
            f"| Independent | {operating['independent_cycles']:,} | "
            f"{operating['independent_clock_mhz']:.3f} MHz | "
            f"{operating['independent_cycle_derived_compute_ms']:.5f} ms | "
            f"{operating['independent_resources']['luts']:,} | "
            f"{operating['independent_resources']['registers']:,} | "
            f"{operating['independent_resources']['bram_tiles']:.1f} | "
            f"{operating['independent_resources']['dsps']} | "
            f"{operating['independent_axis_bytes']:,} |",
            f"| Persistent mask-only | {operating['persistent_cycles']:,} | "
            f"{operating['persistent_clock_mhz']:.3f} MHz | "
            f"{operating['persistent_cycle_derived_compute_ms']:.5f} ms | "
            f"{operating['persistent_resources']['luts']:,} | "
            f"{operating['persistent_resources']['registers']:,} | "
            f"{operating['persistent_resources']['bram_tiles']:.1f} | "
            f"{operating['persistent_resources']['dsps']} | "
            f"{operating['persistent_axis_bytes']:,} |",
            "",
            f"The persistent row has {operating['cycle_reduction_percent']:.2f}% "
            f"fewer cycles and {operating['axis_reduction_percent']:.2f}% fewer AXI "
            "bytes, but only 0.11936 ms lower cycle-derived elapsed time. Because "
            "clock, routing, resources, and memory organization differ, this is not "
            "an observed wall-time speedup, a clock-normalized comparison, an area "
            "advantage, or an isolated mechanism effect. The BRAM difference is a "
            "property of the coupled memory organizations.",
            "",
            "## B030 Same-Bitstream Controlled Companion",
            "",
            f"B030 runs {b030['masks']} masks across four policy cells with "
            f"{b030['repetitions_per_cell']} repetitions per cell on one routed "
            f"{b030['clock_mhz']:.0f}-MHz design. All {b030['rows']} rows pass "
            "checksum, length, counter, completion, and terminal invariants. "
            "The preregistered raw and normalized coverage, retention, and "
            "interaction medians are all zero because closure applies to "
            f"{b030['opportunity_masks']['coverage']}/{b030['masks']} masks and "
            f"retention to {b030['opportunity_masks']['retention']}/{b030['masks']}. "
            "Conditional closure reductions reach "
            f"{b030['conditional_reductions_percent']['closure_0x810081']:.2f}% "
            "and "
            f"{b030['conditional_reductions_percent']['closure_0x000081']:.2f}%; "
            "full-mask retention reaches "
            f"{b030['conditional_reductions_percent']['retention_0xFFFFFF']:.2f}%. "
            "This is opportunity-dependent same-build evidence, not universal "
            "acceleration or an area, energy, full-scale-throughput, external-AXI, "
            "or publication-safety claim.",
            "",
            "## Independent-Worklist Headline",
            "",
            "The independent architecture-only suite contains "
            f"{independent['sparse_masks']} sparse masks. Median physical "
            f"cycle and AXI-byte reductions are {independent['median_cycle_reduction_percent']:.2f}% "
            f"and {independent['median_axis_byte_reduction_percent']:.2f}%, "
            f"and cycles versus active positions have R-squared "
            f"{independent['cycles_vs_active_positions_r_squared']:.6f}. "
            "The supplying selector remains rejected; these values establish "
            "architecture scaling only.",
            "",
            "## Worklist Service Rate Is Not Dense FPS",
            "",
            f"The {rate_boundary['sparse_worklist_services_per_second']:.3f} services/s "
            f"number is the service rate of one fixed 17-tile sparse request on a "
            f"{rate_boundary['sparse_worklist_clock_mhz']:.3f}-MHz image. It is not "
            f"dense-frame FPS. Dense 360p-to-720p execution is "
            f"{rate_boundary['dense_frames_per_second']:.3f} FPS on a distinct "
            f"{rate_boundary['dense_frame_clock_mhz']:.3f}-MHz image. Because both "
            "the admitted work and routed clock differ, no ratio between these rates "
            "is an architecture claim.",
            "",
            "## Distinct 58.824-MHz Bitstreams",
            "",
            "The two physical suites use separate routed images and must not "
            "share one unlabeled resource row:",
            "",
            "| Image purpose | MHz | WNS (ns) | LUT | Registers | BRAM | DSP |",
            "|---|---:|---:|---:|---:|---:|---:|",
            f"| Controlled geometry and commit | {controlled_image['clock_mhz']:.3f} | "
            f"{controlled_image['wns_ns']:.3f} | {controlled_image['slice_luts']} | "
            f"{controlled_image['registers']} | {controlled_image['bram_tiles']} | "
            f"{controlled_image['dsps']} |",
            f"| Independent temporal worklists and stage counters | "
            f"{independent_image['clock_mhz']:.3f} | {independent_image['wns_ns']:.3f} | "
            f"{independent_image['slice_luts']} | {independent_image['registers']} | "
            f"{independent_image['bram_tiles']} | {independent_image['dsps']} |",
        ]
    )
    lines.extend(["", "## Raw Evidence Digests", ""])
    for row in report["raw_evidence"]:
        lines.append(
            f"- `{row['evidence_id']}`: `{row['sha256']}` ({row['size_bytes']} bytes)"
        )
    lines.extend(
        [
            "",
            "## Audit Gates",
            "",
            *[
                f"- `{name}`: **{'PASS' if passed else 'FAIL'}**"
                for name, passed in report["gates"].items()
            ],
            "",
        ]
    )
    return "\n".join(lines)


# Expose output paths so the audit can be used both in the full repository and
# from the anonymous reviewer package without changing hard-coded locations.
def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse deterministic evidence-index output locations."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument(
        "--output-markdown", type=Path, default=DEFAULT_OUTPUT_MARKDOWN
    )
    return parser.parse_args(argv)


# Write both machine-readable and reviewer-readable evidence maps only after
# every physical marker and evidence-boundary gate has passed.
def main(argv: Sequence[str] | None = None) -> int:
    """Generate the Paper 2 evidence index and fail on any claim drift."""

    args = parse_args(argv)
    report = build_report()
    for path in (args.output_json, args.output_markdown):
        path.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    args.output_markdown.write_text(
        render_markdown(report), encoding="utf-8", newline="\n"
    )
    print(
        "PAPER2_PHYSICAL_EVIDENCE_AUDIT_PASS "
        f"claims={len(report['claims'])} sources={len(report['raw_evidence'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
