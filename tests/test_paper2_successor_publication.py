"""Publication regression checks; physical evidence remains immutable."""
from pathlib import Path
from src.hardware.verify_paper2_successor_diagnostics import verify

ROOT = Path(__file__).resolve().parents[1]


def test_diagnostic_evidence_replays_without_new_measurement():
    result = verify()
    assert result["diagnostic_rows"] == 12
    assert not result["confirmatory_speedup_claim"]
    assert round(result["medians"][0]["legacy_transfer_drain_ms"], 3) == 239.739


def test_manuscript_retains_scope_and_closest_alternative():
    text = " ".join((ROOT / "docs/paper/sparse_refinement_accelerator.tex").read_text().split())
    assert "ren2018sbnet" in text and "li2023sige" in text
    assert "precision-scalable end-to-end" not in text
    assert "adds no measurable same-clock" not in text
    assert "same-clock end-to-end service time" not in text
    assert "software-managed completion" in text
    assert "maximum-clock effect remains untested" in text
    assert "0.01049\\%" in text
    assert "261.948, 28.260, and 46.389" in text
