"""Artifact-only replay: no hardware, manuscript, absolute source tree or torch."""
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]

def replay(name):
 result=subprocess.run([sys.executable,"-B",str(ROOT/"scripts/paper2_conventional_comparison_v1"/name)],cwd=ROOT,capture_output=True,text=True,timeout=90)
 assert result.returncode==0,result.stdout+result.stderr
 return json.loads(result.stdout)

def test_confirmation_raw_bytes_and_complete_schedule():
 result=replay("replay_physical.py")
 assert result["pass"] and result["records"]==306
 assert result["raw_byte_archives"]==51 and result["archived_words"]==14929920
 assert result["mode_bank_balance_verified"]
 assert len(result["all_sparse_merged_vs_outer_regressions"])==5

def test_physical_fault_and_reuse_public_bytes():
 result=replay("replay_safety.py")
 assert result["pass"] and len(result["checks"])==11
 assert result["archived_words"]==1013760 and not result["performance_measurement"]
 assert all(row["byte_oracle_pass"] for row in result["checks"])
 assert result["checks"][3]["guard_elapsed_cycles"]==50000001
 assert all(result["checks"][i]["distinct_private_candidate_observed"] for i in (1,3,7))
