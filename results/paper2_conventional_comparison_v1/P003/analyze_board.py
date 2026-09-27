"""Byte-check selected physical output archives and report every recorded cell."""
import argparse,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
import numpy as np
from run_traversal import golden
from src.experiments.paper2_conventional_comparison_v1.comparison import rectangles,union_mask
def fnv(values):
 h=0x811c9dc5
 for v in values:h=((h^int(v))*16777619)&0xffffffff
 return h
def u64(row,k):return int(row[k])+(int(row[k+1])<<32)
def main():
 p=argparse.ArgumentParser();p.add_argument("--run-id",required=True);a=p.parse_args()
 out=ROOT/"results/paper2_conventional_comparison_v1"/a.run_id
 if (out/"analysis.json").exists():raise FileExistsError("Analysis already exists")
 manifest=json.loads((out/"launch_manifest.json").read_text());cases=json.loads(Path(manifest["case_manifest"]).read_text())
 for name in ("oracle_weights","case_manifest_pin"):
  pin=manifest[name];assert hashlib.sha256(Path(pin["path"]).read_bytes()).hexdigest()==pin["sha256"],"Numerical input pin changed"
 data=np.fromfile(out/"records.bin",dtype="<u4");assert len(data)>=32 and data[0]==0x524f4931
 count=int(data[2]);assert len(data)==32+26*count
 archive=np.fromfile(out/"archive.bin",dtype="<u4") if (out/"archive.bin").exists() else np.array([],dtype="<u4")
 assert len(archive)==int(data[3]);freq=int(data[4]);assert freq>0 and int(data[5])==len(cases)
 # Zynq Cortex-A9 global timer ticks at half the configured CPU frequency.
 # Bind the firmware's conversion constant to the actual deployed XSA clock.
 expected_timer_hz=float(manifest["hwh_cpu_mhz"])*1e6/2
 assert abs(freq-expected_timer_hz)<=1,"Timer conversion disagrees with deployed XSA"
 oracle=golden();expected=[]
 for case in cases:
  selected=union_mask(rectangles(case["selected_tile_indices"]),0,360,640).repeat(2,0).repeat(2,1)
  words=oracle[selected].reshape(-1);expected.append((words,fnv(words)))
 rows=[];archive_checks=0;bad=[]
 for raw in data[32:].reshape(-1,26):
  case,mode,rep=map(int,raw[:3]);assert case<len(cases) and mode<3
  rc=int(raw[3]);rc=rc-(1<<32) if rc>0x7fffffff else rc
  words,reference_checksum=expected[case];length=int(raw[21]);assert length==len(words)
  service_ticks=u64(raw,8);stage_ticks=sum(u64(raw,k) for k in (10,12,14,16))
  assert service_ticks>=stage_ticks,"Stage timers exceed enclosing service timer"
  row={"case_index":case,"case":cases[case]["name"],"mode":("full_raster","outer_bbox","merged_rectangles")[mode],"repeat":rep,"warmup_failure":rep==99,"rc":rc,"regions":int(raw[4]),"input_words":int(raw[5]),"output_words":int(raw[6]),"status":int(raw[7]),"service_ms":u64(raw,8)*1000/freq,"planning_ms":u64(raw,10)*1000/freq,"packing_ms":u64(raw,12)*1000/freq,"dma_and_engine_ms":u64(raw,14)*1000/freq,"invalidate_and_scatter_ms":u64(raw,16)*1000/freq,"request_guard_elapsed_cycles":int(raw[18]),"checksum":int(raw[19]),"frame_id":int(raw[22]),"completed_regions":int(raw[23]),"archive_word_offset":int(raw[20]),"archive_word_length":length,"numerical_checksum_pass":int(raw[19])==reference_checksum,"byte_archive_pass":None}
  row["other_service_ms"]=row["service_ms"]-sum(row[k] for k in ("planning_ms","packing_ms","dma_and_engine_ms","invalidate_and_scatter_ms"))
  row["private_bank"]=int(raw[24]);row["published_frame_bank_token"]=int(raw[25])
  if not rc:
   if int(raw[24])>1 or int(raw[25])!=((int(raw[22])<<1)|int(raw[24])):bad.append({"case":case,"mode":mode,"reason":"publication identity/bank token"})
   if int(raw[6])!=length or int(raw[19])!=reference_checksum or not (int(raw[7])&4) or int(raw[23])!=int(raw[4]):bad.append({"case":case,"mode":mode,"reason":"status/count/checksum"})
   if rep==0:
    offset=int(raw[20]);end=offset+length
    okay=end<=len(archive) and np.array_equal(archive[offset:end],words)
    row["byte_archive_pass"]=bool(okay);archive_checks+=1
    if not okay:bad.append({"case":case,"mode":mode,"reason":"archived bytes differ or absent"})
  else:bad.append({"case":case,"mode":mode,"reason":"recorded firmware failure","rc":rc})
  rows.append(row)
 full_success=int(data[1])==1 and count==len(cases)*3*int(data[6]) and not bad
 balanced=None
 if full_success:
  for i,row in enumerate(rows):
   rep=i//(len(cases)*3);case=(i//3)%len(cases);mode=(i%3+rep+case)%3
   assert (row["repeat"],row["case_index"],row["mode"],row["frame_id"])==(rep,case,("full_raster","outer_bbox","merged_rectangles")[mode],len(cases)*3+i+1),"Frozen schedule mismatch"
  assert int(data[7])==rows[-1]["published_frame_bank_token"]
  if int(data[6])==6:
   balanced=all(sum(r["case_index"]==case and r["mode"]==mode and r["private_bank"]==bank for r in rows)==3 for case in range(len(cases)) for mode in ("full_raster","outer_bbox","merged_rectangles") for bank in (0,1))
   assert balanced,"Mode/private-bank imbalance"
 comparisons=[]
 for i,case in enumerate(cases):
  modes={mode:[r["service_ms"] for r in rows if r["case_index"]==i and r["mode"]==mode and r["repeat"]!=99 and r["rc"]==0] for mode in ("full_raster","outer_bbox","merged_rectangles")}
  means={k:float(np.mean(v)) if v else None for k,v in modes.items()}
  comparisons.append({"case":case["name"],"selected_tiles":len(case["selected_tile_indices"]),"service_means_ms":means,"samples":{k:len(v) for k,v in modes.items()},"not_a_held_out_mask":True})
 pins={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (out/"records.bin",out/"archive.bin",out/"launch_manifest.json") if p.exists()}
 report={"pass":full_success,"mode_and_bank_balance_verified":balanced,"physical_terminal_status":int(data[1]),"cache_enabled":bool(data[8]),"timer_hz":freq,"fabric_hz":manifest["fabric_mhz_actual"]*1e6,"records":rows,"comparisons":comparisons,"numerical_byte_archives_checked":archive_checks,"failures":bad,"input_hashes":pins,"measurement":"request-to-selected-residual-publication, not rendering/display/reconstruction","request_guard_cycles_include_host_gaps":True,"no_novel_cropping_claim":True,"source":str(Path(__file__).relative_to(ROOT))}
 (out/"analysis.json").write_text(json.dumps(report,indent=2)+"\n")
 print(json.dumps({"pass":full_success,"record_count":count,"byte_archives":archive_checks,"failures":bad}));raise SystemExit(0 if full_success else 1)
if __name__=="__main__":main()
