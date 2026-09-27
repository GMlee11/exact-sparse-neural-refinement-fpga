"""Claim-safety tests for the readable sparse exactness argument."""

from pathlib import Path


PROOF = Path("docs/sparse_accelerator_exactness_proof.md")


def test_proof_preserves_radius_three_lr_closure() -> None:
    """Prevent the old radius-two decoder sentence from returning."""

    proof = " ".join(PROOF.read_text(encoding="utf-8").lower().split())

    assert "s0 = d1(s1) = d3(s3)" in proof
    assert "largest closure radius checked by the hardware decoder is three" in proof
    assert "largest hardware dilation radius is two" not in proof


def test_proof_limits_formality_and_states_both_invariants() -> None:
    """Require rigorous prose while retaining the non-formal evidence boundary."""

    proof = " ".join(PROOF.read_text(encoding="utf-8").lower().split())

    assert "selected-output closure lemma" in proof
    assert "structurally minimal" in proof
    assert "atomic publication invariant" in proof
    assert "do not constitute machine-checked formal verification" in proof
