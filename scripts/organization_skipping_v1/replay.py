"""Portable read-only replay of three-width organization/skipping captures."""
from pathlib import Path
import gzip,hashlib,importlib.util,io,json,statistics,sys
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
DATA=ROOT/'results/organization_skipping_v1'
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(Path(__file__).resolve().parent))
import analyze, summarize
def doc(p):return json.loads(p.read_text())
from payloads import payload_bytes, payload_exists, raw_payload

def sha(b):return hashlib.sha256(b).hexdigest()
def raw(p): return raw_payload(p)
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def dense(image,model,oracle):
    act=image.astype(np.float64)
    for layer in range(3):
        weights=model.weights[layer].astype(np.float64);bias=model.biases[layer]
        assert int(np.abs(bias).max())+weights.shape[1]*9*128*128<2**31
        pad=np.pad(act,((1,1),(1,1),(0,0)))
        windows=np.lib.stride_tricks.sliding_window_view(pad,(3,3),axis=(0,1))
        out=np.empty((360,640,len(bias)),dtype=np.float64);divisor=2.0**model.shifts[layer]
        for row in range(0,360,24):
            v=np.einsum('yxckl,ockl->yxo',windows[row:row+24],weights,optimize=True)+bias
            v=np.sign(v)*np.floor((np.abs(v)+divisor/2)/divisor)
            if layer<2:v=np.maximum(v,0)
            out[row:row+24]=np.clip(v,-128,127)
        act=out
    rgb=oracle.shuffle(act.astype(np.int8))
    from src.experiments.paper2_conventional_comparison_v1.comparison import Rect
    for box in (Rect(0,0,3,4),Rect(0,636,3,640),Rect(357,0,360,4),Rect(357,636,360,640),Rect(59,63,63,67)):
        assert np.array_equal(oracle.int_patch(image,model,box),rgb[box.y0*2:box.y1*2,box.x0*2:box.x1*2])
    u=rgb.astype(np.uint8).astype(np.uint32)
    return u[:,:,0]|(u[:,:,1]<<8)|(u[:,:,2]<<16)

def main():
    export=doc(DATA/'export_manifest.json')
    for name,pin in export['files'].items():
        b=payload_bytes(ROOT/name);assert sha(b)==pin['distributed_sha256'],name
        assert sha(gzip.decompress(b) if pin['compression']=='gzip' else b)==pin['original_sha256'],name
    oracle=load('width_oracle',ROOT/'scripts/width_study_v1/replay.py')
    bankbytes=gzip.decompress((ROOT/export['input_bank']).read_bytes())
    banks=np.frombuffer(bankbytes,dtype='<u4').reshape(4,360,640)
    total=archives=qualification=qualarchives=diagnostic=0
    comparison=doc(DATA/'comparison.json')
    for width,campaign in export['campaigns'].items():
        folder=DATA/width;g=doc(folder/'goldens/manifest.json')
        assert sha(bankbytes)==g['input_banks']['sha256']
        for pin in campaign['compiled_sources'].values():assert sha((ROOT/pin['path']).read_bytes())==pin['sha256']
        model=oracle.model(ROOT/export['models'][width]);goldens={}
        for fi in (0,2):
            image=np.stack([(banks[fi]>>(8*c))&255 for c in range(3)],axis=-1).astype(np.uint8).view(np.int8)
            path=(ROOT/'results/design_study_v1/skipping/goldens' if width=='w24' else folder/'goldens')/g['frames'][fi]['golden_file']
            b=raw(path);assert sha(b)==g['frames'][fi]['golden_sha256']
            golden=np.load(io.BytesIO(b),allow_pickle=False)
            assert np.array_equal(dense(image,model,oracle),golden)
            goldens[fi]=golden
        print('Regenerated dense references:',width,flush=True)
        primary=[]
        for run in campaign['launches']:
            target=folder/run;m=doc(target/'launch_manifest.json')
            c=doc(target/'capture_record.json');assert c['status']=='CAPTURED' and c['serial_closed']
            data=np.frombuffer(raw(target/'records.bin'),dtype='<u4')
            archive=np.frombuffer(raw(target/'archive.bin'),dtype='<u4') if payload_exists(target/'archive.bin.gz') else np.array([],dtype='<u4')
            actual=analyze.parse(data,archive,m,g,goldens)
            saved=doc(target/('analysis_corrected.json' if width=='w24' and run=='Q001' else 'analysis.json'))
            assert actual['passed'] and saved['passed']
            assert actual['records']==saved['records'] and actual['byte_archives']==saved['byte_archives']
            if run.startswith('P'):
                primary+=actual['records'];total+=len(actual['records']);archives+=actual['byte_archives']
            elif run.startswith('Q'):qualification+=len(actual['records']);qualarchives+=actual['byte_archives']
            else:diagnostic+=len(actual['records'])
        summary=summarize.summarize(primary);saved=doc(folder/'pilot_summary.json')
        assert summary['cases']==saved['cases']
        cells=[c['segments'][0] for c in summary['cases'] if not c['control']]
        for condition in ('reference','skip_off','skip_on'):
            expected=comparison['widths'][width[1:]]['all']['engines'][condition]['mean_service_ms']
            for mode in ('raster','bounding_box','merged'):
                assert abs(statistics.mean(c['mean_service_ms'][condition][mode] for c in cells)-expected[mode])<1e-10
        print('All captures and aggregates replayed:',width,flush=True)
    assert (total,archives,qualification,qualarchives,diagnostic)==(1944,324,216,216,72)
    print('ORGANIZATION_SKIPPING_REPLAY_PASS',total,'primary records;',archives,'primary archives;',qualification,'qualification records;',qualarchives,'qualification archives;',diagnostic,'diagnostic records')
if __name__=='__main__':main()
