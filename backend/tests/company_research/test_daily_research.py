"""Synthetic engineering cases. Real acceptance is kept separately."""
import pytest
from fastapi import HTTPException
from test_shared_evidence import service, company
from test_analysis_snapshots import evidence, freeze, candidate


def published(research, issuer):
    from roll.research.company import MaterialCommand, FactCommand
    from test_shared_evidence import material_input
    metadata = material_input(issuer['company_id'])
    metadata['subject_name'] = issuer['legal_name']
    material = research.import_material(MaterialCommand(**metadata), b'Disclosed refining business; no forward volume evidence')
    fact = research.add_fact(FactCommand(company_id=issuer['company_id'], material_id=material['material_id'],
        metric='business_structure', business='REFINING', value='Disclosed refining business', value_type='TEXT',
        unit='CNY_MILLION', currency='CNY', scope='CONSOLIDATED',
        period_start='2025-01-01', period_end='2025-12-31', change_reason='Synthetic text fixture'))
    packet = freeze(research, issuer, fact)
    return research.apply_analysis_candidate(packet['input_id'], candidate(packet, fact))


def test_daily_view_pins_shared_core_without_hiding_research_when_valuation_missing(tmp_path):
    research = service(tmp_path)
    issuer = research.register(company())
    snapshot = published(research, issuer)
    view = research.daily_view(issuer['company_id'], snapshot['snapshot_id'])
    assert view['snapshot'] == research.analysis_snapshot(snapshot['snapshot_id'], 'REPORT')
    assert view['attention_reasons'][0]['text'].startswith('Refining business')
    assert view['valuation']['status'] == 'UNAVAILABLE'
    assert view['valuation']['scenarios'] == []
    assert view['information_state']['research_verification_refreshed'] is False
    assert set(view['changes']) == {'OPERATING_EVIDENCE', 'PRICE', 'VALUATION_ASSUMPTION_OR_METHOD'}
    assert view['catalysts'][0]['date'] is None
    assert view['risks'][0]['kind'] == 'INVALIDATION_CONDITION'
    assert view['risks'][0]['verified_fact'] is False
    assert view['risks'][0]['hypothesis_version_id'] == snapshot['core']['hypotheses'][0]['version_id']
    other = research.register(company('第二家公司', ['第二公司'], [dict(exchange='SZSE', code='000848', share_class='A', currency='CNY')]))
    with pytest.raises(HTTPException) as error:
        research.daily_view(other['company_id'], snapshot['snapshot_id'])
    assert error.value.detail['code'] == 'CROSS_COMPANY_REFERENCE'


def test_selected_watch_company_keeps_assistance_history_prices_and_shared_core_isolated(tmp_path, monkeypatch):
    import time
    from roll.runtime.assistance import Assistance, AssistanceCommand
    from roll.market.directory import WatchCommand
    from test_assistance import prices
    research = service(tmp_path)
    issuer = research.register(company())
    first = published(research, issuer)
    other = research.register(company('第二家公司', ['第二公司'], [dict(exchange='SZSE', code='000848', share_class='A', currency='CNY')]))
    second = published(research, other)
    market = research.evidence.market
    market.watch(WatchCommand(instrument='SZSE:000848', operation='ADD', expected_list_version=market.listing()['version']))
    def acquire(request, *args):
        from datetime import date, timedelta
        rows = prices()
        for index, row in enumerate(rows):
            row['code'] = request['symbol']
            row['date'] = (date.fromisoformat(request['end_date'])-timedelta(days=44-index)).isoformat()
        assert 'adjustflag' in request['fields'] if request['symbol'] == 'sz.000848' else True
        return b'synthetic daily rows', dict(received_at='2026-02-15T00:00:00+00:00', sdk_distribution_version='fixture', fixture_rows=rows)
    monkeypatch.setattr('roll.runtime.assistance.acquire', acquire)
    monkeypatch.setattr('roll.runtime.assistance.rows', lambda result: result['fixture_rows'])
    monkeypatch.delenv('ROLL_CODEX_AUTH_FILE', raising=False)
    assistance = Assistance(research.ledger, market=market, research=research)
    run = assistance.start(AssistanceCommand(instrument='SZSE:000848'))
    for _ in range(100):
        saved = assistance.get(run['run_id'])
        if saved['status'] != 'RUNNING':
            break
        time.sleep(.02)
    assert saved['company_id'] == other['company_id']
    assert saved['research']['snapshot']['snapshot_id'] == second['snapshot_id']
    assert saved['material']['company_research']['snapshot']['snapshot_id'] != first['snapshot_id']
    assert saved['sources'][0]['source_id'] == 'sz.000848'
    assert saved['sources'][0]['price_unit'] == 'CNY'
    assert saved['sources'][0]['raw_archive']['sha256'] == saved['sources'][0]['sha256']
    assert saved['material']['market_data_as_of'] == saved['sources'][0]['last_date']
    assert saved['material']['as_of'] >= saved['research']['snapshot']['as_of']
    assert saved['material']['historical_pit'] is False
    assert assistance.history('SSE:600362') == []
    assert assistance.history('SZSE:000848')[0]['run_id'] == run['run_id']
    assistance.close()


def test_archive_refresh_no_new_material_reuses_snapshot_and_failure_can_retry(tmp_path):
    research = service(tmp_path)
    issuer = research.register(company())
    snapshot = published(research, issuer)
    def empty(scope):
        return []
    a = research.refresh_daily(issuer['company_id'], 'archive01', empty)
    b = research.refresh_daily(issuer['company_id'], 'archive01', empty)
    assert a == b
    assert a['snapshot_id'] == snapshot['snapshot_id']
    assert a['analysis_input_id'] is None and a['model_executed'] is False
    assert a['check']['source_id'] == 'saved-archive-catalog'
    assert a['check']['new_material_count'] == 0
    assert a['network_check_performed'] is False
    assert research.analysis_snapshots(issuer['company_id'])['total'] == 1
    def timeout(scope):
        raise TimeoutError('external archive unavailable')
    failed = research.refresh_daily(issuer['company_id'], 'archive02', timeout)
    assert failed['check']['status'] == 'FAILED'
    retry = research.refresh_daily(issuer['company_id'], 'archive03', empty)
    assert retry['check']['status'] == 'SUCCESS'
    assert retry['check']['check_id'] != failed['check']['check_id']
    assert research.analysis_snapshots(issuer['company_id'])['total'] == 1


def test_research_updates_use_existing_worker_queue_with_company_scope_and_explicit_retry(tmp_path, monkeypatch):
    from roll.app import create_app
    from fastapi.testclient import TestClient
    from roll.market.directory import WatchCommand
    from datetime import datetime, timezone
    import threading
    monkeypatch.delenv('ROLL_CODEX_AUTH_FILE', raising=False)
    app = create_app(tmp_path, runtime_role='API')
    research = app.state.company_research
    issuer = research.register(company())
    snapshot = published(research, issuer)
    other = research.register(company('第二家公司', ['第二公司'], [dict(exchange='SZSE', code='000848', share_class='A', currency='CNY')]))
    app.state.market.watch(WatchCommand(instrument='SZSE:000848', operation='ADD', expected_list_version=app.state.market.listing()['version']))
    with TestClient(app) as client:
        base = '/api/observation-updates/SZSE:000848'
        settings = client.get(base).json()['settings']
        assert client.post(base+'/settings', json=dict(enabled=True, expected_revision=settings['revision'], basis='Synthetic research schedule', research_postclose=True)).status_code == 200
        command = dict(kind='RESEARCH', idempotency_key='archive1', basis='Synthetic archive-only check', refresh_sources=False)
        response = client.post(base+'/requests', json=command)
        assert response.status_code == 201, response.text
        job = response.json()
        app.state.observation_updates.work(datetime.now(timezone.utc), threading.Event())
        saved = client.get('/api/observation-update-jobs/'+job['job_id']).json()
        assert saved['status'] == 'COMPLETE', saved
        observation = client.get(base).json()['observations'][0]
        assert observation['payload']['company_id'] == other['company_id']
        assert observation['payload']['snapshot_id'] is None
        assert observation['payload']['network_check_performed'] is False
        assert client.post(base+'/requests', json=command).json()['job_id'] == saved['job_id']
        command['idempotency_key']='archive2'
        repeated = client.post(base+'/requests', json=command).json()
        app.state.observation_updates.work(datetime.now(timezone.utc), threading.Event())
        assert client.get('/api/observation-update-jobs/'+repeated['job_id']).json()['observation_id'] == saved['observation_id']
        # Existing providers are accurately scoped; selecting another company does not broaden them.
        assert client.post(base+'/requests', json={**command,'kind':'NEWS','idempotency_key':'wrong-scope'}).status_code == 409
        assert research.analysis_snapshot(snapshot['snapshot_id'])['company_id'] == issuer['company_id']
        assert client.get('/api/account').json()['version'] == 0


def test_daily_backup_restores_core_checks_and_refuses_rehashed_cross_company_binding(tmp_path):
    import json
    from roll.runtime.backups import Backups, restore_at_start
    from roll.research.company.service import record
    research = service(tmp_path/'source')
    issuer = research.register(company())
    snapshot = published(research, issuer)
    update = research.refresh_daily(issuer['company_id'], 'saved-check', lambda scope: [])
    backups = Backups(tmp_path/'source')
    bundle = backups.export(backups.create()['backup_id'])
    restored = Backups(tmp_path/'restored')
    restored.stage_restore(bundle)
    restore_at_start(restored)
    recovered = service(tmp_path/'restored')
    view = recovered.daily_view(issuer['company_id'], snapshot['snapshot_id'])
    assert view['snapshot'] == snapshot
    assert view['latest_checks'][0]['check_id'] == update['check']['check_id']
    other = research.register(company('第二家公司', ['第二公司'], [dict(exchange='SZSE', code='000848', share_class='A', currency='CNY')]))
    other_snapshot = published(research, other)
    with research.ledger.connection() as db:
        corrupted = {k:v for k,v in update.items() if k!='content_sha256'}
        corrupted['snapshot_id'] = other_snapshot['snapshot_id']
        db.execute('UPDATE company_research_commands SET result=? WHERE scope=? AND key=?',
            (json.dumps(record(corrupted)), 'daily-update:'+issuer['company_id'], 'saved-check'))
    with pytest.raises(HTTPException) as error:
        backups.create()
    assert error.value.detail['code'] == 'RESEARCH_REFERENCE_INVALID'


@pytest.mark.parametrize('bad_count',[0,20])
def test_archive_batches_progress_beyond_twenty_without_rewriting_the_operating_snapshot(tmp_path,bad_count):
    import json
    from roll.accounts.ledger import now
    research = service(tmp_path)
    issuer = research.register(company())
    snapshot = published(research, issuer)
    # Seed the external legacy source store with explicitly synthetic archived records.
    with research.ledger.connection() as db:
        db.execute('CREATE TABLE financial_income_facts(id TEXT PRIMARY KEY,instrument TEXT,value TEXT)')
    for index in range(25):
        original = research.evidence.archive(f'METHOD statement source row {index}'.encode(), 'METHOD_ARCHIVE', source_url='https://issuer.example/statement', received_at=now())
        upstream = dict(instrument='SSE:600362',source_id='fixture-financial',source_url='https://issuer.example/statement',
            raw_sha256=None if index<bad_count else original['sha256'],evidence_kind='METHOD_CASE',report_period='2025-12-31',statement='INCOME',
            period_basis='YEAR_TO_DATE',unit='YUAN',currency='CNY',statement_scope='CONSOLIDATED',
            first_received_at=original['received_at'])
        with research.ledger.connection() as db:
            db.execute('INSERT INTO financial_income_facts VALUES(?,?,?)',(str(index),'SSE:600362',json.dumps(upstream)))
    first = research.refresh_daily(issuer['company_id'],'batch1')
    second = research.refresh_daily(issuer['company_id'],'batch2')
    third = research.refresh_daily(issuer['company_id'],'batch3')
    assert [r['check']['new_material_count'] for r in [first,second,third]] == [20-bad_count,5,0]
    if not bad_count:
        assert first['gap'] == 'NEW_ARCHIVED_MATERIAL_REQUIRES_SOURCED_FACT_EXTRACTION'
    else:
        assert first['check']['errors'][0]['code']=='SOURCE_ORIGINAL_MISSING'
        assert third['archive_failures']['unresolved_record_count']==20
    assert all(not r['model_executed'] and r['snapshot_id']==snapshot['snapshot_id'] for r in [first,second,third])
    assert research.materials(issuer['company_id'])['total']==26-bad_count
    assert research.analysis_snapshots(issuer['company_id'])['total']==1


def test_rejected_news_record_does_not_block_valid_records_and_explicit_recheck_is_possible(tmp_path):
    import json
    from roll.accounts.ledger import now
    research = service(tmp_path)
    issuer = research.register(company())
    published(research, issuer)
    with research.ledger.connection() as db:
        db.execute('CREATE TABLE news_facts(id TEXT PRIMARY KEY,instrument TEXT,value TEXT)')
    for identifier,title in [('bad','无关公司新闻'),('good','江西铜业股份有限公司经营披露')]:
        raw=research.evidence.archive(title.encode(), 'METHOD_NEWS', received_at=now(),source_url='https://finance.eastmoney.com/a/'+identifier+'.html')
        fact=dict(fact_id=identifier,instrument='SSE:600362',source_id='fixture-news',title=title,excerpt=title,
            url='https://finance.eastmoney.com/a/'+identifier+'.html',list_sha256=raw['sha256'],body_status='UNAVAILABLE',
            evidence_kind='METHOD_CASE',first_received_at=raw['received_at'])
        with research.ledger.connection() as db:
            db.execute('INSERT INTO news_facts VALUES(?,?,?)',(identifier,'SSE:600362',json.dumps(fact)))
    first=research.refresh_daily(issuer['company_id'],'bad-then-good')
    assert first['check']['status']=='PARTIAL'
    assert first['check']['new_material_count']==1
    assert first['check']['errors'][0]['record_id']=='bad'
    assert first['check']['errors'][0]['code']=='SOURCE_IDENTITY_UNCONFIRMED'
    following=research.refresh_daily(issuer['company_id'],'continue-after-rejection')
    assert following['check']['status']=='SUCCESS' and following['check']['new_material_count']==0
    assert following['archive_failures']['unresolved_record_count']==1
    retry=research.refresh_daily(issuer['company_id'],'explicit-identity-recheck',retry_rejected=True)
    assert retry['check']['status']=='PARTIAL'
    assert retry['check']['errors'][0]['record_id']=='bad'


def test_new_fact_freezes_a_bounded_analysis_and_model_unavailability_preserves_the_old_core(tmp_path, monkeypatch):
    from roll.app import create_app
    from roll.market.directory import WatchCommand
    from roll.runtime.observation_updates import UpdateSettings, UpdateRequest
    from datetime import datetime, timezone
    import threading
    monkeypatch.setenv('ROLL_CODEX_AUTH_FILE', str(tmp_path/'unconfigured'))
    app=create_app(tmp_path,runtime_role='API')
    research,updates=app.state.company_research,app.state.observation_updates
    issuer=research.register(company())
    snapshot=published(research,issuer)
    _,new_fact=evidence(research,issuer,'New disclosed interruption challenges refining stability')
    market=app.state.market
    market.watch(WatchCommand(instrument='SSE:600362',operation='ADD',expected_list_version=market.listing()['version']))
    updates.configure('SSE:600362',UpdateSettings(enabled=True,expected_revision=1,basis='Synthetic explicit research'))
    job=updates.submit('SSE:600362',UpdateRequest(kind='RESEARCH',idempotency_key='new-fact',basis='Synthetic model-unavailable update'))
    updates.work(datetime.now(timezone.utc),threading.Event())
    saved=updates.get(job['job_id'])
    assert saved['status']=='PARTIAL'
    observation=updates.listing('SSE:600362')['observations'][0]
    payload=observation['payload']
    packet=research.analysis_input(payload['analysis_input_id'])
    assert new_fact['version_id'] in packet['fact_version_ids']
    assert packet['parent_snapshot_id']==snapshot['snapshot_id']
    assert research.analysis_run(payload['analysis_run_id'])['status']=='UNAVAILABLE'
    assert payload['model_executed'] is False
    assert research.analysis_snapshot(snapshot['snapshot_id'])==snapshot
    assert research.analysis_snapshots(issuer['company_id'])['total']==1
    assert 'RESEARCH:SSE:600362' in updates.listing('SSE:600362')['health']


def test_verified_existing_financial_fields_automatically_enter_the_frozen_daily_input(tmp_path):
    from fastapi.testclient import TestClient
    from roll.app import create_app
    from test_company_research_sources import setup
    from test_financial_statements import statements
    with TestClient(create_app(tmp_path,runtime_role='API')) as client:
        issuer=setup(client,'akshare-financial-em')
        research=client.app.state.company_research
        snapshot=published(research,issuer)
        client.app.state.financial_statements.worker=statements
        run=client.post('/api/market/financial/SSE:600362/statements/collect',json=dict(idempotency_key='daily-native',basis='METHOD deterministic existing financial fields')).json()
        assert run['status']=='COMPLETE',run
        first_material=client.post('/api/company-research/materials/from-source',json=dict(company_id=issuer['company_id'],source_type='FINANCIAL_FACT',record_id=run['facts'][0]['fact_id']))
        assert first_material.status_code==201,first_material.text
        update=research.refresh_daily(issuer['company_id'],'native-financial')
        assert update['analysis_input_id'] is not None
        packet=research.analysis_input(update['analysis_input_id'])
        native={f['metric']:f for f in packet['payload']['facts'] if f['business']=='FINANCIAL_STATEMENT'}
        assert native['assets']['value']=='293265142356'
        assert native['assets']['period_start']==native['assets']['period_end']=='2026-06-30'
        assert native['operating_cash_flow']['value']=='5814230993'
        assert native['operating_cash_flow']['period_start']=='2026-01-01'
        assert native['operating_cash_flow']['period_end']=='2026-06-30'
        assert native['assets']['unit']=='YUAN' and native['assets']['currency']=='CNY'
        assert native['assets']['scope']=='CONSOLIDATED' and native['assets']['table']=='BALANCE:TOTAL_ASSETS'
        assert research.material(native['assets']['material_id'])['source_kind']=='METHOD_CASE'
        assert packet['parent_snapshot_id']==snapshot['snapshot_id']
        assert research.analysis_snapshot(snapshot['snapshot_id'])==snapshot
        assert client.get('/api/account').json()['version']==0


def test_unknown_financial_basis_keeps_material_and_gap_without_inventing_periods_or_facts(tmp_path):
    import json,hashlib
    from fastapi.testclient import TestClient
    from roll.app import create_app
    from test_company_research_sources import setup
    from test_financial_statements import statements
    async def unknown(instrument,output):
        manifest=await statements(instrument,output)
        for capture in manifest['captures']:
            path=output/capture['raw_file'];value=json.loads(path.read_bytes());value['data'][0]['CURRENCY']='USD'
            raw=json.dumps(value).encode();path.write_bytes(raw);capture['sha256']=hashlib.sha256(raw).hexdigest()
        return manifest
    with TestClient(create_app(tmp_path,runtime_role='API')) as client:
        issuer=setup(client,'akshare-financial-em');research=client.app.state.company_research
        snapshot=published(research,issuer)
        client.app.state.financial_statements.worker=unknown
        run=client.post('/api/market/financial/SSE:600362/statements/collect',json=dict(idempotency_key='unknown-native',basis='METHOD unknown financial semantics')).json()
        assert run['status']=='COMPLETE',run
        update=research.refresh_daily(issuer['company_id'],'unknown-financial')
        assert update['analysis_input_id'] is None
        assert update['financial_adaptation']['unresolved_material_count']==2
        assert update['financial_adaptation']['remaining_material_count']==0
        assert update['financial_adaptation']['batch_material_count']==2
        assert research.facts(issuer['company_id'])['total']==1
        assert research.analysis_snapshot(snapshot['snapshot_id'])==snapshot


def test_removed_watch_member_is_cancelled_without_stopping_another_company_job(tmp_path):
    from roll.app import create_app
    from roll.market.directory import WatchCommand
    from roll.runtime.observation_updates import UpdateSettings,UpdateRequest
    from datetime import datetime,timezone
    import threading
    app=create_app(tmp_path,runtime_role='API');research=app.state.company_research;market=app.state.market;updates=app.state.observation_updates
    research.register(company())
    research.register(company('第二家公司',['第二公司'],[dict(exchange='SZSE',code='000848',share_class='A',currency='CNY')]))
    for instrument in ['SZSE:000848','SSE:600362']:
        market.watch(WatchCommand(instrument=instrument,operation='ADD',expected_list_version=market.listing()['version']))
        updates.configure(instrument,UpdateSettings(enabled=True,expected_revision=1,basis='METHOD finite watch jobs'))
    removed=updates.submit('SZSE:000848',UpdateRequest(kind='RESEARCH',idempotency_key='removed',basis='METHOD'))
    remaining=updates.submit('SSE:600362',UpdateRequest(kind='RESEARCH',idempotency_key='remaining',basis='METHOD'))
    market.watch(WatchCommand(instrument='SZSE:000848',operation='REMOVE',expected_list_version=market.listing()['version']))
    updates.work(datetime.now(timezone.utc),threading.Event())
    assert updates.get(removed['job_id'])['status']=='CANCELLED'
    assert updates.get(remaining['job_id'])['status']=='COMPLETE'


def test_method_postclose_research_is_once_per_current_day_and_does_not_fill_offline_days(tmp_path):
    from roll.app import create_app
    from roll.market.directory import WatchCommand
    from roll.runtime.observation_updates import UpdateSettings
    from datetime import datetime
    import threading
    app=create_app(tmp_path,runtime_role='API');research=app.state.company_research;market=app.state.market;updates=app.state.observation_updates
    issuer=research.register(company());snapshot=published(research,issuer)
    market.watch(WatchCommand(instrument='SSE:600362',operation='ADD',expected_list_version=market.listing()['version']))
    updates.configure('SSE:600362',UpdateSettings(enabled=True,research_postclose=True,expected_revision=1,basis='METHOD synthetic clock; not actual postclose evidence'))
    first=datetime.fromisoformat('2026-10-19T15:06:00+08:00')
    updates.work(first,threading.Event());updates.work(first,threading.Event())
    value=updates.listing('SSE:600362')
    assert len(value['jobs'])==1 and value['jobs'][0]['status']=='COMPLETE'
    assert value['jobs'][0]['scheduled_checkpoint']=='2026-10-19T15:05:00+08:00'
    updates.work(datetime.fromisoformat('2026-10-22T15:06:00+08:00'),threading.Event())
    current=updates.listing('SSE:600362')
    assert len(current['jobs'])==2
    assert {j['command']['idempotency_key'] for j in current['jobs']}=={'research-postclose:2026-10-19','research-postclose:2026-10-22'}
    assert len(current['observations'])==1 and all(j['status']=='COMPLETE' for j in current['jobs'])
    assert research.analysis_snapshot(snapshot['snapshot_id'])==snapshot


def test_existing_observation_idempotency_survives_the_new_optional_retry_field(tmp_path):
    from fastapi.testclient import TestClient
    from roll.app import create_app
    from roll.accounts.ledger import encode
    import json,hashlib
    with TestClient(create_app(tmp_path,runtime_role='API')) as client:
        base='/api/observation-updates/SSE:600362'
        assert client.post(base+'/settings',json=dict(enabled=True,expected_revision=1,basis='METHOD legacy command')).status_code==200
        old=dict(idempotency_key='legacy-news',basis='METHOD old stored request',kind='NEWS',refresh_sources=False)
        created=client.post(base+'/requests',json=old).json()
        # Legacy persisted command: the optional07 retry field did not exist.
        created['command']=old
        with client.app.state.ledger.connection() as db:
            db.execute('UPDATE observation_update_jobs SET command_hash=?,value=? WHERE id=?',
                (hashlib.sha256(encode(old).encode()).hexdigest(),json.dumps(created),created['job_id']))
        repeated=client.post(base+'/requests',json=old)
        assert repeated.status_code==201,repeated.text
        assert repeated.json()['job_id']==created['job_id']


def test_partial_model_publication_is_bound_to_the_new_accepted_snapshot_and_keeps_rejections(tmp_path,monkeypatch):
    import json,threading
    from datetime import datetime,timezone
    from roll.app import create_app
    from roll.market.directory import WatchCommand
    from roll.runtime.observation_updates import UpdateSettings,UpdateRequest
    worker=tmp_path/'method-partial-worker.py'
    worker.write_text('''import json,sys
c=json.loads(sys.stdin.readline());p=json.loads(c['prompt']);fid=p['evidence']['facts'][-1]['version_id']
claim=dict(text='Refining source evidence requires review',fact_version_ids=[fid],gap_reason=None)
bad=dict(key='invalid',previous_version_id=None,business='REFINING',statement='Unsupported hypothesis',horizon='Next disclosure',observation_metrics=['disclosed operations'],support_fact_version_ids=['unknown-fact'],counter_fact_version_ids=[],invalidation_conditions=['New contrary disclosure'],next_validation_event=dict(description='Next disclosure',date=None,date_unknown_reason='No disclosed date',date_fact_version_ids=[]),gaps=['Missing support'],change_reason='METHOD invalid citation')
candidate=dict(company_id=p['company_id'],input_sha256=p['packet_sha256'],business_structure=[claim],attention_reasons=[claim],counterevidence=[],hypotheses=[bad],insufficient_hypotheses_reason='METHOD partial candidate',limitations=['Synthetic boundary output, no actual model'],valuation_unavailable_reason='No valuation evidence')
print(json.dumps(dict(kind='thread',model='gpt-6.1-sol',provider='METHOD',thread_id='method-partial',instruction_sources=[])),flush=True)
print(json.dumps(dict(kind='completed',status='completed',output=json.dumps(candidate),error_info=None)),flush=True)
''',encoding='utf-8')
    auth=tmp_path/'method-auth.json'
    auth.write_text(json.dumps(dict(auth_mode='chatgpt',tokens=dict(access_token='METHOD_CASE_NOT_REAL_CREDENTIAL'))))
    monkeypatch.setenv('ROLL_CODEX_AUTH_FILE',str(auth))
    app=create_app(tmp_path/'data',runtime_role='API');research=app.state.company_research;updates=app.state.observation_updates;market=app.state.market
    issuer=research.register(company());old=published(research,issuer)
    evidence(research,issuer,'New disclosed interruption challenges refining stability')
    research.analysis_worker=worker
    market.watch(WatchCommand(instrument='SSE:600362',operation='ADD',expected_list_version=market.listing()['version']))
    updates.configure('SSE:600362',UpdateSettings(enabled=True,expected_revision=1,basis='METHOD partial boundary output'))
    job=updates.submit('SSE:600362',UpdateRequest(kind='RESEARCH',idempotency_key='partial-model',basis='METHOD accepted partial research'))
    updates.work(datetime.now(timezone.utc),threading.Event())
    saved=updates.get(job['job_id']);assert saved['status']=='PARTIAL',saved
    payload=updates.listing('SSE:600362')['observations'][0]['payload']
    assert payload['snapshot_id']!=old['snapshot_id']
    run=research.analysis_run(payload['analysis_run_id'])
    assert run['status']=='PARTIAL' and run['snapshot_id']==payload['snapshot_id']
    accepted=research.analysis_snapshot(payload['snapshot_id'])
    assert accepted['core']['business_structure'] and accepted['rejections'][0]['code']=='UNKNOWN_CITATION'
    assert 'OPERATING_ANALYSIS:PARTIAL' in saved['errors']
    assert research.analysis_snapshot(old['snapshot_id'])==old
