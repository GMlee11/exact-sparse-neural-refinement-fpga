"""Portable read-only replay; reuses released W24 inputs and regenerates pixels."""
from pathlib import Path
import gzip, hashlib, importlib.util, io, json, sys
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
DATA=ROOT/'results/output_suppression_v1'
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(Path(__file__).resolve().parent))
import analyze, summarize

def doc(p):return json.loads(p.read_text())
from payloads import payload_bytes, payload_exists, raw_payload

def sha(b):return hashlib.sha256(b).hexdigest()
def raw(p): return raw_payload(p)
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def main():
    export=doc(DATA/'export_manifest.json')
    for name,pin in export['files'].items():
        b=payload_bytes(ROOT/name);assert sha(b)==pin['sha256'],name
        assert sha(gzip.decompress(b) if pin['compression']=='gzip' else b)==pin['original_sha256'],name
    for pin in export['compiled_sources'].values():
        assert sha((ROOT/pin['path']).read_bytes())==pin['sha256']
    oracle=load('suppression_width_oracle',ROOT/'scripts/width_study_v1/replay.py')
    dense=load('suppression_dense',ROOT/'scripts/organization_skipping_v1/replay.py').dense
    folder=ROOT/export['goldens'];g=doc(folder/'manifest.json')
    bankbytes=raw(folder/'input_banks.bin');assert sha(bankbytes)==g['input_banks']['sha256']
    banks=np.frombuffer(bankbytes,dtype='<u4').reshape(4,360,640)
    model=oracle.model(ROOT/export['model']);goldens={}
    for fi in (0,2):
        image=np.stack([(banks[fi]>>(8*c))&255 for c in range(3)],axis=-1).astype(np.uint8).view(np.int8)
        b=raw(folder/g['frames'][fi]['golden_file']);assert sha(b)==g['frames'][fi]['golden_sha256']
        goldens[fi]=np.load(io.BytesIO(b),allow_pickle=False)
        assert np.array_equal(dense(image,model,oracle),goldens[fi])
    analyses={};manifests={};qrecords=qarchives=0
    for run in ('Q001','Q002','P001','P002','P003','P004'):
        target=DATA/run;m=doc(target/'launch_manifest.json');c=doc(target/'capture_record.json')
        assert c['status']=='CAPTURED' and c['serial_closed'] and c['terminal']
        data=np.frombuffer(raw(target/'records.bin'),dtype='<u4')
        archive=np.frombuffer(gzip.decompress(payload_bytes(DATA/export['archives'][run])),dtype='<u4') if run in export['archives'] else np.array([],dtype='<u4')
        actual=analyze.parse(data,archive,m,g,goldens);saved=doc(target/'analysis.json')
        assert actual['passed'] and saved['passed']
        assert actual['records']==saved['records'] and actual['byte_archives']==saved['byte_archives']
        if run.startswith('Q'):
            qrecords+=len(actual['records']);qarchives+=actual['byte_archives']
        else:analyses[run]=actual;manifests[run]=m
    assert (qrecords,qarchives)==(144,144)
    actual=summarize.compute(analyses,manifests);saved=doc(DATA/'comparison.json')
    for k,v in actual.items():assert v==saved[k],k
    print('OUTPUT_SUPPRESSION_REPLAY_PASS 864 primary records; 144 primary archives; 144 qualification records; 144 qualification archives; regenerated W24 dense outputs')

if __name__=='__main__':main()
