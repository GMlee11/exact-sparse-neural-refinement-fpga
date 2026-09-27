import copy
import json
from pathlib import Path
import pytest
from src.report.paper2_roi_publication import build, render

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def summary():
    return json.loads((ROOT / "results/paper2_conventional_comparison_v1/P003/summary.json").read_text())


def test_complete_table_and_regressions(summary):
    result = build(summary)
    assert result["merged_reduction_vs_full_percent"] == pytest.approx(16.293653, abs=1e-5)
    assert len(result["merged_vs_outer_regressions"]) == 5
    assert len(result["all_cells"]) == 17
    tex = render(result)
    assert "309.941" in tex and "96.157" in tex
    assert "not complete rendering" in tex


@pytest.mark.parametrize("field,value", [("qualification_pass", False), ("records", 305), ("byte_archives", 50)])
def test_reject_incomplete_evidence(summary, field, value):
    summary[field] = value
    with pytest.raises(AssertionError):
        build(summary)


def test_reject_changed_aggregate(summary):
    summary["primary_sparse_equal_mask_mean_ms"]["full_raster"] += 1
    with pytest.raises(AssertionError):
        build(summary)


def test_reject_missing_control(summary):
    summary["all_cells"].pop(0)
    with pytest.raises(AssertionError):
        build(summary)
