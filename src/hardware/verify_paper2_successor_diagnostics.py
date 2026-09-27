"""Read-only replay of compact successor evidence; never contacts hardware."""
from __future__ import annotations

import hashlib
import json
import re
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = Path("results/paper2_service_successor_v1")


def verify(root: Path = ROOT) -> dict:
    simulation = root / BASE / "engineering_evidence_v1"
    log_bytes = (simulation / "E010_stage2.log").read_bytes()
    assert hashlib.sha256(log_bytes).hexdigest() == "0646daba50e685005b7ee8cd84e52012f5ac30f216938f5244051b38bf4ad13b"
    log = log_bytes.decode("utf-8")
    cases = []
    for index, expected in enumerate(((2456290, 2456290), (2688760, 2688478))):
        case = json.loads((simulation / f"E010_case{index}_terminal.json").read_text())
        assert (case["baseline_cycles"], case["candidate_cycles"]) == expected
        assert case["engineering_only"] is True
        assert case["full_output_words_per_core"] == 921600
        assert case["byte_coordinate_order_and_work_counters_pass"] is True
        assert f"PAPER2_INTEGRATED_MASK_PASS mask={index} baseline_cycles={expected[0]} candidate_cycles={expected[1]}" in log
        cases.append(case)
    assert "PAPER2_INTEGRATED_PASS 2 FULL-SIZE development masks" in log
    raw = (root / BASE / "host_diagnostic_H002/uart.raw").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == "cbc76ee1fd520ef38dea5e30d51e7dba12679bb79137ff659121d656b943819e"
    lines = raw.decode("ascii").splitlines()

    def fields(line: str) -> dict[str, int]:
        return {key: int(value, 16 if value.startswith("0x") else 10)
                for key, value in re.findall(r"(\w+)=(0x[0-9A-Fa-f]+|\d+)", line)}

    header = fields(lines[0])
    assert header["synthetic_not_renderer"] == 1
    assert header["timer_hz"] == 333333343
    rows = [fields(line) for line in lines if line.startswith("P2_HOST_ROW ")]
    assert [(r["pattern"], r["repeat"]) for r in rows] == [(p, i) for p in (0, 4, 1) for i in range(4)]
    assert lines[-1] == "P2_HOST_DIAGNOSTIC_TERMINAL rows=12 failure=0 no_confirmatory_claim=1"
    medians = []
    for pattern, checksum, words, cycles in ((0, 0x9897196f, 921600, 14102071), (4, 0x398d4cc8, 15360, 1627560), (1, 0x0ad32674, 76800, 2558463)):
        selected = [r for r in rows if r["pattern"] == pattern]
        for row in selected:
            assert row["result"] == row["rc"] == 0
            assert row["warmup"] == int(row["repeat"] == 0)
            assert row["mm2s"] == row["s2mm"] == 0x1002
            assert (row["checksum"], row["words"], row["core_cycles"]) == (checksum, words, cycles)
        measured = [r for r in selected if not r["warmup"]]
        medians.append({"pattern": pattern, **{
            key.replace("_ticks", "_ms"): statistics.median(r[key] for r in measured) * 1000 / header["timer_hz"]
            for key in ("legacy_transfer_drain_ticks", "run_inclusive_ticks", "clear_ticks", "output_checksum_ticks")}})
    return {"status": "PASS", "simulation": cases, "diagnostic_rows": len(rows), "medians": medians,
            "confirmatory_speedup_claim": False, "renderer_latency_measured": False}


if __name__ == "__main__":
    print(json.dumps(verify(), indent=2))
