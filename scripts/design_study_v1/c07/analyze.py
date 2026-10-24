"""Independent C07 physical byte/metadata/schedule replay. Never accesses board."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import traceback
import numpy as np

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3]
sys.path.insert(0,str(ROOT))
from schedule import requests,CONDITIONS
from src.experiments.paper2_conventional_comparison_v1.comparison import rectangles,union_mask


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def u64(row,k):return int(row[k])+(int(row[k+1])<<32)


def check_pins(manifest):
 for pin in [manifest['image'],manifest['xsa'],manifest['firmware'],*manifest['scripts'],*manifest['pins']]:
  assert sha(pin['path'])==pin['sha256'],'pin mismatch: '+pin['path']


def expected_words(case,golden):
 selected=union_mask(rectangles(case['selected_tile_indices']),0,360,640).repeat(2,0).repeat(2,1)
 return golden[selected].reshape(-1)


def parse_records(data,archive,manifest,goldens,g):
 assert len(data)>=32 and int(data[0])==0x43303731
 count=int(data[2]);assert len(data)==32+count*28 and len(archive)==int(data[3])
 ordinal=manifest['ordinal'];assert ordinal in range(4)
 assert list(map(int,data[[5,6,8,11,12,13,14,15,21,22]]))==[68,3,1,ordinal,manifest['target_kind'],manifest['global_repeat_base'],0,manifest['initial_bank'],28,manifest['expected_records']]
 assert list(map(int,data[16:20]))==[f['input_word_fnv'] for f in g['frames']]
 freq=int(data[4]);assert abs(freq-float(manifest['hwh_cpu_mhz'])*1e6/2)<=1
 schedule=list(requests(ordinal));assert count==len(schedule)
 assert int(data[9])==(136 if manifest['target_kind'] else 68)
 rows=[];bad=[];archives=0;next_offset=0
 for i,(raw,want) in enumerate(zip(data[32:].reshape(-1,28),schedule)):
  case=int(raw[0]);mode=int(raw[1]);rep=int(raw[2]);condition=int(raw[26])
  assert (case,mode,rep,condition)==(want['case_index'],2,want['global_repeat'],want['condition_id']),'schedule mismatch'
  c=g['cases'][case];fi=c['frame_index'];frame=g['frames'][fi]
  regs=rectangles(c['selected_tile_indices'],mode='merged_rectangles')
  expected_input=sum(r.expand(3,360,640).area for r in regs)
  assert int(raw[4])==len(regs) and int(raw[5])==expected_input,'dependency traffic/region mismatch'
  rc=int(raw[3]);rc=rc-2**32 if rc>=2**31 else rc
  length=int(raw[21]);assert length==c['expected_words']
  assert int(raw[24])==want['private_bank'] and int(raw[22])==want['frame_id']
  assert int(raw[25])==want['published_frame_bank_token']
  enable=3 if condition==2 else 0
  assert int(raw[27])==enable
  service_ticks=u64(raw,8);assert service_ticks>=sum(u64(raw,k) for k in (10,12,14,16))
  numerical=int(raw[19])==c['expected_fnv']
  okay=rc==0 and numerical and (int(raw[7])&4)!=0 and not(int(raw[7])&17) and int(raw[6])==length and int(raw[23])==int(raw[4])
  bytepass=None
  if rep==0:
   assert int(raw[20])==next_offset
   words=expected_words(c,goldens[fi]);assert len(words)==length
   end=next_offset+length
   bytepass=bool(end<=len(archive) and np.array_equal(archive[next_offset:end],words))
   next_offset=end;archives+=1;okay=okay and bytepass
  else:assert int(raw[20])==0xffffffff
  if not okay:bad.append({'record':i,'case':case,'rc':rc,'byte_archive_pass':bytepass,'checksum_pass':numerical,'status':int(raw[7])})
  row={'case_index':case,'case':c['name'],'frame_index':fi,'frame_name':frame['stratum']+'/'+frame['scene'],
   'mask_index':c['mask_index'],'mask_name':c['name'].split('_',1)[1],
   'condition':CONDITIONS[condition],'launch_id':manifest['launch_id'],'global_repeat':rep,'repeat':rep,
   'mode':'merged_rectangles','rc':rc,'warmup_failure':False,'event_outcome':'committed' if okay else 'rejected_or_failed',
   'regions':int(raw[4]),'input_words':int(raw[5]),'output_words':int(raw[6]),'status':int(raw[7]),
   'service_ms':service_ticks*1000/freq,'planning_ms':u64(raw,10)*1000/freq,'packing_ms':u64(raw,12)*1000/freq,
   'dma_and_engine_ms':u64(raw,14)*1000/freq,'invalidate_and_scatter_ms':u64(raw,16)*1000/freq,
   'request_guard_elapsed_cycles':int(raw[18]),'checksum':int(raw[19]),'frame_id':int(raw[22]),
   'completed_regions':int(raw[23]),'archive_word_offset':int(raw[20]),'archive_word_length':length,
   'numerical_checksum_pass':numerical,'byte_archive_pass':bytepass,'private_bank':int(raw[24]),
   'published_frame_bank_token':int(raw[25]),'zero_enable_readback':int(raw[27])}
  row['other_service_ms']=row['service_ms']-sum(row[k] for k in ('planning_ms','packing_ms','dma_and_engine_ms','invalidate_and_scatter_ms'))
  rows.append(row)
 assert next_offset==len(archive) and int(data[7])==rows[-1]['published_frame_bank_token']
 return {'pass':int(data[1])==1 and not bad,'prospective_schedule_verified':True,'records':rows,'failures':bad,
  'numerical_byte_archives_checked':archives,'mode_and_bank_balance_verified':None,'timer_hz':freq,
  'fabric_hz':manifest['fabric_mhz_actual']*1e6,'physical_terminal_status':int(data[1]),'cache_enabled':True,
  'measurement':'planning-to-selected-residual-publication; arm/input selection outside boundary; not reconstructed display',
  'preparation_requests':int(data[9]),'comparisons':[],'development_only':True}


def analyze_dense(data,words,goldens,g):
 assert len(data)==32 and int(data[0])==0x43303731 and int(data[2])==0 and int(data[3])==0
 assert list(map(int,data[[9,10,11,12,14,26]]))==[4,3686400,99,1,1,15]
 assert list(map(int,data[16:20]))==[f['input_word_fnv'] for f in g['frames']]
 assert len(words)==3686400
 checks=[bool(np.array_equal(words[i*921600:(i+1)*921600],goldens[i].reshape(-1))) for i in range(4)]
 return {'pass':int(data[1])==1 and all(checks),'physical_terminal_status':int(data[1]),'dense_frame_byte_pass':checks,
  'dense_archived_words':len(words),'performance_measurement':False,'fabric_hz':50000000,'records':[]}


def main():
 p=argparse.ArgumentParser();p.add_argument('--id',required=True);a=p.parse_args()
 out=HERE/'physical'/a.id;target=out/'analysis.json'
 if target.exists():raise FileExistsError(target)
 result={}
 try:
  m=json.loads((out/'launch_manifest.json').read_text());check_pins(m)
  capture=json.loads((out/'capture_record.json').read_text());assert capture['status']=='CAPTURED' and capture['terminal'] and capture['serial_closed']
  if m['safety_qualification']:
   helper=ROOT/'scripts/paper2_conventional_comparison_v1/replay_safety.py'
   proc=subprocess.run([sys.executable,str(helper),'--run',str(out),'--cases',str(HERE/'firmware/F003/cases.json'),'--record'],capture_output=True,timeout=300)
   (out/'safety_replay.log').write_bytes(proc.stdout+proc.stderr)
   assert proc.returncode==0
   result=json.loads((out/'safety_analysis.json').read_text());result['fabric_hz']=50000000
  else:
   g=json.loads(Path(m['golden_manifest']).read_text());folder=Path(m['golden_manifest']).parent
   for frame in g['frames']:assert sha(folder/frame['golden_file'])==frame['golden_sha256']
   golden=[np.load(folder/f['golden_file'],mmap_mode='r',allow_pickle=False) for f in g['frames']]
   data=np.fromfile(out/'records.bin',dtype='<u4')
   if m['dense_qualification']:result=analyze_dense(data,np.fromfile(out/'dense.bin',dtype='<u4'),golden,g)
   else:
    archive=np.fromfile(out/'archive.bin',dtype='<u4') if (out/'archive.bin').exists() else np.array([],dtype='<u4')
    result=parse_records(data,archive,m,golden,g)
 except Exception as error:
  result={'pass':False,'error':repr(error),'records':[]};(out/'analysis_failure.log').write_text(traceback.format_exc())
 result['input_hashes']={p.name:sha(p) for p in out.iterdir() if p.is_file() and p.name in ('records.bin','archive.bin','dense.bin','launch_manifest.json','capture_record.json')}
 result['analyzer_sha256']=sha(__file__)
 target.write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps({'pass':result['pass'],'records':len(result.get('records',[])),'error':result.get('error'),'archives':result.get('numerical_byte_archives_checked')}))
 raise SystemExit(0 if result['pass'] else 1)


if __name__=='__main__':main()
