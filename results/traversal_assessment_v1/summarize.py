"""Recompute the bounded baseline challenge without inferring board speedup."""
from pathlib import Path
import json
HERE=Path(__file__).resolve().parent
def summarize(data):
    assert data['passed'] and len(data['cells'])==10
    results=[]
    for state in (0,1):
        cells={c['case']:c for c in data['cells'] if c['skipping']==state}
        r,m=cells[0],cells[2]
        gap0=r['reference_cycles']-m['reference_cycles']
        gap1=r['suppressed_cycles']-m['suppressed_cycles']
        results.append(dict(skipping=state,raster_reference_cycles=r['reference_cycles'],
            raster_suppressed_cycles=r['suppressed_cycles'],merged_reference_cycles=m['reference_cycles'],
            merged_suppressed_cycles=m['suppressed_cycles'],reference_gap_cycles=gap0,
            suppressed_gap_cycles=gap1,gap_reduction_percent=100*(1-gap1/gap0),
            raster_reduction_percent=r['reduction_percent'],merged_reduction_percent=m['reduction_percent']))
    return dict(scope='Five request geometries, W24 development frame 0, both skip states; RTL loop cycles only',
        primary_top_mask_results=results,
        conclusion='Output suppression materially weakens the raster baseline; residual scanner cost remains. No independent optimized accelerator or physical service claim.',
        arithmetic_parallelism='HOLD: baseline output/traversal handling precedes another lane sweep')
if __name__=='__main__':
    output=HERE/'assessment.json';assert not output.exists()
    data=summarize(json.loads((HERE/'comparison.json').read_text()))
    output.write_text(json.dumps(data,indent=2)+'\n');print(json.dumps(data,indent=2))
