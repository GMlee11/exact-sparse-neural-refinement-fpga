"""Replay unchanged Q001 bytes after fixing a checker-only default-mode error.

The original failed analysis and original source snapshots remain intact.
No firmware, timing boundary, workload, board data or golden is changed.
"""
import json
import numpy as np
from common import HERE, GOLDEN, golden_manifest, sha
from analyze import parse


def main():
    out=HERE/'physical/Q001';dest=out/'analysis_corrected.json'
    if dest.exists():raise FileExistsError(dest)
    manifest=json.loads((out/'launch_manifest.json').read_text())
    changes=[]
    from pathlib import Path
    for p in [manifest['image'],manifest['xsa'],manifest['firmware'],*manifest['scripts'],*manifest['pins']]:
        current=sha(p['path'])
        if current!=p['sha256']:
            name=Path(p['path']).name
            assert name in ['common.py','test_pilot.py','physical.py']
            snapshot=HERE/'corrections/checker_v1'/name
            assert sha(snapshot)==p['sha256']
            changes.append(dict(file=name,original_sha256=p['sha256'],corrected_sha256=current,
                                original_snapshot=str(snapshot)))
    assert {c['file'] for c in changes}=={'common.py','test_pilot.py','physical.py'}
    g=golden_manifest();goldens={}
    for fi in (0,2):
        f=g['frames'][fi];assert sha(GOLDEN/f['golden_file'])==f['golden_sha256']
        goldens[fi]=np.load(GOLDEN/f['golden_file'],mmap_mode='r',allow_pickle=False)
    capture=json.loads((out/'capture_record.json').read_text())
    assert capture['status']=='CAPTURED' and capture['terminal'] and capture['serial_closed']
    data=np.fromfile(out/'records.bin',dtype='<u4');archive=np.fromfile(out/'archive.bin',dtype='<u4')
    result=parse(data,archive,manifest,g,goldens)
    result.update(correction='Explicit merged_rectangles mode in checker; previous default was tiles',
        original_failed_analysis_sha256=sha(out/'analysis.json'),source_changes=changes,
        unchanged_capture_sha256={n:sha(out/n) for n in ['records.bin','archive.bin','launch_manifest.json','capture_record.json']},
        replay_source_sha256=sha(__file__))
    dest.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(passed=result['passed'],records=len(result['records']),archives=result['byte_archives'])))


if __name__=='__main__':main()
