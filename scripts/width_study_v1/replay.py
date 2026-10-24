"""Read-only NumPy replay of eight width-study captures and three integer models."""
from pathlib import Path
from types import SimpleNamespace
import contextlib, gzip, hashlib, importlib.util, io, json, re, statistics, sys, tempfile
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
DATA=ROOT/'results/width_study_v1'
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'scripts/paper2_conventional_comparison_v1'))

from payloads import payload_bytes, payload_exists, raw_payload

def sha(b): return hashlib.sha256(b).hexdigest()
def doc(p): return json.loads(p.read_text())
def raw(p): return raw_payload(p)
def signed(text,bits):
    value=int(text,16)
    return value-(1<<bits) if value&(1<<(bits-1)) else value

def model(path):
    text=path.read_text()
    width=int(re.search(r'TRAINED_FEATURE_CHANNELS\s*=\s*(\d+)',text)[1])
    rows={int(i):[signed(v,8) for v in reversed(re.findall(r"8'sh([0-9A-Fa-f]{2})",s))]
          for i,s in re.findall(r'^\s*(\d+): trained_weight_row = \{([^}]+)\};',text,re.M)}
    biases={int(i):signed(v,32) for i,v in re.findall(r"^\s*(\d+): trained_bias_flat = 32'sh([0-9A-Fa-f]{8});",text,re.M)}
    shifts={int(i):int(v) for i,v in re.findall(r"^\s*(\d+): trained_right_shift_flat = 5'd(\d+);",text,re.M)}
    assert len(rows)==3*width+width*width+12*width and len(biases)==2*width+12
    assert len(shifts)==len(biases)
    weights=[];bias=[];shift=[];row=0;channel=0
    for outputs,inputs in ((width,3),(width,width),(12,width)):
        weights.append(np.asarray([rows[i] for i in range(row,row+outputs*inputs)],dtype=np.int8).reshape(outputs,inputs,3,3))
        bias.append(np.asarray([biases[i] for i in range(channel,channel+outputs)],dtype=np.int64))
        shift.append(np.asarray([shifts[i] for i in range(channel,channel+outputs)],dtype=np.int64))
        row+=outputs*inputs;channel+=outputs
    return SimpleNamespace(width=width,weights=weights,biases=bias,shifts=shift)

def shuffle(x):
    h,w,_=x.shape
    return x.reshape(h,w,3,2,2).transpose(0,3,1,4,2).reshape(2*h,2*w,3)

def int_patch(image,m,target):
    from src.experiments.paper2_conventional_comparison_v1.comparison import Rect
    box=target.expand(3,360,640);x=image[box.y0:box.y1,box.x0:box.x1].astype(np.int64)
    for layer in range(3):
        h,w,_=x.shape;pad=np.pad(x,((1,1),(1,1),(0,0)))
        weight=m.weights[layer].astype(np.int64)
        acc=np.broadcast_to(m.biases[layer],(h,w,len(weight))).copy()
        for ky in range(3):
            for kx in range(3):acc+=pad[ky:ky+h,kx:kx+w]@weight[:,:,ky,kx].T
        s=m.shifts[layer];v=np.sign(acc)*((np.abs(acc)+(1<<(s-1)))>>s)
        if layer<2:v=np.maximum(v,0)
        v=np.clip(v,-128,127);n=target.expand(2-layer,360,640)
        x=v[n.y0-box.y0:n.y1-box.y0,n.x0-box.x0:n.x1-box.x0].copy();box=n
    return shuffle(x.astype(np.int8))

def golden(path):
    from src.experiments.paper2_conventional_comparison_v1.comparison import Rect
    m=model(path);y,x,c=np.indices((360,640,3),dtype=np.int32)
    image=((17*y+29*x+43*c+51)%256-128).astype(np.int8)
    act=image.astype(np.float64)
    for layer in range(3):
        weights=m.weights[layer].astype(np.float64);bias=m.biases[layer]
        assert int(np.abs(bias).max())+weights.shape[1]*9*128*128<2**31
        pad=np.pad(act,((1,1),(1,1),(0,0)))
        windows=np.lib.stride_tricks.sliding_window_view(pad,(3,3),axis=(0,1))
        out=np.empty((360,640,len(bias)),dtype=np.float64)
        divisor=2.0**m.shifts[layer]
        for row in range(0,360,24):
            v=np.einsum('yxckl,ockl->yxo',windows[row:row+24],weights,optimize=True)+bias
            v=np.sign(v)*np.floor((np.abs(v)+divisor/2)/divisor)
            if layer<2:v=np.maximum(v,0)
            out[row:row+24]=np.clip(v,-128,127)
        act=out
    rgb=shuffle(act.astype(np.int8))
    for box in (Rect(0,0,3,4),Rect(0,636,3,640),Rect(357,0,360,4),Rect(357,636,360,640),Rect(120,256,124,260),Rect(59,63,63,67)):
        assert np.array_equal(int_patch(image,m,box),rgb[box.y0*2:box.y1*2,box.x0*2:box.x1*2])
    u=rgb.astype(np.uint8).astype(np.uint32)
    return u[:,:,0]|(u[:,:,1]<<8)|(u[:,:,2]<<16)

def summary(reports):
    rows=[]
    for network,saved in reports:
        cells=[i for i,c in enumerate(saved['comparisons']) if 0<c['selected_tiles']<60]
        means={m:statistics.mean(statistics.mean(r['service_ms'] for r in saved['records']
                   if r['case_index']==i and r['mode']==m) for i in cells)
               for m in ('full_raster','outer_bbox','merged_rectangles')}
        rows.append({'network':network,'means':means,
                     'vs_raster':100*(1-means['merged_rectangles']/means['full_raster']),
                     'vs_bbox':100*(1-means['merged_rectangles']/means['outer_bbox'])})
    return rows

def main():
    export=doc(DATA/'export_manifest.json')
    for name,pin in export['files'].items():
        blob=payload_bytes(ROOT/name);assert sha(blob)==pin['distributed_sha256'],name
        unpacked=gzip.decompress(blob) if pin['compression']=='gzip' else blob
        assert sha(unpacked)==pin['original_sha256'],name
    for mapping in export['compiled_sources'].values():
        for pin in mapping.values():assert sha((ROOT/pin['path']).read_bytes())==pin['sha256']
    packages={n:ROOT/p for n,p in export['model_packages'].items()}
    goldens={n:golden(p) for n,p in packages.items()}
    print('Three dense references regenerated; per-channel shifts and six INT64 patches checked.',flush=True)
    spec=importlib.util.spec_from_file_location('raw_board_replay',ROOT/'scripts/paper2_conventional_comparison_v1/replay_physical.py')
    replay=importlib.util.module_from_spec(spec);spec.loader.exec_module(replay)
    results={}
    with tempfile.TemporaryDirectory(prefix='paper2_width_') as scratch:
        for campaign,order in export['campaigns'].items():
            reports=[];expected=doc(DATA/campaign/'comparison.json')
            for item in order:
                run=item['run'];network=item['model'];folder=DATA/campaign/run
                saved=doc(folder/'analysis.json');capture=doc(folder/'capture_record.json')
                assert saved['pass'] and capture['status']=='CAPTURED' and capture['serial_closed']
                target=Path(scratch)/campaign/run;target.mkdir(parents=True)
                for name in ('records.bin','archive.bin','launch_manifest.json','analysis.json'):
                    (target/name).write_bytes(raw(folder/name))
                replay.WEIGHTS=packages[network];replay.golden=lambda n=network:goldens[n]
                previous=sys.argv;sys.argv=['replay','--run',str(target),'--cases',str(ROOT/'results/paper2_conventional_comparison_v1/F006/cases.json')]
                try:
                    with contextlib.redirect_stdout(io.StringIO()):replay.main()
                finally:sys.argv=previous
                reports.append((network,saved))
                print('Width raw replay passed:',campaign,run,network,flush=True)
            rows=summary(reports)
            for i,row in enumerate(rows):
                original=expected['runs'][i]
                # Independent averaging order can differ by one float64 ULP.
                assert all(abs(v-original['sparse_equal_mask_means_ms'][k])<1e-10
                           for k,v in row['means'].items())
                assert abs(row['vs_raster']-original['merged_reduction_vs_raster_percent'])<1e-10
                assert abs(row['vs_bbox']-original['merged_reduction_vs_bbox_percent'])<1e-10
            for block,a,b in ((1,0,1),(2,3,2)):
                effect=expected['within_session_width_interactions'][block-1]
                assert abs(rows[b]['vs_raster']-rows[a]['vs_raster']-effect['merged_vs_raster_effect_change_percentage_points'])<1e-10
                assert abs(rows[b]['vs_bbox']-rows[a]['vs_bbox']-effect['merged_vs_bbox_effect_change_percentage_points'])<1e-10
            results[campaign]=rows
    print(json.dumps({'pass':True,'records':2448,'byte_archives':408,'dense_models':3,'campaigns':results},indent=2))

if __name__=='__main__':main()
