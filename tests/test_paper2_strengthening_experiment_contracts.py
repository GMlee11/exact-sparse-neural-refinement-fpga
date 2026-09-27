from pathlib import Path

import yaml
import json


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_retrospective_applicability_uses_every_frozen_b030_mask() -> None:
    evidence = json.loads((REPO_ROOT / "results/analysis/sparse_distilled_same_bitstream_b030_execution_factorial.json").read_text())
    groups = {(True, False): [], (False, True): [], (True, True): [], (False, False): []}
    for row in evidence["per_mask"]:
        contrast = row["outcomes"]["cycles"]["raw"]
        groups[(contrast["coverage"] > 0, contrast["retention"] > 0)].append(row["mask_hex"].removeprefix("0x"))
    assert {key: len(value) for key, value in groups.items()} == {
        (True, False): 2, (False, True): 3, (True, True): 2, (False, False): 5,
    }
    text = (REPO_ROOT / "docs/paper/sparse_refinement_accelerator.tex").read_text()
    table = text.split(r"\label{tab:mechanism-applicability}")[1].split(r"\end{table}")[0]
    for masks in groups.values():
        assert all(r"\texttt{" + mask + "}" in table for mask in masks)
    assert "retrospective design guidance" in text
    assert "All 12 masks remain in the aggregate" in text


def _load_yaml(relative_path: str) -> dict:
    with (REPO_ROOT / relative_path).open("r", encoding="utf-8") as stream:
        return yaml.safe_load(stream)


def test_experiment_126_preregistration_locks_comparability_gates() -> None:
    contract = _load_yaml(
        "configs/sparse_same_clock_organization_control_v1.yaml"
    )

    assert contract["numeric_experiment_id"] == 126
    assert contract["status"] == "preregistered_not_run"
    assert contract["organizations"] == [
        "independent_halo_tiles",
        "rectangle_compaction",
        "global_closure_persistent",
    ]
    assert contract["frozen_inputs"]["sealed_images_used"] is False
    assert contract["frozen_inputs"]["selector_used_or_tuned"] is False

    controls = contract["matched_controls"]
    assert controls["fabric_clock_hz"] == 50_000_000
    assert controls["fabric_clock_tolerance_hz"] == 1_000
    assert [
        controls["conv1_output_lanes"],
        controls["conv2_output_lanes"],
        controls["conv3_output_lanes"],
    ] == [2, 12, 6]
    assert controls["dsp48_count"] == 180
    assert controls["private_atomic_commit_all_organizations"] is True
    assert controls["vivado_version"] == 2020.2
    assert controls["route_seed_sweeps_allowed"] is False

    resources = contract["resource_interpretation"]
    assert resources["compute_resources_exactly_matched"] is True
    assert resources["total_resources_expected_equal"] is False
    assert resources["inert_padding_allowed"] is False

    acceptance = contract["acceptance"]
    reduction_gates = {
        name: value
        for name, value in acceptance.items()
        if name.endswith("_reduction_percent")
    }
    assert len(reduction_gates) == 6
    assert set(reduction_gates.values()) == {25.0}
    assert acceptance["all_routes_meet_setup_and_hold"] is True
    assert acceptance[
        "all_outputs_checksums_counters_and_commit_outcomes_exact"
    ] is True
    assert acceptance["no_claim_if_any_correctness_or_control_gate_fails"] is True

    bindings = contract["artifact_bindings"]["organizations"]
    assert list(bindings) == contract["organizations"]
    assert len({bindings[name]["bitstream"] for name in bindings}) == 3
    assert len({bindings[name]["software_image"] for name in bindings}) == 3
    assert all(bindings[name]["bitstream"].endswith(".bit") for name in bindings)
    assert all(
        bindings[name]["software_image"].endswith("_app_ocm.elf")
        for name in bindings
    )

    analysis_plan = contract["analysis_plan"]
    assert analysis_plan["row_estimator"] == (
        "median_of_10_post_initialization_repetitions"
    )
    assert analysis_plan["organization_estimator"] == (
        "median_of_16_pattern_row_medians"
    )
    assert analysis_plan["require_all_48_rows"] is True
    assert analysis_plan["require_all_480_timed_iterations"] is True

    setup = contract["estimated_setup"]
    assert setup["expected_implementation_runs"] == 3
    assert setup["expected_board_images"] == 3
    assert setup["expected_board_replays"] == 48


def test_experiment_127_contract_preserves_software_only_boundary() -> None:
    contract = _load_yaml(
        "configs/finite_receptive_field_closure_validation_v1.yaml"
    )

    assert contract["numeric_experiment_id"] == 127
    assert contract["status"] == "completed_deterministic_software_contract"
    assert contract["evidence_boundary"]["rtl_simulation_claimed"] is False
    assert contract["evidence_boundary"]["formal_verification_claimed"] is False
    assert contract["evidence_boundary"]["routed_hardware_claimed"] is False
    assert contract["evidence_boundary"]["physical_validation_claimed"] is False
    assert contract["evidence_boundary"]["selector_tuned"] is False
