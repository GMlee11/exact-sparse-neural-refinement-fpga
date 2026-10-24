"""Verify retained assessment; optionally rerun RTL in an external temp folder."""
from pathlib import Path
import argparse,gzip,hashlib,json,subprocess,tempfile
from summarize import summarize
HERE=Path(__file__).resolve().parent
def main():
    p=argparse.ArgumentParser();p.add_argument('--xilinx-bin',type=Path);a=p.parse_args()
    export=json.loads((HERE/'export_manifest.json').read_text())
    for name,pin in export['files'].items():
        b=(HERE/name).read_bytes();assert hashlib.sha256(b).hexdigest()==pin['sha256'],name
        raw=gzip.decompress(b) if pin['compressed'] else b
        assert hashlib.sha256(raw).hexdigest()==pin['original_sha256']
    comparison=json.loads((HERE/'comparison.json').read_text())
    assert summarize(comparison)==json.loads((HERE/'assessment.json').read_text())
    for variant in ('reference','suppressed'):
        folder=HERE/variant;freeze=json.loads((folder/'freeze.json').read_text())
        result=json.loads((folder/'result.json').read_text());assert result['passed']
        text=(folder/'stage2.log').read_text()
        assert text.count('AXI_REQUEST_PASS')==10 and text.count('AXI_FAILURE_PASS')==10
        for name,digest in freeze['files'].items():
            path=folder/name;b=path.read_bytes() if path.exists() else gzip.decompress(Path(str(path)+'.gz').read_bytes())
            assert hashlib.sha256(b).hexdigest()==digest,name
        if a.xilinx_bin:
            with tempfile.TemporaryDirectory(prefix='paper2_traversal_') as tmp:
                target=Path(tmp)
                for name in freeze['files']:
                    path=folder/name
                    (target/name).write_bytes(path.read_bytes() if path.exists() else gzip.decompress(Path(str(path)+'.gz').read_bytes()))
                for cmd in (['xvlog.bat','--sv',*freeze['order']],['xelab.bat','tb_roi_integration','-s','integrated'],['xsim.bat','integrated','-runall']):
                    cmd[0]=str(a.xilinx_bin/cmd[0]);run=subprocess.run(cmd,cwd=target,capture_output=True,text=True,timeout=1200)
                    assert run.returncode==0,run.stdout[-2000:]+run.stderr[-1000:]
                assert 'PAPER2_ROI_INTEGRATION_PASS' in run.stdout
                for values in result['requests']:
                    case,regions,service,loop=values
                    assert f'AXI_REQUEST_PASS case={case} regions={regions} service_cycles={service} execution_loop_cycles={loop}' in run.stdout
    print('TRAVERSAL_ASSESSMENT_VERIFY_PASS', 'and RTL rerun' if a.xilinx_bin else '(retained evidence; no new simulation)')
if __name__=='__main__':main()
