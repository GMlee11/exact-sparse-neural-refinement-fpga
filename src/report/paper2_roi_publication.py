"""Generate the complete P003 publication table from verified summary records."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parents[2]
MODES = ("full_raster", "outer_bbox", "merged_rectangles")


def build(summary: dict) -> dict:
    assert summary["qualification_pass"] and summary["records"] == 306
    assert summary["byte_archives"] == 51
    cells = summary["all_cells"]
    assert len(cells) == 17 and len({c["case"] for c in cells}) == 17
    sparse = [c for c in cells if 0 < c["selected_tiles"] < 60]
    assert len(sparse) == 15
    means = {m: statistics.mean(c["modes"][m]["mean_ms"] for c in sparse) for m in MODES}
    for m in MODES:
        assert abs(means[m] - summary["primary_sparse_equal_mask_mean_ms"][m]) < 1e-9
    return {
        "run": "P003", "records": 306, "raw_byte_archives": 51,
        "sparse_equal_mask_mean_ms": means,
        "merged_reduction_vs_full_percent": 100 * (1 - means[MODES[2]] / means[MODES[0]]),
        "merged_reduction_vs_outer_percent": 100 * (1 - means[MODES[2]] / means[MODES[1]]),
        "merged_vs_outer_regressions": [c["case"] for c in sparse if c["modes"][MODES[2]]["mean_ms"] > c["modes"][MODES[1]]["mean_ms"]],
        "all_cells": cells,
        "scope": "Six repetitions per cell in one board session; pre-existing masks, not unseen generalization."
    }


def render(report: dict) -> str:
    lines = [r"\begin{table}[!htbp]", r"\centering\small",
             r"\caption{Same-image 50-MHz request-to-selected-residual-publication time (ms),",
             r"six repetitions per cell, balanced across mode order and two private banks.",
             r"The primary mean weights the fifteen sparse masks equally; empty and dense",
             r"controls remain separate. This is not complete rendering time.}",
             r"\label{tab:roi-service}",
             r"\begin{tabular}{@{}lrrrr@{}}", r"\toprule",
             r"Request & Tiles & Full raster & Outer box & Merged \\", r"\midrule"]
    for c in report["all_cells"]:
        family = c["case"]
        label = ("Empty" if c["selected_tiles"] == 0 else "Dense" if c["selected_tiles"] == 60
                 else "Clustered" if family.startswith("clustered")
                 else "Scattered" if family.startswith("scattered")
                 else "Checkerboard" if family.startswith("adversarial")
                 else "Prefix" if family.startswith("deadline") else "Motion band")
        values = " & ".join(f'{c["modes"][m]["mean_ms"]:.3f}' for m in MODES)
        lines.append(f'{label} & {c["selected_tiles"]} & {values} ' + r"\\")
    values = " & ".join(f'{report["sparse_equal_mask_mean_ms"][m]:.3f}' for m in MODES)
    lines += [r"\midrule", "Sparse mean & -- & " + values + r" \\",
              r"\bottomrule", r"\end{tabular}", r"\end{table}", ""]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "results/paper2_conventional_comparison_v1/P003/summary.json")
    parser.add_argument("--json-output", type=Path, default=ROOT / "results/tables/paper2_roi_publication_v1.json")
    parser.add_argument("--tex-output", type=Path, default=ROOT / "docs/paper/generated/paper2_roi_publication_v1.tex")
    args = parser.parse_args()
    raw = args.source.read_bytes()
    report = build(json.loads(raw))
    report["summary_sha256"] = hashlib.sha256(raw).hexdigest()
    for path, text in ((args.json_output, json.dumps(report, indent=2) + "\n"), (args.tex_output, render(report))):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
