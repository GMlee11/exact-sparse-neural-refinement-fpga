"""Frozen simulation-only conventional selected-output suppression challenge."""
from pathlib import Path
import concurrent.futures, hashlib, importlib.util, json, re, subprocess, sys, time
import numpy as np

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
PILOT=ROOT/'experiments/paper2_zero_region_20261022'
sys.path.insert(0,str(PILOT))
import common
TOOLS=Path('C:/Xilinx/Vivado/2020.2/bin')

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def replace(text,old,new):
    assert text.count(old)==1,old
    return text.replace(old,new)

def suppress(text):
    text=replace(text,'    input  logic                                conv3_valid,',
        '''    input logic [63:0] selected_tile_mask,
    input logic [LR_ROW_BITS-1:0] mask_origin_row,
    input logic [LR_COLUMN_BITS-1:0] mask_origin_column,
    input  logic                                conv3_valid,''')
    text=replace(text,'    assign conv3_ready = (state == STATE_IDLE);',
        '''    wire top_selected, bottom_selected;
    sparse_hierarchical_mask_lookup #(.IMAGE_WIDTH(IMAGE_WIDTH),
        .IMAGE_HEIGHT(IMAGE_HEIGHT),.RADIUS(0),
        .COLUMN_BITS(LR_COLUMN_BITS),.ROW_BITS(LR_ROW_BITS)) top_mask (
        .selected_tile_mask(selected_tile_mask),.row(lr_row+mask_origin_row),
        .column(lr_column+mask_origin_column),.selected(top_selected));
    sparse_hierarchical_mask_lookup #(.IMAGE_WIDTH(IMAGE_WIDTH),
        .IMAGE_HEIGHT(IMAGE_HEIGHT),.RADIUS(0),
        .COLUMN_BITS(LR_COLUMN_BITS),.ROW_BITS(LR_ROW_BITS)) bottom_mask (
        .selected_tile_mask(selected_tile_mask),.row(lr_row+mask_origin_row),
        .column(bottom_drain_column+mask_origin_column),.selected(bottom_selected));
    assign conv3_ready = (state == STATE_IDLE);''')
    text=replace(text,'                state <= STATE_EMIT_TOP;',
        '''                if (top_selected) state <= STATE_EMIT_TOP;
                else if (lr_column == effective_image_width-1'b1) begin
                    bottom_drain_column <= 0;
                    state <= STATE_DRAIN_BOTTOM_READ;
                end else begin
                    lr_column <= lr_column+1'b1;
                    state <= STATE_IDLE;
                end''')
    old='''                bottom_pair_read_data <= bottom_pair_buffer[bottom_drain_column];
                state <= STATE_DRAIN_BOTTOM_LEFT;'''
    new='''                if (bottom_selected) begin
                    bottom_pair_read_data <= bottom_pair_buffer[bottom_drain_column];
                    state <= STATE_DRAIN_BOTTOM_LEFT;
                end else if (bottom_drain_column == effective_image_width-1'b1) begin
                    bottom_drain_column <= 0;
                    lr_column <= 0;
                    if (accepted_final_lr_pixel) begin
                        lr_row <= 0;
                        frame_done <= 1'b1;
                    end else lr_row <= lr_row+1'b1;
                    state <= STATE_IDLE;
                end else bottom_drain_column <= bottom_drain_column+1'b1;'''
    return replace(text,old,new)

def prepare():
    source=PILOT/'qualification/Q002'
    frozen=json.loads((source/'freeze.json').read_text())
    for n,h in frozen['files'].items():assert sha(source/n)==h,n
    order=json.loads((source/'result.json').read_text())['stages'][0]['command'][2:]
    g=common.golden_manifest();f=g['frames'][0]
    image=np.fromfile(common.GOLDEN/'input_banks.bin',dtype='<u4').reshape(4,360,640)[0]
    golden=np.load(common.GOLDEN/f['golden_file'],allow_pickle=False)
    assert sha(common.GOLDEN/f['golden_file'])==f['golden_sha256']
    cases=[([0,2],0),([0,2],1),([0,2],2),([57,59],1),([57,59],2)]
    desc=[len(cases)];ins=[];outs=[]
    for indices,mode in cases:
        regions=common.regions(indices,mode);mask=sum(1<<i for i in indices)
        desc.extend([mask&0xffffffff,mask>>32,len(regions)])
        for box,owned in regions:
            ownedmask=sum(1<<i for i in owned)
            take=common.union_mask(common.rectangles(owned),3,360,640)
            scope=np.zeros_like(take);scope[box.y0:box.y1,box.x0:box.x1]=True;take &= scope
            want=common.union_mask(common.rectangles(owned),0,360,640).repeat(2,0).repeat(2,1)
            src,expected=image[take],golden[want]
            desc.extend([box.x0,box.y0,box.x1-box.x0,box.y1-box.y0,ownedmask&0xffffffff,
                ownedmask>>32,len(src),len(expected),len(ins),len(outs)])
            ins.extend(src.tolist());outs.extend(expected.tolist())
    for variant in ('reference','suppressed'):
        folder=HERE/variant;folder.mkdir(exist_ok=False)
        for name in order:
            text=(source/name).read_text()
            if variant=='suppressed':
                if name=='espcn_streaming_pixel_shuffle_rgb.sv':text=suppress(text)
                if name=='paper2_origin_core.sv':
                    text=replace(text,'        .conv3_valid(conv3_valid),',
                        '''        .selected_tile_mask(selected_tile_mask),
        .mask_origin_row(mask_origin_row),.mask_origin_column(mask_origin_column),
        .conv3_valid(conv3_valid),''')
            (folder/name).write_text(text)
        for name,values in [('descriptors',desc),('inputs',ins),('outputs',outs)]:
            (folder/f'integration_{name}.mem').write_text(''.join(f'{v:08x}\n' for v in values))
        (folder/'freeze.json').write_text(json.dumps(dict(cases=cases,order=order,
            selected_words_per_mode=len(outs),source_hashes=frozen['files'],
            files={p.name:sha(p) for p in folder.iterdir() if p.is_file()},
            protocol_sha256=sha(HERE/'PROTOCOL.txt'),script_sha256=sha(__file__)),indent=2)+'\n')
    return order

def run(variant,order):
    folder=HERE/variant;stages=[];passed=False;raw=''
    commands=[['xvlog.bat','--sv',*order],['xelab.bat','tb_roi_integration','-s','integrated'],
              ['xsim.bat','integrated','-runall']]
    for i,cmd in enumerate(commands):
        cmd[0]=str(TOOLS/cmd[0]);start=time.monotonic()
        with (folder/f'stage{i}.log').open('xb') as log:
            proc=subprocess.Popen(cmd,cwd=folder,stdout=log,stderr=subprocess.STDOUT)
            try:rc=proc.wait(timeout=1200)
            except subprocess.TimeoutExpired:
                subprocess.run(['taskkill','/PID',str(proc.pid),'/T','/F'],capture_output=True)
                proc.wait(timeout=15);rc='timeout'
        raw=(folder/f'stage{i}.log').read_text(errors='replace')
        stages.append(dict(command=cmd,exit=rc,seconds=time.monotonic()-start))
        print(variant,i,rc,raw[-1400:],flush=True)
        if rc!=0:break
        if i==2:passed='PAPER2_ROI_INTEGRATION_PASS' in raw and 'Fatal:' not in raw
    requests=re.findall(r'AXI_REQUEST_PASS case=(\d+) regions=(\d+) service_cycles=(\d+) execution_loop_cycles=(\d+)',raw)
    freeze=json.loads((folder/'freeze.json').read_text())
    passed=passed and len(requests)==10 and raw.count('AXI_FAILURE_PASS')==10
    passed=passed and all(sha(folder/n)==h for n,h in freeze['files'].items())
    result=dict(passed=passed,stages=stages,requests=requests,board_access=False,
                selected_words_per_mode=freeze['selected_words_per_mode'])
    (folder/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    return result

if __name__=='__main__':
    order=prepare()
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        results=dict(zip(('reference','suppressed'),pool.map(lambda v:run(v,order),('reference','suppressed'))))
    assert all(r['passed'] for r in results.values()),'Retained failed simulation; inspect logs'
    cells=[]
    for i,(a,b) in enumerate(zip(results['reference']['requests'],results['suppressed']['requests'])):
        assert a[:2]==b[:2]
        cells.append(dict(skipping=i//5,case=int(a[0]),regions=int(a[1]),
            reference_cycles=int(a[3]),suppressed_cycles=int(b[3]),
            reduction_percent=100*(1-int(b[3])/int(a[3]))))
    (HERE/'comparison.json').write_text(json.dumps(dict(passed=True,cells=cells,
        scope='RTL loop cycles, not physical complete service; existing development input'),indent=2)+'\n')
    print(json.dumps(cells,indent=2))
