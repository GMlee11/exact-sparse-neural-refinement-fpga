"""Prospective C07 ABBA analysis; preserves every case and repeat.

Descriptive engineering comparison, not independent-sample significance testing.
Consumes independently numerically qualified per-launch reports, never edits them.
"""
from collections import Counter, defaultdict
import argparse
import hashlib
import json
import math
from pathlib import Path
from statistics import mean

CONDITIONS = ('reference_B001', 'C07_zero_off', 'C07_zero_on')
SCHEDULE = {'P001': ((CONDITIONS[0],), range(3)),
            'P002': (CONDITIONS[1:], range(3)),
            'P003': (CONDITIONS[1:], range(3, 6)),
            'P004': ((CONDITIONS[0],), range(3, 6))}


def summarize(reports):
    if len(reports) != 4:
        raise ValueError('Exactly four frozen ABBA launch reports required')
    rows = []
    seen_launches = set()
    for report in reports:
        assert report['pass'] is True
        assert report['prospective_schedule_verified'] is True
        assert abs(report['fabric_hz'] - 50_000_000) < 1
        launch_rows = report['records']
        ids = {r['launch_id'] for r in launch_rows}
        assert len(ids) == 1
        launch = ids.pop()
        assert launch in SCHEDULE and launch not in seen_launches
        seen_launches.add(launch)
        conditions, repeats = SCHEDULE[launch]
        assert len(launch_rows) == len(conditions)*len(repeats)*4*17
        for r in launch_rows:
            assert r['condition'] in conditions and r['global_repeat'] in repeats
            assert r['event_outcome'] == 'committed' and r['rc'] == 0
            assert r['mode'] == 'merged_rectangles'
            assert r['case_index'] == r['frame_index']*17+r['mask_index']
            assert r['private_bank'] in (0, 1)
            assert math.isfinite(r['service_ms']) and r['service_ms'] >= 0
            expected_enable = 3 if r['condition'] == 'C07_zero_on' else 0
            assert r['zero_enable_readback'] == expected_enable
            if r['global_repeat'] == 0:
                assert r['byte_archive_pass'] is True
            else:
                assert r['byte_archive_pass'] is None
        rows.extend(launch_rows)
    assert seen_launches == set(SCHEDULE)
    by = defaultdict(list)
    names = {}
    unique = set()
    for r in rows:
        key = (r['condition'], r['frame_index'], r['mask_index'], r['global_repeat'])
        assert key not in unique
        unique.add(key)
        cell = key[:3]
        by[cell].append(r)
        mi = r['mask_index']
        assert mi not in names or names[mi] == r['mask_name']
        names[mi] = r['mask_name']
    assert len(unique) == 1224
    assert set(names) == set(range(17))
    assert names[0].startswith('empty_control') and names[1].startswith('dense_control')
    for c in CONDITIONS:
        for fi in range(4):
            for mi in range(17):
                records = by[c, fi, mi]
                assert {r['global_repeat'] for r in records} == set(range(6))
                assert Counter(r['private_bank'] for r in records) == {0: 3, 1: 3}
    assert sum(r['byte_archive_pass'] is True for r in rows) == 204
    cells = []
    for fi in range(4):
        for mi in range(17):
            values = {c: mean(r['service_ms'] for r in by[c, fi, mi]) for c in CONDITIONS}
            assert values[CONDITIONS[0]] > 0 and values[CONDITIONS[1]] > 0
            cells.append({'frame_index': fi, 'mask_index': mi, 'mask_name': names[mi],
                'mean_service_ms': values,
                'on_vs_reference_percent': 100*(values[CONDITIONS[2]]/values[CONDITIONS[0]]-1),
                'on_vs_off_percent': 100*(values[CONDITIONS[2]]/values[CONDITIONS[1]]-1)})
    sparse = [x for x in cells if x['mask_index'] >= 2]
    def aggregate(items):
        return {'cases': len(items),
            'mean_case_percent_change_on_vs_reference': mean(x['on_vs_reference_percent'] for x in items),
            'reference_regressions': sum(x['on_vs_reference_percent'] > 0 for x in items),
            'worst_case_percent_change_on_vs_reference': max(x['on_vs_reference_percent'] for x in items),
            'mean_case_percent_change_on_vs_off': mean(x['on_vs_off_percent'] for x in items),
            'mean_service_ms': {c: mean(x['mean_service_ms'][c] for x in items) for c in CONDITIONS}}
    paired = []
    for repeat in range(6):
        rr = [r for r in rows if r['global_repeat'] == repeat and r['mask_index'] >= 2]
        vals = {c: mean(r['service_ms'] for r in rr if r['condition'] == c) for c in CONDITIONS}
        paired.append({'global_repeat': repeat, 'mean_service_ms': vals,
                       'on_vs_reference_percent': 100*(vals[CONDITIONS[2]]/vals[CONDITIONS[0]]-1)})
    return {'pass': True, 'records': len(rows), 'byte_archives': 204,
            'all_case_condition_bank_balance_verified': True,
            'interpretation': 'Negative percentage means faster. Descriptive development comparison; four programming launches, not six independent physical sessions.',
            'primary_equal_frame_mask_sparse': aggregate(sparse),
            'per_frame_sparse': {str(fi): aggregate([x for x in sparse if x['frame_index'] == fi]) for fi in range(4)},
            'dense_separate': aggregate([x for x in cells if x['mask_index'] == 1]),
            'empty_separate': aggregate([x for x in cells if x['mask_index'] == 0]),
            'paired_repeats': paired, 'all_cells_including_regressions': cells}


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('reports', nargs=4, type=Path)
    p.add_argument('--output', required=True, type=Path)
    args = p.parse_args()
    result = summarize([json.loads(f.read_text()) for f in args.reports])
    result['input_report_sha256'] = {str(f.resolve()): hashlib.sha256(f.read_bytes()).hexdigest() for f in args.reports}
    result['analysis_source_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    with args.output.open('x', encoding='utf-8') as f:
        json.dump(result, f, indent=2)
        f.write('\n')
    print(json.dumps(result['primary_equal_frame_mask_sparse'], indent=2))
