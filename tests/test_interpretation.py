"""Check new explanations against unchanged current-study evidence."""
from pathlib import Path
import hashlib, json, re
import pytest

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'results/interpretation_v1'


def test_geometry_includes_every_primary_sparse_cell_and_loss():
    rows=json.loads((DATA/'analysis.json').read_text())['geometry']
    assert {(r['frame'],r['mask']) for r in rows} == {(f,m) for f in (0,2) for m in (2,5,4,10)}
    assert sum(r['merged_vs_box_percent']<0 for r in rows)==2
    assert all(r['merged_regions']==1 and r['merged_positions']==r['box_positions']
               for r in rows if r['mask'] in (2,4))
    for r in rows:
        means=r['suppressed_skip_on_ms']
        assert r['merged_vs_box_percent']==100*(1-means['merged']/means['bounding_box'])


def test_channel_histograms_retain_bias_transactions():
    result=json.loads((DATA/'analysis.json').read_text())
    for record in result['sparsity']:
        for layer in record['layers']:
            for cell in layer['masks']:
                hist=cell['eligible_channel_histogram'];c=cell['input_channels']
                assert len(hist)==c+1 and sum(hist)==cell['positions']
                issued=sum(max(1,i)*n for i,n in enumerate(hist))
                expected=100*(1-issued/(cell['positions']*c))
                assert cell['effective_channel_issue_reduction_percent']==pytest.approx(expected,abs=1e-10)


def test_model_provenance_matches_export_headers():
    data=json.loads((DATA/'model_provenance.json').read_text())['models']
    for width,record in data.items():
        path=ROOT/record['package']
        assert hashlib.sha256(path.read_bytes()).hexdigest()==record['package_sha256']
        assert record['checkpoint_sha256']==re.search(r'Checkpoint SHA-256: ([a-f0-9]{64})',path.read_text())[1]
        assert record['floating_config']['distillation']['teacher_weight']==0.7
        assert record['epoch']==(9 if width=='w16' else 0)
        assert record['checkpoint_type']==('best' if width=='w16' else 'initial_qat_baseline')
