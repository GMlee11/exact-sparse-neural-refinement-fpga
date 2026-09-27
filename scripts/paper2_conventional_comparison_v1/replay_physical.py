"""Read-only, location-independent P003 raw-byte/timing reproduction.

Keep repository-relative source/weights layout. Absolute historical machine
paths in the launch record are provenance only; this command does not use them.
"""
import argparse,hashlib,json,statistics,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from portable_oracle import golden
from src.experiments.paper2_conventional_comparison_v1.comparison import WEIGHTS,rectangles,union_mask
MODES=("full_raster","outer_bbox","merged_rectangles")
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def fnv(words):
 value=0x811c9dc5
 for word in words:value=((value^int(word))*16777619)&0xffffffff
 return value
def ticks(row,k):return int(row[k])+(int(row[k+1])<<32)
def main():
 p=argparse.ArgumentParser();p.add_argument("--run",type=Path,default=ROOT/"results/paper2_conventional_comparison_v1/P003");p.add_argument("--cases",type=Path,default=ROOT/"results/paper2_conventional_comparison_v1/F006/cases.json");a=p.parse_args()
 manifest=json.loads((a.run/"launch_manifest.json").read_text());saved=json.loads((a.run/"analysis.json").read_text());cases=json.loads(a.cases.read_text())
 assert sha(WEIGHTS)==manifest["oracle_weights"]["sha256"] and sha(a.cases)==manifest["case_manifest_pin"]["sha256"]
 for name,digest in saved["input_hashes"].items():assert sha(a.run/name)==digest,f"Evidence changed: {name}"
 data=np.fromfile(a.run/"records.bin",dtype="<u4");archive=np.fromfile(a.run/"archive.bin",dtype="<u4")
 assert data[0]==0x524f4931 and data[1]==1 and data[2]==306 and data[5]==17 and data[6]==6 and data[8]==1
 assert len(data)==32+306*26 and len(archive)==int(data[3]);freq=int(data[4])
 assert abs(freq-float(manifest["hwh_cpu_mhz"])*1e6/2)<=1
 oracle=golden();expected=[]
 for case in cases:
  mask=union_mask(rectangles(case["selected_tile_indices"]),0,360,640).repeat(2,0).repeat(2,1)
  words=oracle[mask].reshape(-1);expected.append((words,fnv(words)))
 cells={(i,m):[] for i in range(17) for m in range(3)};banks={(i,m):[] for i in range(17) for m in range(3)};archives=0;next_offset=0
 for i,row in enumerate(data[32:].reshape(-1,26)):
  case=(i//3)%17;rep=i//51;mode=(i%3+rep+case)%3;frame=52+i
  assert tuple(map(int,row[:3]))==(case,mode,rep) and row[3]==0 and row[22]==frame
  words,checksum=expected[case];assert row[6]==row[21]==len(words) and row[19]==checksum
  assert row[7]&4 and not row[7]&17 and row[23]==row[4]
  assert row[24] in (0,1) and row[25]==(frame<<1)|int(row[24])
  assert ticks(row,8)>=sum(ticks(row,k) for k in (10,12,14,16))
  banks[case,mode].append(int(row[24]));cells[case,mode].append(ticks(row,8)*1000/freq)
  if rep==0:
   offset=int(row[20]);assert offset==next_offset
   assert np.array_equal(archive[offset:offset+len(words)],words)
   next_offset+=len(words);archives+=1
 assert next_offset==len(archive) and archives==51 and int(data[7])==int(data[-1])
 assert all(v.count(0)==v.count(1)==3 for v in banks.values())
 sparse=[i for i,c in enumerate(cases) if 0<len(c["selected_tile_indices"])<60];assert len(sparse)==15
 means={MODES[m]:statistics.mean(statistics.mean(cells[i,m]) for i in sparse) for m in range(3)}
 for row in saved["records"]:
  key=(row["case_index"],MODES.index(row["mode"]));assert abs(cells[key][row["repeat"]]-row["service_ms"])<1e-9
 regressions=[{"case":cases[i]["name"],"merged_over_outer":statistics.mean(cells[i,2])/statistics.mean(cells[i,1])} for i in sparse if statistics.mean(cells[i,2])>statistics.mean(cells[i,1])]
 print(json.dumps({"pass":True,"records":306,"raw_byte_archives":archives,"archived_words":len(archive),"mode_bank_balance_verified":True,"sparse_equal_mask_means_ms":means,"full_over_merged":means[MODES[0]]/means[MODES[2]],"outer_over_merged":means[MODES[1]]/means[MODES[2]],"all_sparse_merged_vs_outer_regressions":regressions},indent=2))
if __name__=="__main__":main()
