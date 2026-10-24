"""Independent descriptive aggregation of the frozen A B B A campaign.

Consumes numerically qualified per-launch analyses, not raw/unchecked timings.
Repeated requests within a launch are not independent physical sessions. No
confidence interval or unseen-workload/general-architecture claim is produced.
"""
import argparse
import hashlib
import json
from pathlib import Path
from statistics import mean

MODES = ("full_raster", "outer_bbox", "merged_rectangles")
PHASES = ("planning_ms", "packing_ms", "dma_and_engine_ms",
          "invalidate_and_scatter_ms", "other_service_ms")
ORDER = ("reference", "candidate", "candidate", "reference")


def summarize(reports):
    if len(reports) != 4:
        raise ValueError("Four qualified launches in fixed A B B A order required")
    reference_cells = None
    reference_traffic = {}
    per_launch = []
    all_cells = []
    for index, report in enumerate(reports):
        if not report["pass"] or not report["mode_and_bank_balance_verified"]:
            raise ValueError("Unqualified launch")
        if report["fabric_hz"] != 50_000_000 or not report["cache_enabled"]:
            raise ValueError("Clock/cache configuration mismatch")
        rows = report["records"]
        if len(rows) != 306 or report["numerical_byte_archives_checked"] != 51:
            raise ValueError("Incomplete frozen launch")
        tiles = {c["case"]: c["selected_tiles"] for c in report["comparisons"]}
        if len(tiles) != 17 or sum(0 < n < 60 for n in tiles.values()) != 15:
            raise ValueError("Unexpected workload")
        if reference_cells is None:
            reference_cells = tiles
        if tiles != reference_cells:
            raise ValueError("Mask identities/selected counts differ")
        cells = {}
        for case, selected in tiles.items():
            for mode in MODES:
                selected_rows = [r for r in rows if r["case"] == case and r["mode"] == mode]
                if len(selected_rows) != 6 or sorted(r["repeat"] for r in selected_rows) != list(range(6)):
                    raise ValueError("Missing or duplicate repetitions")
                if any(r["rc"] or not r["numerical_checksum_pass"] for r in selected_rows):
                    raise ValueError("Numerical/terminal failure")
                archived = [r for r in selected_rows if r["repeat"] == 0]
                if len(archived) != 1 or archived[0]["byte_archive_pass"] is not True:
                    raise ValueError("Missing byte verification")
                traffic = {(r["regions"], r["input_words"], r["output_words"]) for r in selected_rows}
                if len(traffic) != 1:
                    raise ValueError("Traffic changes within a cell")
                key = (case, mode)
                traffic = next(iter(traffic))
                if index == 0:
                    reference_traffic[key] = traffic
                if traffic != reference_traffic[key]:
                    raise ValueError("Comparison changes work/traffic")
                cells[key] = {"service_ms": mean(r["service_ms"] for r in selected_rows),
                              "phase_means_ms": {p: mean(r[p] for r in selected_rows) for p in PHASES},
                              "service_min_ms": min(r["service_ms"] for r in selected_rows),
                              "service_max_ms": max(r["service_ms"] for r in selected_rows)}
        per_launch.append({"position": index + 1, "implementation": ORDER[index],
                           "sparse_equal_mask_mean_ms": {
                               mode: mean(cells[case, mode]["service_ms"] for case, n in tiles.items() if 0 < n < 60)
                               for mode in MODES}})
        all_cells.append(cells)
    comparisons = []
    for case, selected in reference_cells.items():
        for mode in MODES:
            ref = mean(all_cells[i][case, mode]["service_ms"] for i in (0, 3))
            candidate = mean(all_cells[i][case, mode]["service_ms"] for i in (1, 2))
            comparisons.append({"case": case, "selected_tiles": selected, "mode": mode,
                                "reference_ms": ref, "candidate_ms": candidate,
                                "candidate_change_percent": 100 * (candidate / ref - 1),
                                "regression": candidate > ref,
                                "launch_cells": [c[case, mode] for c in all_cells],
                                "regions_input_output_words": reference_traffic[case, mode]})
    overall = {}
    for mode in MODES:
        subset = [c for c in comparisons if c["mode"] == mode and 0 < c["selected_tiles"] < 60]
        ref, candidate = (mean(c[k] for c in subset) for k in ("reference_ms", "candidate_ms"))
        overall[mode] = {"reference_ms": ref, "candidate_ms": candidate,
                         "candidate_change_percent": 100 * (candidate / ref - 1),
                         "regressed_sparse_masks": sum(c["regression"] for c in subset),
                         "max_mask_regression_percent": max(0, max(c["candidate_change_percent"] for c in subset))}
    return {"complete_qualified_ABBA": True, "record_count": 1224, "byte_archives": 204,
            "not_held_out_workloads": True, "independent_launches_per_implementation": 2,
            "primary_timing_mode": "merged_rectangles", "sparse_equal_mask_means": overall,
            "per_launch": per_launch, "all_cells_including_controls": comparisons,
            "interpretation": "Descriptive integrated-implementation comparison, not statistical equivalence or isolated primitive causality"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("analyses", nargs=4, type=Path, help="Fixed chronological reference/candidate/candidate/reference analyses")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = summarize([json.loads(path.read_text()) for path in args.analyses])
    result["inputs"] = [{"path": str(p.resolve()), "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
                        for p in args.analyses]
    result["analysis_source_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    with args.output.open("x", encoding="utf-8") as output:
        json.dump(result, output, indent=2)
        output.write("\n")
    print(json.dumps(result["sparse_equal_mask_means"], indent=2))


if __name__ == "__main__":
    main()
