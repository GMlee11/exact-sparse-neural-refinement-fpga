"""Offline characterization of retained inputs and final-baseline geometry.

Default: recompute and verify the distributed analysis. --write creates it once.
No hardware timings are generated, modified, pooled across studies, or fitted.
"""
from pathlib import Path
import argparse, gzip, hashlib, importlib.util, io, json, statistics, sys
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT/'results/interpretation_v1/analysis.json'
sys.path.insert(0, str(ROOT))
from src.experiments.paper2_conventional_comparison_v1.comparison import Rect, rectangles, union_mask
from payloads import raw_payload
FRAMES = (0, 2)
MASKS = (2, 5, 4, 10)


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT/path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read(path):
    return json.loads((ROOT/path).read_text())


def characterize(image, model, cases, oracle, golden):
    activation = image.astype(np.float64)
    layers = []
    for layer in range(3):
        weights = model.weights[layer].astype(np.float64)
        bias = model.biases[layer]
        # Products/sums remain exact in float64 and inside the INT32 bound.
        assert int(np.abs(bias).max()) + weights.shape[1]*9*128*128 < 2**31
        padded = np.pad(activation, ((1,1), (1,1), (0,0)))
        windows = np.lib.stride_tricks.sliding_window_view(padded, (3,3), axis=(0,1))
        zero_window = np.all(windows == 0, axis=(-1,-2))
        eligible = np.sum(~zero_window, axis=-1)
        per_mask = []
        for index in MASKS:
            selected = cases[index]['selected_tile_indices']
            support = union_mask(rectangles(selected, mode='tiles'), 2-layer, 360, 640)
            counts = eligible[support]
            channels = weights.shape[1]
            histogram = np.bincount(counts, minlength=channels+1).tolist()
            positions = int(support.sum())
            assert sum(histogram) == positions
            per_mask.append(dict(mask=index, positions=positions,
                input_channels=channels, eligible_channel_histogram=histogram,
                all_zero_channel_window_percent=100*float(zero_window[support].mean()),
                effective_channel_issue_reduction_percent=100*(1-float(np.maximum(1,counts).mean())/channels),
                bias_only_positions=int((counts == 0).sum())))
        out = np.empty((360,640,len(bias)), dtype=np.float64)
        divisor = 2.0**model.shifts[layer]
        for row in range(0,360,24):
            v = np.einsum('yxckl,ockl->yxo', windows[row:row+24], weights, optimize=True)+bias
            v = np.sign(v)*np.floor((np.abs(v)+divisor/2)/divisor)
            if layer < 2:
                v = np.maximum(v,0)
            out[row:row+24] = np.clip(v,-128,127)
        activation = out
        layers.append(dict(layer=layer+1, masks=per_mask,
                           full_frame_output_zero_percent=100*float((out == 0).mean())))
    rgb = oracle.shuffle(activation.astype(np.int8))
    u = rgb.astype(np.uint8).astype(np.uint32)
    words = u[:,:,0] | (u[:,:,1]<<8) | (u[:,:,2]<<16)
    assert np.array_equal(words, golden), 'Regenerated dense output disagrees with archived reference'
    for box in (Rect(0,0,3,4),Rect(357,636,360,640),Rect(59,63,63,67)):
        assert np.array_equal(oracle.int_patch(image, model, box),
                              rgb[2*box.y0:2*box.y1,2*box.x0:2*box.x1])
    return layers


def compute():
    export = read('results/organization_skipping_v1/export_manifest.json')
    cases = read('results/paper2_conventional_comparison_v1/F006/cases.json')
    comparison = read('results/output_suppression_v1/comparison.json')
    sources = {export['input_bank'], 'results/organization_skipping_v1/export_manifest.json',
               'results/paper2_conventional_comparison_v1/F006/cases.json',
               'results/output_suppression_v1/comparison.json',
               'scripts/width_study_v1/replay.py',
               'src/experiments/paper2_conventional_comparison_v1/comparison.py'}
    oracle = load('width_oracle', 'scripts/width_study_v1/replay.py')
    bank = np.frombuffer(gzip.decompress((ROOT/export['input_bank']).read_bytes()), dtype='<u4').reshape(4,360,640)
    sparsity = []
    for width in ('w24','w16','w12'):
        path = export['models'][width]; sources.add(path)
        model = oracle.model(ROOT/path)
        folder = ROOT/'results/organization_skipping_v1'/width/'goldens'
        manifest = json.loads((folder/'manifest.json').read_text())
        sources.add((folder/'manifest.json').relative_to(ROOT).as_posix())
        for frame in FRAMES:
            image = np.stack([(bank[frame]>>(8*c)) & 255 for c in range(3)],axis=-1).astype(np.uint8).view(np.int8)
            base = ROOT/'results/design_study_v1/skipping/goldens' if width == 'w24' else folder
            golden_path = base/manifest['frames'][frame]['golden_file']
            blob = raw_payload(golden_path)
            assert hashlib.sha256(blob).hexdigest() == manifest['frames'][frame]['golden_sha256']
            # The release manifest binds the compressed physical file.
            sources.add(str(golden_path.relative_to(ROOT)).replace('\\','/')+'.gz')
            layers = characterize(image, model, cases, oracle, np.load(io.BytesIO(blob), allow_pickle=False))
            sparsity.append(dict(width=width, frame=frame, layers=layers))
        print('OFFLINE_ACTIVATIONS_VERIFIED', width, flush=True)
    rows = []
    for frame in FRAMES:
        for mask in MASKS:
            means = {r['mode']:r['suppressed_ms'] for r in comparison['cells']
                     if r['state']=='skip_on' and r['frame']==frame and r['mask']==mask}
            assert len(means)==3
            indices = cases[mask]['selected_tile_indices']
            tiles = rectangles(indices,mode='tiles')
            bbox = Rect(min(t.y0 for t in tiles),min(t.x0 for t in tiles),
                        max(t.y1 for t in tiles),max(t.x1 for t in tiles)).expand(3,360,640)
            merged = [r.expand(3,360,640) for r in rectangles(indices,mode='merged_rectangles')]
            rows.append(dict(frame=frame,mask=mask,name=cases[mask]['name'],tiles=len(indices),
                merged_regions=len(merged), raster_positions=360*640,
                box_positions=bbox.area, merged_positions=sum(r.area for r in merged),
                suppressed_skip_on_ms=means,
                merged_vs_raster_percent=100*(1-means['merged']/means['raster']),
                merged_vs_box_percent=100*(1-means['merged']/means['bounding_box'])))
    summarized=[]
    for width in ('w24','w16','w12'):
        for layer in range(3):
            cells=[m for r in sparsity if r['width']==width for m in r['layers'][layer]['masks']]
            values=[c['effective_channel_issue_reduction_percent'] for c in cells]
            summarized.append(dict(width=width,layer=layer+1,
                equal_cell_issue_reduction_percent=statistics.mean(values),
                min_cell_issue_reduction_percent=min(values),max_cell_issue_reduction_percent=max(values)))
    return dict(method='Post-hoc offline analysis of the two retained interaction images and four sparse masks. Each global dependency-support position counted once, not once per overlapping crop. Effective issued channels=max(1, eligible channels), retaining the bias-only transaction. These are channel-opportunity counts, not measured cycle reductions.',
        source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sorted(sources)},
        geometry=rows, sparsity=sparsity, sparsity_summary=summarized)


def main():
    p=argparse.ArgumentParser();p.add_argument('--write',action='store_true');a=p.parse_args()
    result=compute()
    if a.write:
        assert not OUT.exists(), 'Do not overwrite derived evidence'
        OUT.parent.mkdir(parents=True,exist_ok=True)
        OUT.write_text(json.dumps(result,indent=2)+'\n',newline='\n')
    else:
        assert result == json.loads(OUT.read_text())
    print('INTERPRETATION_REPLAY_PASS', len(result['geometry']), 'geometry cells; six dense images')
    print(json.dumps(result['sparsity_summary'],indent=2))


if __name__=='__main__':main()
