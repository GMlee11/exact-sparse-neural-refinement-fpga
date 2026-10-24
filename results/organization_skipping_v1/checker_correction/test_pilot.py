"""Local tests use explicitly synthetic mailbox records, never physical evidence."""
import collections
import importlib.util
import sys
from pathlib import Path
import numpy as np
import pytest

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from common import CASE_IDS, GOLDEN, golden_manifest, regions, rectangles, union_mask, schedule
from build_firmware import derive
spec=importlib.util.spec_from_file_location('zero_region_analysis',HERE/'analyze.py')
analysis=importlib.util.module_from_spec(spec);spec.loader.exec_module(analysis)


def test_balanced_arm_positions():
    for kind in [0,1]:
        size=3 if kind==0 else 6
        rows=list(schedule(kind,0,6))
        for case in CASE_IDS:
            groups=[rows[i:i+size] for i in range(0,len(rows),size) if rows[i]['case']==case]
            assert len(groups)==6
            for slot in range(size):
                counts=collections.Counter((g[slot]['condition'],g[slot]['mode']) for g in groups)
                assert set(counts.values())=={6//size}


def test_geometry_and_archive_bounds():
    g=golden_manifest()
    total=0
    for case in CASE_IDS:
        indices=g['cases'][case]['selected_tile_indices']
        want=union_mask(rectangles(indices),0,360,640)
        for mode in range(3):
            owned=[]
            for box,ids in regions(indices,mode):
                owned+=ids
                deps=union_mask(rectangles(ids),3,360,640)
                assert int(deps.sum())==int(deps[box.y0:box.y1,box.x0:box.x1].sum())
            assert sorted(owned)==sorted(indices) and len(owned)==len(set(owned))
            assert (union_mask(rectangles(owned),0,360,640)==want).all()
        total+=g['cases'][case]['expected_words']*6
    assert total==24514560 and total<0x04000000


def test_unchanged_data_functions():
    from common import C07
    original=(C07/'board_campaign.c').read_text();new=derive()
    for start,end in [('static unsigned plan(', '/* Merge selected halo'),
                      ('static unsigned pack(', 'static unsigned scatter('),
                      ('static unsigned scatter(', 'static int dma_init('),
                      ('static unsigned save_bytes(', 'static void publish_flush(')]:
        assert original[original.index(start):original.index(end)]==new[new.index(start):new.index(end)]
    assert '#define RECORD_WORDS 44U' in new and 'profiling!=(operation==2U)' in new


def synthetic_mailbox(monkeypatch):
    ids=(0,2)
    monkeypatch.setattr(analysis,'CASE_IDS',ids)
    # Keep a separate schedule so a synthetic test does not use production global IDs.
    def fake_schedule(kind,base=0,repeats=3):
        for rep in range(repeats):
            for j,case in enumerate(ids):
                for order in range(3):
                    yield dict(case=case,mode=(j+base+rep+order)%3,repeat=base+rep,condition=0)
    monkeypatch.setattr(analysis,'schedule',fake_schedule)
    g=golden_manifest();golden=np.load(GOLDEN/g['frames'][0]['golden_file'],allow_pickle=False)
    m=dict(kind=0,base=0,operation=0,ordinal=0,initial_bank=0)
    order=list(fake_schedule(0));data=np.zeros(32+44*len(order),dtype='<u4')
    data[0]=0x5a523031;data[1]=1;data[2]=len(order);data[4]=333333343
    data[5]=2;data[6]=3;data[8]=1;data[9]=6;data[16:20]=[f['input_word_fnv'] for f in g['frames']]
    data[21]=44;data[22]=len(order);data[25]=50000000
    archive=[];cursor=0
    for i,w in enumerate(order):
        raw=data[32+i*44:32+(i+1)*44];case=w['case'];c=g['cases'][case]
        indices=c['selected_tile_indices'];regs=regions(indices,w['mode'])
        raw[:3]=[case,w['mode'],w['repeat']];raw[4]=len(regs)
        raw[5]=sum(int(union_mask(rectangles(owned),3,360,640)[b.y0:b.y1,b.x0:b.x1].sum()) for b,owned in regs)
        raw[6]=c['expected_words'];raw[7]=6;raw[8]=1000
        for k in [10,12,14,16]:raw[k]=100
        raw[19]=c['expected_fnv'];raw[20]=0xffffffff;raw[21]=c['expected_words']
        fid=6+i+1;bank=fid&1;raw[22]=fid;raw[23]=len(regs);raw[24]=bank;raw[25]=(fid<<1)|bank
        if w['repeat']==0:
            take=union_mask(rectangles(indices),0,360,640).repeat(2,0).repeat(2,1)
            words=golden[take].reshape(-1);raw[20]=cursor;cursor+=len(words);archive.extend(words.tolist())
    data[3]=cursor;data[7]=data[-19]
    return data,np.array(archive,dtype='<u4'),m,g,{0:golden}


def test_parser_accepts_valid_synthetic_record(monkeypatch):
    result=analysis.parse(*synthetic_mailbox(monkeypatch))
    assert result['passed'] and result['byte_archives']==6


@pytest.mark.parametrize('corruption',['pixel','schedule','failed_terminal','unexpected_profile'])
def test_parser_rejects_corruption(monkeypatch,corruption):
    data,archive,m,g,goldens=synthetic_mailbox(monkeypatch)
    if corruption=='pixel':archive[0]^=1
    elif corruption=='schedule':data[33]=2
    elif corruption=='failed_terminal':data[1]=0x80000003
    else:data[32+28]=1
    with pytest.raises(AssertionError):analysis.parse(data,archive,m,g,goldens)


def test_summary_retains_zero_interaction_and_losses():
    from summarize import summarize
    rows=[]
    # A known synthetic adverse result: merged is slower; skipping has no
    # interaction because it scales every organization equally.
    for case in CASE_IDS:
        for condition,factor in [('reference',1.0),('skip_off',1.2),('skip_on',0.8)]:
            for mode,time in [('raster',10.0),('bounding_box',8.0),('merged',9.0)]:
                for repeat in range(6):
                    rows.append(dict(case=case,condition=condition,mode=mode,repeat=repeat,service_ms=factor*time))
    result=summarize(rows)
    for case in result['cases']:
        for segment in case['segments']:
            assert segment['merged_saving_percent']['skip_on']['bounding_box']<0
            assert abs(segment['organization_skip_interaction_percentage_points']['bounding_box'])<1e-10
