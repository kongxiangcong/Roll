"""Saved report to real isolated QuantStats; no fit, advance or new ledger."""
from pathlib import Path
from decimal import Decimal
import copy
import json
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
        assert shadow['annualized_return'] is None and shadow['benchmark_status']=='SAVED_MATCHED_CLOSE_INTERVALS'
        assert set(shadow['benchmarks'])=={'CASH','START_HOLD','MA5_MA20'}
        assert all(b['status']=='DESCRIPTIVE_SAVED_CLOSE_INTERVAL' and len(b['returns'])==33 for b in shadow['benchmarks'].values())
        for label,baseline in shadow['benchmarks'].items():
            original=legacy['platform']['state']['comparators'][label]['curve']
            assert baseline['original_points']==original
            expected=float(Decimal(original[-1]['nav_yuan'])/Decimal(original[0]['nav_yuan'])-1)
            assert abs(baseline['total_return']-expected)<=1e-12
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
        # Mutate only this disposable METHOD copy to exercise a saved legacy
        # series with a hole through the public adapter, then restore it.
        state=legacy['platform']['state'];changed=copy.deepcopy(state)
        removed=changed['comparators']['CASH']['curve'].pop(10)['date']
        with client.app.state.ledger.connection() as db:
            db.execute('UPDATE research_shadow_runs SET value=? WHERE freeze_id=? AND revision=?',(json.dumps(changed),FREEZE,state['revision']));db.commit()
        try:
            mismatch=client.post(base,json={**command,'idempotency_key':'mismatched-baseline'} )
            assert mismatch.status_code==201,mismatch.text
            mismatched=mismatch.json()['namespaces']['SHADOW']
            assert mismatched['benchmark_status']=='SAVED_BASELINE_WINDOW_MISMATCH'
            cash=mismatched['benchmarks']['CASH']
            assert cash['status']=='INCOMPLETE_FIXED_WINDOW' and cash['coverage']['missing_sessions']==[removed]
            assert not cash['returns'] and 'interval_return_difference' not in cash
            assert client.get('/api/research/performance-reports/'+identifier).json()==saved
        finally:
            with client.app.state.ledger.connection() as db:
                db.execute('UPDATE research_shadow_runs SET value=? WHERE freeze_id=? AND revision=?',(json.dumps(state),FREEZE,state['revision']));db.commit()
    monkeypatch.delenv('ROLL_QUANTSTATS_PYTHON')
    with TestClient(create_app(tmp_path/'data',runtime_role='API')) as client:
        assert client.get('/api/research/performance-reports/'+identifier).json()==saved
        assert client.post('/api/research/performance-reports/'+identifier+'/replay').json()['matches_original'] is True
