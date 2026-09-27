"""Tests for Experiment 127's second-topology closure contract."""

from pathlib import Path

from src.hardware.validate_finite_receptive_field_closure import (
    analyze,
    radius_path_exercised,
    render_markdown,
)


CONFIG = Path("configs/finite_receptive_field_closure_validation_v1.yaml")


def test_second_topology_closure_contract_passes_all_preregistered_gates() -> None:
    """Require exact closure, output equality, and structural witnesses."""

    report = analyze(CONFIG)

    assert report["experiment_id"] == 127
    assert report["decision"] == "accept_second_topology_software_closure_contract"
    assert report["topology"]["maximum_path_radius"] == 4
    assert len(report["patterns"]) == 8
    assert all(report["gates"].values())

    displacement = report["support_path_displacement"]
    assert displacement["maximum_observed_displacement"] == 4
    assert displacement["required_attained_radius"] == 4
    assert displacement["attaining_patterns"]
    witness = displacement["exact_radius_witness"]
    assert witness["chebyshev_displacement"] == 4
    assert max(
        abs(witness["input_position"][0] - witness["output_position"][0]),
        abs(witness["input_position"][1] - witness["output_position"][1]),
    ) == 4
    assert witness["path_nodes"] == [
        "input",
        "conv_a",
        "conv_b_dilated",
        "residual_add",
        "output",
    ]
    for step, predecessor, successor in zip(
        witness["edges"], witness["path_nodes"], witness["path_nodes"][1:]
    ):
        assert step["predecessor"] == predecessor
        assert step["successor"] == successor
        assert step["predecessor_position"] == [
            step["successor_position"][0] + step["preimage_offset"][0],
            step["successor_position"][1] + step["preimage_offset"][1],
        ]

    markdown = render_markdown(report)
    assert "Exact Radius-Four Support-Path Witness" in markdown
    assert "Chebyshev displacement: `4`" in markdown


def test_cardinality_only_proxy_cannot_satisfy_radius_four_gate() -> None:
    """Reject large closures unless an exact coordinate witness attains four."""

    cardinality_only_row = {
        "required_positions": {"input": 99, "residual_add": 1},
        "maximum_input_to_output_chebyshev_displacement": 3,
        "maximum_displacement_witness": {
            "input_position": [4, 4],
            "output_position": [1, 1],
            "chebyshev_displacement": 3,
            "edges": [{"predecessor": "input", "successor": "output"}],
        },
    }
    assert not radius_path_exercised([cardinality_only_row], 4)

    inconsistent_witness_row = dict(cardinality_only_row)
    inconsistent_witness_row[
        "maximum_input_to_output_chebyshev_displacement"
    ] = 4
    assert not radius_path_exercised([inconsistent_witness_row], 4)


def test_second_topology_result_remains_synthetic_and_nonphysical() -> None:
    """Prevent a unit-test result from being presented as routed evidence."""

    report = analyze(CONFIG)
    boundary = report["evidence_boundary"]

    assert boundary["synthetic_integer_inputs_only"] is True
    assert boundary["sealed_or_renderer_images_used"] is False
    assert boundary["selector_tuned"] is False
    assert boundary["rtl_simulation_claimed"] is False
    assert boundary["routed_hardware_claimed"] is False
    assert boundary["physical_validation_claimed"] is False
    assert boundary["formal_verification_claimed"] is False
