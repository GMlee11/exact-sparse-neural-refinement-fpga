"""Prespecified effect-size summary. No significance or novelty certification."""
import json
import statistics
from common import HERE, CASE_IDS, sha


def summarize(rows):
    cells={}
    for row in rows:
        key=(row['case'],row['condition'],row['mode'])
        cells.setdefault(key,[]).append(row)
    assert len(cells)==len(CASE_IDS)*9
    for values in cells.values():
        assert sorted(r['repeat'] for r in values)==list(range(6))
    records=[]
    for case in CASE_IDS:
        item=dict(case=case,control=case%17 in (0,1),segments=[])
        for segment,reps in [('all',range(6)),('first_leg',range(3)),('second_leg',range(3,6))]:
            means={(cond,mode):statistics.mean(r['service_ms'] for r in cells[case,cond,mode] if r['repeat'] in reps)
                   for cond in ['reference','skip_off','skip_on'] for mode in ['raster','bounding_box','merged']}
            gains={}
            for cond in ['reference','skip_off','skip_on']:
                gains[cond]={baseline:100*(1-means[cond,'merged']/means[cond,baseline]) for baseline in ['raster','bounding_box']}
            item['segments'].append(dict(segment=segment,
                mean_service_ms={c:{m:means[c,m] for m in ['raster','bounding_box','merged']} for c in gains},
                merged_saving_percent=gains,
                organization_skip_interaction_percentage_points={m:gains['skip_on'][m]-gains['skip_off'][m] for m in ['raster','bounding_box']},
                skip_on_saving_vs_reference_percent={m:100*(1-means['skip_on',m]/means['reference',m]) for m in ['raster','bounding_box','merged']}))
        records.append(item)
    return dict(scope='Exploratory fixed development cases; ABBA legs are not independent sessions',
                cases=records,no_automatic_advancement=True)


def main():
    dest=HERE/'pilot_summary.json'
    if dest.exists():raise FileExistsError(dest)
    rows=[];pins={}
    for i in range(1,5):
        p=HERE/f'physical/P{i:03}/analysis.json';d=json.loads(p.read_text())
        assert d['passed'] and d['purpose']=='exploratory_primary'
        rows+=d['records'];pins[str(p)]=sha(p)
    result=summarize(rows);result['source_sha256']=pins;result['summarizer_sha256']=sha(__file__)
    dest.write_text(json.dumps(result,indent=2)+'\n')
    print(str(dest))


if __name__=='__main__':main()
