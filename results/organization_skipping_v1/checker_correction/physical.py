"""Prepare pinned RAM-only launch scripts. Never executes them or contacts hardware."""
import argparse
import json
import struct
import zipfile
import xml.etree.ElementTree as ET
from common import HERE, ROOT, C07, BRAM, GOLDEN, CASE_IDS, golden_manifest, pin, sha, schedule


def main():
    p=argparse.ArgumentParser();p.add_argument('--run-id',choices=['Q001','P001','P002','P003','P004','R001'],required=True);a=p.parse_args()
    assert json.loads((HERE/'qualification/Q002/result.json').read_text())['passed']
    assert json.loads((HERE/'firmware/F002/result.json').read_text())['compiled']
    operation=1 if a.run_id=='Q001' else 2 if a.run_id=='R001' else 0
    ordinal=int(a.run_id[1:])-1 if not operation else 99 if operation==1 else 100
    kind=1 if operation or ordinal in (1,2) else 0
    base=3 if not operation and ordinal>=2 else 0
    initial=int(ordinal==3)
    if not operation or operation==2:
        assert json.loads((HERE/'physical/Q001/analysis.json').read_text())['passed']
    if operation==2:
        assert all(json.loads((HERE/f'physical/P{i:03}/analysis.json').read_text())['passed'] for i in range(1,5))
    build=(C07 if kind else BRAM)/'runs/B001'
    bit=build/'paper2_roi_v1.bit';xsa=build/'paper2_roi_v1.xsa'
    assert sha(bit)==('c6ddd8f79637e59f22984cf1bb4e890ef91430acecdda23fbee0b4f55adf4b84' if kind else '5a18f276213cbeffff09db65babc22a06aa49155192391deb18f57c1d9c9beda')
    with zipfile.ZipFile(xsa) as z:
        hwh=[n for n in z.namelist() if n.endswith('.hwh')];assert len(hwh)==1
        xml=ET.fromstring(z.read(hwh[0]));init=z.read('ps7_init.tcl')
    params={e.attrib['NAME']:e.attrib.get('VALUE') for e in xml.iter('PARAMETER')}
    assert abs(float(params['PCW_ACT_FPGA0_PERIPHERAL_FREQMHZ'])-50)<0.0001
    assert abs(float(params['PCW_ACT_APU_PERIPHERAL_FREQMHZ'])-666.666687)<0.0001
    regs={e.attrib['INSTANCE']:e.attrib['BASEVALUE'] for e in xml.iter('MEMRANGE') if e.attrib.get('MEMTYPE')=='REGISTER'}
    assert regs=={'dma':'0x40400000','cfg_gpio':'0x41200000','rsp_gpio':'0x41210000'}
    g=golden_manifest();repeats=1 if operation else 3
    expected=list(schedule(kind,base,repeats))
    archive_words=sum(g['cases'][w['case']]['expected_words'] for w in expected if w['repeat']==0 and operation!=2)
    assert archive_words<=0x04000000
    out=HERE/'physical'/a.run_id;out.mkdir(parents=True,exist_ok=False)
    (out/'ps7_init.tcl').write_bytes(init)
    config=out/'launch_config.bin'
    config.write_bytes(struct.pack('<8I',0x5a523031,operation,kind,base,initial,ordinal,len(expected),int(operation==2)))
    elf=HERE/'firmware/F002/campaign.elf'
    assert sha(elf)==json.loads((HERE/'firmware/F002/result.json').read_text())['elf_sha256']
    (out/'program.tcl').write_text(f'''# Volatile configuration only. Run only after user connects the Zybo.
connect -url tcp:127.0.0.1:3121
if {{![string match "*210351BDF8A6A*" [jtag targets]]}} {{error "Expected Zybo cable absent"}}
if {{[llength [targets -target-properties -filter {{name =~ "APU*"}}]] != 1}} {{error "Ambiguous APU"}}
targets -set -filter {{name =~ "APU*"}}
rst -system
after 2000
fpga -file {{{bit.as_posix()}}}
source {{{(out/'ps7_init.tcl').as_posix()}}}
ps7_init
ps7_post_config
targets -set -filter {{name =~ "*A9*#0"}}
rst -processor
after 1000
dow {{{elf.as_posix()}}}
dow -data {{{(GOLDEN/'input_banks.bin').as_posix()}}} 0x18000000
dow -data {{{config.as_posix()}}} 0x05100000
con
puts "ROI_LAUNCH_COMPLETE"
disconnect
exit
''')
    (out/'dump.tcl').write_text(f'''connect -url tcp:127.0.0.1:3121
if {{![string match "*210351BDF8A6A*" [jtag targets]]}} {{error "Wrong cable"}}
targets -set -filter {{name =~ "*A9*#0"}}
stop
set records [lindex [mrd -value 0x05000008] 0]
set words [lindex [mrd -value 0x0500000c] 0]
if {{$records<0 || $records>{len(expected)} || $words<0 || $words>0x04000000}} {{error "Invalid mailbox bounds"}}
mrd -bin -file {{{(out/'records.bin').as_posix()}}} 0x05000000 [expr {{32+$records*44}}]
if {{$words>0}} {{mrd -bin -file {{{(out/'archive.bin').as_posix()}}} 0x06000000 $words}}
puts "ROI_CAPTURE_DONE records=$records words=$words"
disconnect
exit
''')
    capture=(ROOT/'scripts/paper2_conventional_comparison_v1/capture_board.ps1').read_text()
    capture=capture.replace("if($RunId -notmatch '^P[0-9]+$'){throw 'Explicit physical run ID required'}",
        "if($RunId -ne '"+a.run_id+"'){throw 'Wrong run ID'}")
    capture=capture.replace("$p2Root=(Resolve-Path (Join-Path $PSScriptRoot '../..')).Path","$p2Root='"+str(ROOT)+"'")
    capture=capture.replace('$p2Out=Join-Path $p2Root "results/paper2_conventional_comparison_v1/$RunId"',"$p2Out='"+str(out)+"'")
    capture=capture.replace('@($p2Manifest.image,$p2Manifest.xsa,$p2Manifest.firmware)+$p2Manifest.scripts',
        '@($p2Manifest.image,$p2Manifest.xsa,$p2Manifest.firmware)+$p2Manifest.scripts+$p2Manifest.pins')
    (out/'capture.ps1').write_text(capture)
    bindings=[HERE/n for n in ['PROTOCOL.txt','common.py','build_firmware.py','analyze.py','physical.py','summarize.py','test_pilot.py']]
    bindings += [HERE/'qualification/Q002/result.json',HERE/'firmware/F002/result.json',
                 GOLDEN/'manifest.json',GOLDEN/'input_banks.bin',config]
    bindings += [GOLDEN/g['frames'][f]['golden_file'] for f in (0,2)]
    if operation!=1:bindings += [HERE/'physical/Q001/analysis.json']
    manifest=dict(prepared_only=True,board_access=False,launch_id=a.run_id,operation=operation,
        kind=kind,base=base,ordinal=ordinal,initial_bank=initial,expected_records=len(expected),
        expected_archive_words=archive_words,schedule=expected,image=pin(bit),xsa=pin(xsa),firmware=pin(elf),
        scripts=[pin(out/n) for n in ['program.tcl','dump.tcl','ps7_init.tcl','capture.ps1']],
        pins=[pin(p) for p in bindings])
    (out/'launch_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(dict(prepared=str(out),records=len(expected),archive_bytes=archive_words*4,board_access=False)))


if __name__=='__main__':main()
