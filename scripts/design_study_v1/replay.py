"""Portable, read-only raw replay of the completed buffer and skipping studies.

Run python -B scripts/design_study_v1/replay.py from the artifact root.
Uses only NumPy plus the standard library. Temporary raw files live outside repo.
"""
from pathlib import Path
import contextlib, gzip, hashlib, importlib.util, io, json, sys, tempfile
import numpy as np
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
DATA=ROOT/'results/design_study_v1'
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'scripts/paper2_conventional_comparison_v1'))
sys.path.insert(0,str(HERE/'c07'))
from portable_oracle import golden
from src.experiments.paper2_conventional_comparison_v1.comparison import WEIGHTS, Rect, fused_region
from src.hardware.experiment133.reference_sparse_distilled_same_bitstream_133 import parse_trained_package
def loadmodule(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    obj=importlib.util.module_from_spec(spec);spec.loader.exec_module(obj);return obj
from payloads import payload_bytes, payload_exists, raw_payload

def sha(b):return hashlib.sha256(b).hexdigest()
def raw(path): return raw_payload(path)
def doc(path):return json.loads(path.read_text())
def oracle(image):
    model=parse_trained_package(WEIGHTS);activation=image.astype(np.float64)
    for layer in range(3):
        padded=np.pad(activation,((1,1),(1,1),(0,0)))
        windows=np.lib.stride_tricks.sliding_window_view(padded,(3,3),axis=(0,1))
        weights=model.weights[layer].astype(np.float64);bias=model.biases[layer].astype(np.float64)
        out=np.empty((360,640,len(bias)),dtype=np.float64)
        for row in range(0,360,24):
            value=np.einsum('yxckl,ockl->yxo',windows[row:row+24],weights,optimize=True)+bias
            value=np.sign(value)*np.floor((np.abs(value)+128)/256)
            if layer<2:value=np.maximum(value,0)
            out[row:row+24]=np.clip(value,-128,127)
        activation=out
    rgb=activation.astype(np.int8).reshape(360,640,3,2,2).transpose(0,3,1,4,2).reshape(720,1280,3)
    for box in (Rect(0,0,3,4),Rect(120,256,124,260),Rect(357,636,360,640)):
        exact=fused_region(image,model,box).reshape(box.y1-box.y0,box.x1-box.x0,3,2,2).transpose(0,3,1,4,2).reshape(2*(box.y1-box.y0),2*(box.x1-box.x0),3)
        assert np.array_equal(exact,rgb[2*box.y0:2*box.y1,2*box.x0:2*box.x1])
    u=rgb.astype(np.uint8).astype(np.uint32)
    return u[:,:,0]|(u[:,:,1]<<8)|(u[:,:,2]<<16)
def main():
    export=doc(DATA/'export_manifest.json')
    for name,pin in export['files'].items():
        blob=payload_bytes(ROOT/name);assert sha(blob)==pin['distributed_sha256'],name
        original=gzip.decompress(blob) if pin['compression']=='gzip' else blob
        assert sha(original)==pin['original_sha256'],name
    br=loadmodule('old_raw_replay',ROOT/'scripts/paper2_conventional_comparison_v1/replay_physical.py')
    cached=golden();br.golden=lambda:cached
    buffer_reports=[]
    with tempfile.TemporaryDirectory(prefix='paper2_replay_') as tmp:
        for launch in ('P002','P003','P004','P005'):
            folder=DATA/'buffer'/launch;saved=doc(folder/'analysis.json')
            target=Path(tmp)/launch;target.mkdir()
            for name,digest in saved['input_hashes'].items():
                b=raw(folder/name);assert sha(b)==digest;(target/name).write_bytes(b)
            (target/'analysis.json').write_bytes((folder/'analysis.json').read_bytes())
            argv=sys.argv;sys.argv=['replay','--run',str(target),'--cases',str(ROOT/'results/paper2_conventional_comparison_v1/F006/cases.json')]
            try:
                with contextlib.redirect_stdout(io.StringIO()):br.main()
            finally:sys.argv=argv
            buffer_reports.append(saved)
            print('Buffer raw replay passed:',launch,flush=True)
    buf=json.loads(json.dumps(loadmodule('buffer_summary',HERE/'buffer_summary.py').summarize(buffer_reports)))
    expected=doc(DATA/'buffer/paired_service_comparison.json')
    for key,value in buf.items():assert value==expected[key],key
    g=doc(DATA/'skipping/goldens/manifest.json');assert sha(WEIGHTS.read_bytes())==g['weights_sha256']
    bankbytes=raw(DATA/'skipping/goldens/input_banks.bin');assert sha(bankbytes)==g['input_banks']['sha256']
    banks=np.frombuffer(bankbytes,dtype='<u4').reshape(4,360,640)
    goldens=[]
    for i,f in enumerate(g['frames']):
        b=raw(DATA/'skipping/goldens'/f['golden_file']);assert sha(b)==f['golden_sha256']
        arr=np.load(io.BytesIO(b),allow_pickle=False)
        image=np.stack([(banks[i]>>(8*c))&255 for c in range(3)],axis=-1).astype(np.uint8).view(np.int8)
        assert np.array_equal(oracle(image),arr),'Dense reference regeneration failed'
        goldens.append(arr);print('Dense input/reference regenerated:',i,flush=True)
    parser=loadmodule('c07_parser',HERE/'c07/analyze.py');reports=[]
    for launch in ('P001','P002','P003','P004'):
        folder=DATA/'skipping'/launch;saved=doc(folder/'analysis.json');manifest=doc(folder/'launch_manifest.json')
        assert sha((HERE/'c07/analyze.py').read_bytes())==saved['analyzer_sha256']
        for name,digest in saved['input_hashes'].items():assert sha(raw(folder/name))==digest,name
        archive=raw(folder/'archive.bin') if payload_exists(folder/'archive.bin.gz') else b''
        replay=parser.parse_records(np.frombuffer(raw(folder/'records.bin'),dtype='<u4'),np.frombuffer(archive,dtype='<u4'),manifest,goldens,g)
        assert replay['pass'] and replay['records']==saved['records']
        reports.append(replay);print('Skipping raw replay passed:',launch,flush=True)
    skip=loadmodule('skip_summary',HERE/'skip_summary.py').summarize(reports)
    expected=doc(DATA/'skipping/c07_paired_physical_analysis.json')
    for key,value in skip.items():assert value==expected[key],key
    print(json.dumps({'pass':True,'buffer_records':1224,'buffer_byte_archives':204,
        'skipping_records':1224,'skipping_byte_archives':204,'dense_references_regenerated':4,
        'buffer_means':buf['sparse_equal_mask_means'],'skipping_primary':skip['primary_equal_frame_mask_sparse']},indent=2))
if __name__=='__main__':main()
