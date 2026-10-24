"""Frozen equal-cell analysis of the W24 output-suppression board comparison."""
import json
from collections import defaultdict
from statistics import mean
from common import HERE, FRAMES, MASKS, sha

RUNS = {'P001': 'original', 'P002': 'suppressed',
        'P003': 'suppressed', 'P004': 'original'}
STATES = ('skip_off', 'skip_on')
MODES = ('raster', 'bounding_box', 'merged')
SPARSE = (2, 5, 4, 10)


def compute(analyses, manifests):
    cells = defaultdict(list)
    legs = defaultdict(list)
    for run, implementation in RUNS.items():
        a, m = analyses[run], manifests[run]
        assert a['passed'] and len(a['records']) == 216
        assert m['implementation'] == implementation and m['operation'] == 0
        assert a['byte_archives'] == (72 if run in ('P001', 'P002') else 0)
        leg = 0 if run in ('P001', 'P002') else 1
        for r in a['records']:
            key = (implementation, r['condition'], r['mode'], r['frame'], r['mask'])
            cells[key].append(r['service_ms'])
            legs[(leg, *key)].append(r['service_ms'])
    assert len(cells) == 144 and all(len(v) == 6 for v in cells.values())
    assert len(legs) == 288 and all(len(v) == 3 for v in legs.values())
    per_cell = []
    summaries = []
    for state in STATES:
        for mode in MODES:
            for frame in FRAMES:
                for mask in MASKS:
                    old = mean(cells[('original', state, mode, frame, mask)])
                    new = mean(cells[('suppressed', state, mode, frame, mask)])
                    per_cell.append(dict(state=state, mode=mode, frame=frame, mask=mask,
                        original_ms=old, suppressed_ms=new, saved_ms=old-new,
                        reduction_pct=100*(old-new)/old))
            subset = [r for r in per_cell if r['state'] == state and
                      r['mode'] == mode and r['mask'] in SPARSE]
            old, new = (mean(r[k] for r in subset) for k in ('original_ms', 'suppressed_ms'))
            leg_results = []
            for leg in (0, 1):
                x, y = (mean(mean(legs[(leg, impl, state, mode, f, mask)])
                             for f in FRAMES for mask in SPARSE)
                        for impl in ('original', 'suppressed'))
                leg_results.append(dict(leg=leg, original_ms=x, suppressed_ms=y,
                                        saved_ms=x-y, reduction_pct=100*(x-y)/x))
            summaries.append(dict(state=state, mode=mode, original_ms=old,
                suppressed_ms=new, saved_ms=old-new, reduction_pct=100*(old-new)/old,
                cells_slower=sum(r['saved_ms'] < 0 for r in subset), legs=leg_results))
    gaps = []
    for state in STATES:
        by_mode = {r['mode']: r for r in summaries if r['state'] == state}
        old = by_mode['raster']['original_ms']-by_mode['merged']['original_ms']
        new = by_mode['raster']['suppressed_ms']-by_mode['merged']['suppressed_ms']
        gaps.append(dict(state=state, original_raster_minus_merged_ms=old,
            suppressed_raster_minus_merged_ms=new, gap_reduction_pct=100*(old-new)/old,
            suppressed_merged_vs_raster_pct=100*new/by_mode['raster']['suppressed_ms'],
            suppressed_merged_vs_bbox_pct=100*(by_mode['bounding_box']['suppressed_ms']-
                by_mode['merged']['suppressed_ms'])/by_mode['bounding_box']['suppressed_ms']))
    return dict(passed=True, primary_records=864, primary_archives=144,
                sparse_summaries=summaries, organization_gaps=gaps, cells=per_cell,
                independent_sessions=1, statistical_significance_claim=False)


def main():
    out = HERE/'comparison.json'
    if out.exists():
        raise FileExistsError('Preserve existing analysis')
    analyses = {r: json.loads((HERE/'physical'/r/'analysis.json').read_text()) for r in RUNS}
    manifests = {r: json.loads((HERE/'physical'/r/'launch_manifest.json').read_text()) for r in RUNS}
    result = compute(analyses, manifests)
    for q in ('Q001', 'Q002'):
        qualification = json.loads((HERE/'physical'/q/'analysis.json').read_text())
        assert qualification['passed'] and len(qualification['records']) == 72
        assert qualification['byte_archives'] == 72
    result['qualification_records'] = 144
    result['qualification_archives'] = 144
    result['build'] = json.loads((HERE/'build/result.json').read_text())
    result['bindings'] = {str(p.relative_to(HERE)): sha(p) for p in
        [HERE/'PROTOCOL.txt', HERE/'summarize.py', *[HERE/'physical'/r/'analysis.json'
                                                  for r in (*RUNS, 'Q001', 'Q002')]]}
    out.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({k: v for k, v in result.items() if k not in ('cells', 'bindings', 'build')}, indent=2))


if __name__ == '__main__':
    main()
