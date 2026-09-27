"""Read and independently verify the bounded physical safety byte archives."""
import argparse,hashlib,json,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from portable_oracle import golden
from src.experiments.paper2_conventional_comparison_v1.comparison import WEIGHTS,rectangles,union_mask
from replay_physical import fnv
NAMES=("seed_publication","cancel_after_private_region","reuse_after_cancel","expire_between_regions_immutable_budget","reuse_after_expiry","insufficient_halo","reuse_after_bad_halo","duplicate_owned_region","reuse_after_duplicate","active_restart","reuse_after_restart")
def main():
 p=argparse.ArgumentParser();p.add_argument("--run",type=Path,default=ROOT/"results/paper2_conventional_comparison_v1/P005");p.add_argument("--cases",type=Path,default=ROOT/"results/paper2_conventional_comparison_v1/F008/cases.json");p.add_argument("--record",action="store_true");a=p.parse_args()
 manifest=json.loads((a.run/"launch_manifest.json").read_text());cases=json.loads(a.cases.read_text())
 assert hashlib.sha256(WEIGHTS.read_bytes()).hexdigest()==manifest["oracle_weights"]["sha256"]
 assert hashlib.sha256(a.cases.read_bytes()).hexdigest()==manifest["case_manifest_pin"]["sha256"]
 data=np.fromfile(a.run/"records.bin",dtype="<u4");archive=np.fromfile(a.run/"archive.bin",dtype="<u4")
 assert data[0]==0x524f4931 and data[9]==0x53414631
 assert len(data)==32+26*int(data[2]) and len(archive)==int(data[3])
 mask=union_mask(rectangles(cases[2]["selected_tile_indices"]),0,360,640).repeat(2,0).repeat(2,1)
 words=golden()[mask].reshape(-1);checksum=fnv(words);rows=[];passed=int(data[1])==1 and int(data[2])==11
 previous_token=0
 for i,row in enumerate(data[32:].reshape(-1,26)):
  offset=int(row[20]);length=int(row[21]);s=int(row[3]);outcome=(s>>5)&7;fault=i in(1,3,5,7,9)
  expected=(3 if i==1 else 4 if i==3 else 5) if fault else 1
  numerical=length==len(words) and offset==i*len(words) and np.array_equal(archive[offset:offset+length],words)
  identity=int(row[12])==i+1 and int(row[13])==(i if fault else i+1)
  token=int(row[5]);token_ok=(token==previous_token and int(row[4])==previous_token) if fault else ((token>>1)==i+1 and token!=previous_token)
  correct=bool(int(row[0])==0x53544654 and row[1]==i and row[2]==1 and row[6]==checksum and row[7]==checksum and row[14]==1 and numerical and identity and token_ok and outcome==expected and not(s&1) and bool(s&4)==(not fault))
  if i in(1,3,7):correct=correct and row[8]==15360 and row[9]==1 and row[15]==1
  if i==3:correct=correct and 50000000<=row[10]<=50000002
  rows.append({"id":i,"test":NAMES[i] if i<len(NAMES) else "unexpected","pass":bool(correct),"outcome":outcome,"status":s,"frame_id":int(row[12]),"committed_source_id":int(row[13]),"public_token":token,"private_words_before_fault":int(row[8]),"completed_regions_before_fault":int(row[9]),"guard_elapsed_cycles":int(row[10]),"distinct_private_candidate_observed":bool(row[15]),"archived_words":length,"byte_oracle_pass":bool(numerical)})
  passed=passed and correct;previous_token=token
 result={"pass":bool(passed),"physical_terminal_status":int(data[1]),"checks":rows,"archived_words":len(archive),"performance_measurement":False,"same_routed_image_sha256":manifest["image"]["sha256"],"input_hashes":{n:hashlib.sha256((a.run/n).read_bytes()).hexdigest() for n in ("records.bin","archive.bin","launch_manifest.json")}}
 if a.record:
  target=a.run/"safety_analysis.json";assert not target.exists();target.write_text(json.dumps(result,indent=2)+"\n")
 print(json.dumps(result,indent=2));raise SystemExit(0 if passed else 1)
if __name__=="__main__":main()
