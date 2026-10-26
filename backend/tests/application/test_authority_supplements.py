import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from fastapi.testclient import TestClient
from roll.app import create_app
from roll.market import authority_supplements as authority


def method_source(tmp_path, volume='19499178', amount='762858168.3800'):
    worker = tmp_path / 'method_worker.py'
    result = {'error_code': '0', 'calls': 3, 'received_bytes': 11, 'wire_b64': 'bWV0aG9kLXdpcmU=',
              'received_at': '2026-10-20T00:15:00+00:00',
              'fields': ['date', 'code', 'open', 'high', 'low', 'close', 'preclose', 'volume', 'amount', 'adjustflag', 'tradestatus', 'isST'],
              'rows': [['2026-10-19', 'sh.600362', '39', '39.46', '38.78', '39.09', '39.43', volume, amount, '3', '1', '0']]}
    worker.write_bytes(('import json,sys\njson.load(sys.stdin)\nprint(' + repr(json.dumps(result)) + ')').encode())
    return worker


def snapshot(client):
    listing = client.get('/api/market/list').json()
    assert client.post('/api/market/watch', json={'operation':'ADD','instrument':'SSE:600362','expected_list_version':listing['version']}).status_code == 200
    request = client.post('/api/data/requests', json={'instruments':['SSE:600362'],'groups':['DAILY'], 'purpose':'OBSERVATION',
        'start_date':'2026-10-19','end_date':'2026-10-19','daily_source':'BAOSTOCK','baostock_auth_mode':'PUBLIC'}).json()
    run = client.post('/api/data/requests/' + request['request_id'] + '/retrieve').json()
    assert run['status'] == 'COMPLETE', run
    return client.get('/api/data/snapshots/' + run['snapshot_id']).json()


def test_method_daily_contract_idempotency_cutoff_and_replay(tmp_path):
    worker = method_source(tmp_path); data = tmp_path / 'data'
    with TestClient(create_app(data, baostock_worker=worker, runtime_role='API')) as client:
        snap = snapshot(client)
        command = {'kind':'DAILY','snapshot_id':snap['snapshot_id'],'idempotency_key':'one'}
        result = client.post('/api/market/source-authority', json=command)
        assert result.status_code == 201, result.text
        saved = result.json(); use = saved['details']['rows'][0]['successor_use']
        assert saved['evidence_kind'] == 'METHOD_CASE'
        assert use['provider_daily_allowed'] and not use['model_daily_input_allowed'] and not use['strict_historical_as_of_allowed']
        assert saved['details']['sse_reported_comparison']['TRADE_AMT'] == '76300.67'
        assert client.post('/api/market/source-authority', json=command).json() == saved
        assert client.post('/api/market/source-authority', json={**command,'kind':'STATUS_PHASE','snapshot_id':None}).status_code == 409
        assert client.post('/api/market/source-authority', json={'kind':'DAILY','idempotency_key':'missing'}).status_code == 422
        url = '/api/market/source-authority?instrument=SSE:600362&known_by='
        assert client.get(url+'2026-10-19T23:00:00%2B08:00').json() == []
        assert client.get(url+'2026-10-19T23:00:00').status_code == 422
        assert client.get('/api/account').json()['version'] == 0
    with TestClient(create_app(data, runtime_role='API')) as client:
        assert client.get('/api/market/source-authority/'+saved['assessment_id']).json() == saved


def test_successor_rejects_normal_zero_turnover_without_changing_legacy_snapshot(tmp_path):
    with TestClient(create_app(tmp_path/'data', baostock_worker=method_source(tmp_path,'0','0'), runtime_role='API')) as client:
        snap = snapshot(client); old = snap['facts'][0]
        assert old['model_daily_input_allowed']  # Preserved legacy semantics; do not rewrite frozen packets.
        saved = client.post('/api/market/source-authority', json={'kind':'DAILY','snapshot_id':snap['snapshot_id'],'idempotency_key':'zero'}).json()
        use = saved['details']['rows'][0]['successor_use']
        assert not use['provider_daily_allowed']
        assert set(use['rejections']) >= {'POSITIVE_VOLUME_SHARES_REQUIRED','POSITIVE_AMOUNT_YUAN_REQUIRED'}
        assert client.get('/api/data/snapshots/'+snap['snapshot_id']).json() == snap
        for changed in [{'reported_tradestatus':'0'},{'completion_state':'UNCONFIRMED_CURRENT_DAY'}, {'adjustment':'FORWARD'}, {'errors':['INVALID_OHLC_RANGE']}]:
            assert not authority.daily_use({**old,'volume_shares':'1','amount_yuan':'39',**changed})['provider_daily_allowed']


def test_actual_document_phase_and_lifecycle_do_not_grant_full_coverage(tmp_path):
    with TestClient(create_app(tmp_path, runtime_role='API')) as client:
        outputs=[]
        for kind in ['STATUS_PHASE','ACTION_DOCUMENTS']:
            response=client.post('/api/market/source-authority',json={'kind':kind,'idempotency_key':kind})
            assert response.status_code==201,response.text
            value=response.json();outputs.append(value)
            assert value['evidence_kind']=='REAL_SAVED_SOURCE_OBSERVATION' and not value['system_usable']
            assert value['network_calls']==value['account_events_added']==0
        phase=outputs[0]['details']; actions=outputs[1]['details']
        assert phase['source_reported_date']=='2026-10-19' and phase['fp_phase_display']=='闭市'
        assert not phase['complete_status_verified'] and not phase['negative_coverage_verified']
        assert actions['returned_count']==6 and actions['missing_reported_rows']==0 and actions['announcement_count']==181
        assert len(actions['notices'])==3 and all(n['payment_fulfilled'] is None and n['cancelled'] is None for n in actions['notices'])
        assert actions['notices'][1]['scheduled_payment_date']=='2026-07-17'
        assert not actions['complete_action_coverage'] and not actions['pending_older_obligations_complete']
        original=client.get('/api/data/archives/'+outputs[1]['references'][0]['archive_sha256'])
        assert original.status_code==200
        assert client.get('/api/account').json()['version']==0


def test_corrupt_reference_and_saved_original_refuse(tmp_path,monkeypatch):
    copied=tmp_path/'reference';shutil.copytree(authority.REFERENCE,copied)
    with TestClient(create_app(tmp_path/'data',runtime_role='API')) as client:
        value=client.post('/api/market/source-authority',json={'kind':'STATUS_PHASE','idempotency_key':'ok'}).json()
        raw=client.app.state.authority_supplements.evidence.raw(value['references'][0]['archive_sha256'])
        raw.write_bytes(b'corrupt')
        assert client.get('/api/market/source-authority/'+value['assessment_id']).status_code==409
        monkeypatch.setattr(authority,'REFERENCE',copied)
        (copied/'phase_client.raw').write_bytes(b'corrupt')
        assert client.post('/api/market/source-authority',json={'kind':'STATUS_PHASE','idempotency_key':'bad'}).status_code==409


def test_daily_choices_and_commands_exclude_research_before_fact_replay(tmp_path,monkeypatch):
    with TestClient(create_app(tmp_path/'data', baostock_worker=method_source(tmp_path), runtime_role='API')) as client:
        snap=snapshot(client)
        assert client.get('/api/market/source-authority/daily-options').json()==[{
            'snapshot_id':snap['snapshot_id'],'created_at':snap['created_at'],'evidence_kind':'METHOD_CASE'}]
        ledger=client.app.state.authority_supplements.ledger
        # Engineering-only classification change in an isolated fixture; no real research/SEALED data opened.
        with ledger.connection() as db:
            row=db.execute('SELECT value FROM data_requests WHERE id=?',(snap['request_id'],)).fetchone()
            value=json.loads(row[0]);value['purpose']='RESEARCH'
            db.execute('UPDATE data_requests SET value=? WHERE id=?',(json.dumps(value),snap['request_id']))
        assert client.get('/api/market/source-authority/daily-options').json()==[]
        def forbidden(*args,**kwargs):raise AssertionError('Research input replay must never be reached')
        monkeypatch.setattr(client.app.state.authority_supplements.evidence,'replay',forbidden)
        assert client.post('/api/market/source-authority',json={'kind':'DAILY','snapshot_id':snap['snapshot_id'],'idempotency_key':'research'}).status_code==403


def test_missing_reference_refuses_without_saving_and_preserves_archived_replay(tmp_path, monkeypatch):
    with TestClient(create_app(tmp_path/'data', runtime_role='API')) as client:
        command = {'kind': 'STATUS_PHASE', 'idempotency_key': 'saved-before-reference-loss'}
        response = client.post('/api/market/source-authority', json=command)
        assert response.status_code == 201, response.text
        saved = response.json()
        original_reference = authority.REFERENCE
        for missing, expected in [
            ('sources.json', 'AUTHORITY_MANIFEST_UNAVAILABLE'),
            ('phase_client.raw', 'AUTHORITY_ORIGINAL_UNAVAILABLE:phase_client'),
        ]:
            copied = tmp_path / missing
            shutil.copytree(original_reference, copied, ignore=shutil.ignore_patterns(missing))
            monkeypatch.setattr(authority, 'REFERENCE', copied)
            refused = client.post('/api/market/source-authority', json={
                'kind': 'STATUS_PHASE', 'idempotency_key': 'missing-' + missing,
            })
            assert refused.status_code == 409, refused.text
            assert refused.json()['detail'] == expected
            assert client.get('/api/market/source-authority/' + saved['assessment_id']).json() == saved
            assert client.post('/api/market/source-authority', json=command).json() == saved
            assert client.get('/api/market/source-authority?instrument=SSE:600362').json() == [saved]
            assert client.get('/api/account').json()['version'] == 0


def test_older_action_supplement_preserves_v1_and_distinguishes_cash_from_reference(tmp_path, monkeypatch):
    data = tmp_path / 'data'
    with TestClient(create_app(data, runtime_role='API')) as client:
        with monkeypatch.context() as legacy:
            legacy.setattr(authority, 'ACTION_REFERENCE', authority.REFERENCE)
            legacy.setattr(authority, 'ACTION_MANIFEST', authority.MANIFEST)
            old = client.post('/api/market/source-authority', json={
                'kind': 'ACTION_DOCUMENTS', 'idempotency_key': 'legacy',
            }).json()
        assert len(old['details']['notices']) == 2
        command = {'kind': 'ACTION_DOCUMENTS', 'idempotency_key': 'older-supplement'}
        response = client.post('/api/market/source-authority', json=command)
        assert response.status_code == 201, response.text
        saved = response.json()
        notice = next(n for n in saved['details']['notices'] if n['notice_number'] == '2025-026')
        assert notice['cash_cny_per_share'] == '0.70'
        assert notice['ex_reference_cash_cny_per_share'] == '0.6965'
        assert notice['record_date'] == '2025-07-21'
        assert notice['ex_date'] == notice['scheduled_payment_date'] == '2025-07-22'
        assert notice['payment_fulfilled'] is None and notice['cancelled'] is None
        assert not saved['details']['pending_older_obligations_complete']
        assert not saved['details']['revision_cancellation_inventory_complete']
        assert not saved['system_usable'] and saved['network_calls'] == 0
        assert client.post('/api/market/source-authority', json=command).json() == saved
        assert client.get('/api/market/source-authority/' + old['assessment_id']).json() == old
        assert client.get('/api/account').json()['version'] == 0
    with TestClient(create_app(data, runtime_role='API')) as client:
        assert client.get('/api/market/source-authority/' + old['assessment_id']).json() == old
        assert client.get('/api/market/source-authority/' + saved['assessment_id']).json() == saved
        original = client.app.state.authority_supplements.evidence.raw(notice['document_version_sha256'])
        original.write_bytes(b'corrupt METHOD fixture only')
        assert client.get('/api/market/source-authority/' + saved['assessment_id']).status_code == 409
        assert client.get('/api/market/source-authority/' + old['assessment_id']).json() == old
