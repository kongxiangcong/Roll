"""Saved report to real isolated QuantStats; no fit, advance or new ledger."""
from pathlib import Path
from fastapi.testclient import TestClient
from roll.app import create_app
from report_method_app import copy_donor,FREEZE,ROOT


def test_performance_report_preserves_saved_window_and_replays_without_runtime(tmp_path,monkeypatch):
    monkeypatch.setenv('ROLL_ENV','test')
    monkeypatch.setenv('ROLL_QUANTSTATS_PYTHON',str(ROOT/'.scratch/rce-runtime/quantstats/Scripts/python.exe'))
    with TestClient(create_app(copy_donor(tmp_path/'data'),runtime_role='API')) as client:
        legacy=client.get('/api/research/reports/'+FREEZE).json()
        base='/api/research/reports/'+FREEZE+'/performance'
        command={'expected_shadow_revision':legacy['platform']['state']['revision'],'idempotency_key':'performance-once','basis':'METHOD saved 193-file donor; no new research computation'}
        result=client.post(base,json=command)
        assert result.status_code==201,result.text
        saved=result.json()
        assert saved['library']['version']=='0.0.86' and saved['network_calls']==0
        assert saved['system_usable'] is False and saved['capability']=='NOT_GRANTED'
        shadow=saved['namespaces']['SHADOW']
        assert shadow['status']=='DESCRIPTIVE_SAVED_CLOSE_INTERVAL'
        assert shadow['coverage']['original_points']==33 and shadow['coverage']['missing_sessions']==[]
        assert shadow['window']==['2026-06-08','2026-07-23']
        assert shadow['annualized_return'] is None and shadow['benchmark_status']=='NO_SAVED_MATCHED_BASELINE_SERIES'
        assert shadow['returns'][0]['value'] is None
        for name in ['ACTUAL','HISTORICAL','ACCOUNT_CONDITIONAL']:
            assert saved['namespaces'][name]['status']=='NOT_A_CONTINUOUS_RETURN_SERIES'
        identifier=saved['performance_report_id']
        image=client.get('/api/research/performance-reports/'+identifier+'/figures/SHADOW')
        assert image.status_code==200 and 'image/svg+xml' in image.headers['content-type']
        assert b'<svg' in image.content
        exported=client.get('/api/research/performance-reports/'+identifier+'/export')
        assert exported.status_code==200 and b'0.0.86' in exported.content and b'NOT_GRANTED' in exported.content
        assert b'<script' not in exported.content and b'src="http' not in exported.content and b'xlink:href="http' not in exported.content
        assert client.post(base,json=command).json()==saved
        assert client.get('/api/research/reports/'+FREEZE).json()==legacy
    monkeypatch.delenv('ROLL_QUANTSTATS_PYTHON')
    with TestClient(create_app(tmp_path/'data',runtime_role='API')) as client:
        assert client.get('/api/research/performance-reports/'+identifier).json()==saved
        assert client.post('/api/research/performance-reports/'+identifier+'/replay').json()['matches_original'] is True
