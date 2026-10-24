"""Independent geometry, bytes and schedule replay for the exploratory pilot."""
import argparse
import json
import traceback
import numpy as np
from common import HERE, GOLDEN, CASE_IDS, RECORD_WORDS, golden_manifest, regions, schedule, sha, union_mask, rectangles

NAMES=['reference','skip_off','skip_on']
MODES=['raster','bounding_box','merged']
STAGES=['request_setup_ms','region_setup_ms','accelerator_kick_ms','cache_flush_ms',
        'dma_mmio_ms','wait_ms','validation_ms','publication_ms']


def u64(row,k):return int(row[k])+(int(row[k+1])<<32)


def parse(data, archive, manifest, g, goldens):
    assert len(data)>=32 and int(data[0])==0x5a523031
    assert int(data[1])==1, 'Firmware did not complete successfully'
    count=int(data[2]);assert len(data)==32+count*RECORD_WORDS
    assert len(archive)==int(data[3])
    kind=manifest['kind'];base=manifest['base'];operation=manifest['operation']
    repeats=1 if operation else 3
    order=list(schedule(kind,base,repeats));assert count==len(order)
    warmups=len(CASE_IDS)*(6 if kind else 3)
    assert list(map(int,data[[5,6,8,9,11,12,13,14,15,21,22,23,25]]))==[
        len(CASE_IDS),repeats,1,warmups,manifest['ordinal'],kind,base,operation,
        manifest['initial_bank'],44,len(order),int(operation==2),50000000]
    assert list(map(int,data[16:20]))==[f['input_word_fnv'] for f in g['frames']]
    freq=int(data[4]);assert abs(freq-333333343.5)<2
    rows=[];cursor=0;archives=0
    for i,(raw,want) in enumerate(zip(data[32:].reshape(-1,44),order)):
        case,mode,rep,condition=map(int,raw[[0,1,2,26]])
        assert (case,mode,rep,condition)==tuple(want[k] for k in ['case','mode','repeat','condition'])
        c=g['cases'][case];indices=c['selected_tile_indices'];regs=regions(indices,mode)
        inputs=0
        for box,owned in regs:
            take=union_mask(rectangles(owned),3,360,640)
            inputs+=int(take[box.y0:box.y1,box.x0:box.x1].sum())
        assert int(raw[3])==0 and int(raw[4])==len(regs) and int(raw[5])==inputs
        assert int(raw[6])==c['expected_words'] and int(raw[21])==c['expected_words']
        assert int(raw[7])&4 and not(int(raw[7])&17)
        assert int(raw[19])==c['expected_fnv'] and int(raw[23])==len(regs)
        fid=warmups+i+1;bank=manifest['initial_bank']^((warmups+i+1)&1)
        assert int(raw[22])==fid and int(raw[24])==bank and int(raw[25])==(fid<<1)|bank
        assert int(raw[27])==(3 if condition==2 else 0)
        if rep==0 and operation!=2:
            assert int(raw[20])==cursor
            take=union_mask(rectangles(indices),0,360,640).repeat(2,0).repeat(2,1)
            expected=goldens[c['frame_index']][take].reshape(-1)
            assert np.array_equal(archive[cursor:cursor+len(expected)],expected),'Archived pixel mismatch'
            cursor+=len(expected);archives+=1
        else:assert int(raw[20])==0xffffffff
        service=u64(raw,8);parts=[u64(raw,k) for k in (10,12,14,16)]
        assert service>=sum(parts)
        detail=[u64(raw,28+2*k) for k in range(8)]
        if operation!=2:assert not any(detail)
        else:assert sum(detail)+parts[0]+parts[1]+parts[3]<=service
        row=dict(case=case,frame=c['frame_index'],mask=c['mask_index'],condition=NAMES[condition],
            mode=MODES[mode],repeat=rep,regions=len(regs),input_words=inputs,
            service_ms=service*1000/freq,planning_ms=parts[0]*1000/freq,
            packing_ms=parts[1]*1000/freq,dma_and_engine_ms=parts[2]*1000/freq,
            scatter_ms=parts[3]*1000/freq,other_ms=(service-sum(parts))*1000/freq)
        row.update({k:t*1000/freq for k,t in zip(STAGES,detail)})
        rows.append(row)
    assert cursor==len(archive)
    assert int(data[7])==int(data[-44+25])
    return dict(passed=True,records=rows,byte_archives=archives,
        purpose='qualification' if operation==1 else 'diagnostic_profile' if operation==2 else 'exploratory_primary',
        not_held_out=True)


def main():
    p=argparse.ArgumentParser();p.add_argument('--run-id',required=True);a=p.parse_args()
    if not (a.run_id[:1] in 'QPR' and a.run_id[1:].isdigit()):raise ValueError('Run ID')
    out=HERE/'physical'/a.run_id
    if (out/'analysis.json').exists():raise FileExistsError('Do not overwrite analysis')
    try:
        m=json.loads((out/'launch_manifest.json').read_text())
        for pin in [m['image'],m['xsa'],m['firmware'],*m['scripts'],*m['pins']]:
            assert sha(pin['path'])==pin['sha256'],pin['path']
        capture=json.loads((out/'capture_record.json').read_text())
        assert capture['status']=='CAPTURED' and capture['terminal'] and capture['serial_closed']
        g=golden_manifest();goldens={}
        for fi in {g['cases'][c]['frame_index'] for c in CASE_IDS}:
            f=g['frames'][fi];assert sha(GOLDEN/f['golden_file'])==f['golden_sha256']
            goldens[fi]=np.load(GOLDEN/f['golden_file'],mmap_mode='r',allow_pickle=False)
        data=np.fromfile(out/'records.bin',dtype='<u4')
        archive=np.fromfile(out/'archive.bin',dtype='<u4') if (out/'archive.bin').exists() else np.array([],dtype='<u4')
        result=parse(data,archive,m,g,goldens)
    except Exception as e:
        result=dict(passed=False,error=repr(e),traceback=traceback.format_exc())
    result['analyzer_sha256']=sha(__file__)
    (out/'analysis.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='records'}))
    raise SystemExit(0 if result['passed'] else 1)


if __name__=='__main__':main()
