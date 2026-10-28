"""METHOD engineering fixtures; real model receipts live in evidence/08."""
from test_shared_evidence import service, company
from test_daily_research import published
import pytest


def test_report_request_freezes_shared_core_and_template_without_account(tmp_path):
    from roll.research.company.reports import ReportCommand
    research = service(tmp_path)
    issuer = research.register(company())
    snapshot = published(research, issuer)
    command = ReportCommand(company_id=issuer['company_id'], snapshot_id=snapshot['snapshot_id'],
        as_of='2026-01-01T00:00:00+00:00', source_mode='REUSE', idempotency_key='one')
    job = research.reports.start(command)
    assert research.reports.start(command) == job
    assert job['snapshot_id'] == snapshot['snapshot_id']
    assert job['model'] == 'gpt-6.1-sol'
    assert job['status'] == 'QUEUED' and job['stage'] == 'ACQUISITION'
    assert job['request_cutoff'] == command.as_of
    assert research.ledger.account()['version'] == 0


def test_missing_sources_produce_ten_sections_and_explicit_partial_gates(tmp_path, monkeypatch):
    from roll.research.company.reports import ReportCommand
    monkeypatch.delenv('ROLL_CODEX_AUTH_FILE', raising=False)
    research = service(tmp_path)
    issuer = research.register(company())
    snapshot = published(research, issuer)
    job = research.reports.start(ReportCommand(company_id=issuer['company_id'], snapshot_id=snapshot['snapshot_id'],
        as_of='2026-01-01T00:00:00+00:00', source_mode='REUSE', idempotency_key='partial'))
    for _ in range(25):
        job = research.reports.advance(job['job_id'])
        if job['report_id']:
            break
    assert job['status'] == 'PARTIAL', job
    report = research.reports.read(job['report_id'])
    assert report['snapshot_id'] == snapshot['snapshot_id']
    assert report['core'] == research.daily_view(issuer['company_id'], snapshot['snapshot_id'])['snapshot']['core']
    markdown = research.reports.markdown(report['report_id'])
    for heading in ['# 速览', '# 第一部分', '# 第二部分', '# 第三部分', '# 第四部分', '## 10.', '### 9.1', '### 9.9', '# 附录 A', '# 附录 I', '# 附录 J', '# 附录 K']:
        assert heading in markdown
    assert len(report['quality']['reference_rules']) == 94
    rules = {r['source_line']: r for r in report['quality']['reference_rules']}
    assert rules[378]['outcome'] == 'FAIL'
    assert rules[464]['outcome'] == 'FAIL'
    assert rules[342]['outcome'] == 'NOT_APPLICABLE'
    assert rules[344]['outcome'] == 'PASS'
    assert rules[487]['severity'] == 'warn'
    assert all(set(['source_hash','source_line','applies','severity','outcome','evidence','reason']) <= set(r) for r in rules.values())
    assert research.reports.advance(job['job_id']) == job


def test_report_acquires_bounded_registered_source_retains_failure_and_shared_material(tmp_path):
    import httpx
    from roll.research.company.reports import ReportCommand
    from test_shared_evidence import material_input
    research=service(tmp_path)
    issuer=research.register(company())
    snapshot=published(research,issuer)
    calls=[]
    def respond(request):
        calls.append(str(request.url))
        return httpx.Response(200,content=b'%PDF-1.7 METHOD original retained') if len(calls)==1 else httpx.Response(503)
    research.evidence.transport=httpx.MockTransport(respond)
    metadata=material_input(issuer['company_id'])
    metadata.update(source_url='https://static.cninfo.com.cn/finalpage/2026-01-01/report.PDF',media_type='application/pdf')
    source=dict(material=metadata,category='本体披露',identity_basis='METHOD confirmed issuer PDF URL')
    job=research.reports.start(ReportCommand(company_id=issuer['company_id'],snapshot_id=snapshot['snapshot_id'],
        as_of='2026-02-01T00:00:00+00:00',idempotency_key='sources',sources=[source,{**source,'category':'行业时序'}]))
    a=research.reports.advance(job['job_id'])
    assert len(calls)==1 and a['stage']=='ACQUISITION'
    b=research.reports.advance(job['job_id'])
    assert len(calls)==2 and b['stage']=='SHARED_FACTS'
    assert b['acquisition']['status']=='PARTIAL'
    material_id=b['acquisition']['receipts'][0]['material_id']
    assert research.material(material_id)['source_kind']=='METHOD_CASE'
    assert research.material_bytes(material_id)==b'%PDF-1.7 METHOD original retained'
    assert research.checks(issuer['company_id'])['total']==2
    assert research.ledger.account()['version']==0


def test_cancel_retry_and_restart_preserve_fixed_input_without_duplicate_publication(tmp_path,monkeypatch):
    from roll.research.company.reports import ReportCommand
    monkeypatch.delenv('ROLL_CODEX_AUTH_FILE',raising=False)
    research=service(tmp_path)
    issuer=research.register(company())
    snapshot=published(research,issuer)
    job=research.reports.start(ReportCommand(company_id=issuer['company_id'],snapshot_id=snapshot['snapshot_id'],
        as_of='2026-02-01T00:00:00+00:00',source_mode='REUSE',idempotency_key='retry'))
    for _ in range(4):
        job=research.reports.advance(job['job_id'])
    fixed=job['input_id']
    assert fixed
    cancelled=research.reports.cancel(job['job_id'])
    assert cancelled['status']=='CANCELLED'
    recovered=service(tmp_path)
    assert recovered.reports.get(job['job_id'])['input_id']==fixed
    retried=recovered.reports.retry(job['job_id'])
    assert retried['status']=='QUEUED' and retried['input_id']==fixed
    for _ in range(18):
        done=recovered.reports.advance(job['job_id'])
        if done['report_id']:break
    assert done['status']=='PARTIAL'
    assert recovered.reports.retry(job['job_id'])['report_id']==done['report_id']
    assert recovered.reports.list(issuer['company_id'])['total']==1


def test_backup_restores_frozen_report_and_rejects_rehashed_wrong_snapshot(tmp_path,monkeypatch):
    import json
    import pytest
    from fastapi import HTTPException
    from roll.runtime.backups import Backups,restore_at_start
    from roll.research.company.service import record
    from roll.research.company.reports import ReportCommand
    monkeypatch.delenv('ROLL_CODEX_AUTH_FILE',raising=False)
    directory=tmp_path/'source'
    research=service(directory)
    issuer=research.register(company())
    snapshot=published(research,issuer)
    job=research.reports.start(ReportCommand(company_id=issuer['company_id'],snapshot_id=snapshot['snapshot_id'],
        as_of='2026-02-01T00:00:00+00:00',source_mode='REUSE',idempotency_key='backup'))
    for _ in range(22):
        job=research.reports.advance(job['job_id'])
        if job['report_id']:break
    report=research.reports.read(job['report_id'])
    backups=Backups(directory)
    bundle=backups.export(backups.create()['backup_id'])
    restore=Backups(tmp_path/'restored')
    restore.stage_restore(bundle);restore_at_start(restore)
    recovered=service(tmp_path/'restored')
    assert recovered.reports.read(report['report_id'])==report
    assert recovered.reports.markdown(report['report_id'])==research.reports.markdown(report['report_id'])
    with research.ledger.connection() as db:
        corrupt={k:v for k,v in report.items() if k!='content_sha256'}
        corrupt['snapshot_id']='unregistered-snapshot'
        db.execute('UPDATE company_research_reports SET value=? WHERE report_id=?',(json.dumps(record(corrupt)),report['report_id']))
    with pytest.raises(HTTPException) as error:
        backups.create()
    assert error.value.detail['code']=='RESEARCH_REFERENCE_INVALID'


def test_model_gap_cannot_inject_active_content_and_exact_command_is_archived(tmp_path,monkeypatch):
    import json
    from roll.research.company.reports import ReportCommand
    worker=tmp_path/'method-report-worker.py'
    worker.write_text('''import json,sys
c=json.loads(sys.stdin.readline());p=json.loads(c['prompt'])
assert c['tools']==[]
print(json.dumps({'kind':'thread','model':c['model'],'provider':'METHOD','thread_id':'method','instruction_sources':[]}),flush=True)
print(json.dumps({'kind':'completed','status':'completed','output':json.dumps({'section_id':p['section_id'],'input_sha256':p['input_sha256'],'paragraphs':[{'text':'Evidence is incomplete','fact_version_ids':[]}],'gaps':['<script>arbitrary_code()</script>']})}),flush=True)
''',encoding='utf-8')
    auth=tmp_path/'method-auth.json'
    auth.write_text(json.dumps({'auth_mode':'chatgpt','tokens':{'access_token':'METHOD_NOT_A_REAL_CREDENTIAL'}}))
    monkeypatch.setenv('ROLL_CODEX_AUTH_FILE',str(auth))
    research=service(tmp_path/'data');research.reports.worker=worker
    issuer=research.register(company());snapshot=published(research,issuer)
    job=research.reports.start(ReportCommand(company_id=issuer['company_id'],snapshot_id=snapshot['snapshot_id'],
        as_of='2026-02-01T00:00:00+00:00',source_mode='REUSE',idempotency_key='model'))
    for _ in range(5):job=research.reports.advance(job['job_id'])
    section=research.reports.sections(job)[0]
    assert section['status']=='FAILED'
    assert '<script>' not in section['rendered']
    run=research.analysis.read('report_runs','run_id',section['run_id'])
    assert run['evidence_kind']=='METHOD_CASE'
    command=json.loads(research.evidence.raw(run['command_archive']['sha256']).read_bytes())
    assert command['tools']==[] and command['model']==job['model']
    assert research.evidence.raw(run['candidate_output_archive']['sha256']).read_bytes()


def test_public_report_refresh_collects_financial_facts_and_binds_new_partial_shared_snapshot(tmp_path,monkeypatch):
    import json
    from fastapi.testclient import TestClient
    from roll.app import create_app
    from test_company_research_sources import setup
    from test_financial_statements import statements
    worker=tmp_path/'method-partial-analysis.py'
    worker.write_text('''import json,sys
c=json.loads(sys.stdin.readline());p=json.loads(c['prompt']);fid=p['evidence']['facts'][-1]['version_id']
claim=dict(text='New sourced financial evidence',fact_version_ids=[fid],gap_reason=None)
bad=dict(key='invalid',previous_version_id=None,business='REFINING',statement='Unsupported hypothesis',horizon='Next disclosure',observation_metrics=['operations'],support_fact_version_ids=['unknown-fact'],counter_fact_version_ids=[],invalidation_conditions=['Contrary disclosure'],next_validation_event=dict(description='Next disclosure',date=None,date_unknown_reason='No date',date_fact_version_ids=[]),gaps=['Missing support'],change_reason='METHOD invalid citation')
v=dict(company_id=p['company_id'],input_sha256=p['packet_sha256'],business_structure=[claim],attention_reasons=[claim],counterevidence=[],hypotheses=[bad],insufficient_hypotheses_reason='METHOD partial',limitations=['METHOD only'],valuation_unavailable_reason='No controlled valuation')
print(json.dumps(dict(kind='thread',model=c['model'],provider='METHOD',thread_id='method',instruction_sources=[])),flush=True)
print(json.dumps(dict(kind='completed',status='completed',output=json.dumps(v),error_info=None)),flush=True)
''',encoding='utf-8')
    auth=tmp_path/'method-auth.json';auth.write_text(json.dumps(dict(auth_mode='chatgpt',tokens=dict(access_token='METHOD_ONLY'))))
    monkeypatch.setenv('ROLL_CODEX_AUTH_FILE',str(auth))
    with TestClient(create_app(tmp_path/'data',runtime_role='API')) as client:
        issuer=setup(client,'akshare-financial-em');research=client.app.state.company_research
        old=published(research,issuer)
        client.app.state.financial_statements.worker=statements
        research.reports.collectors=[research.reports.collectors[1]]
        research.analysis_worker=worker
        research.reports.worker=worker  # Every model phase in this METHOD flow uses the local fake worker.
        response=client.post('/api/company-research/reports',json=dict(company_id=issuer['company_id'],as_of='2026-10-26T00:00:00+00:00',source_mode='REFRESH',idempotency_key='new-source'))
        assert response.status_code==201,response.text
        job=response.json()
        for _ in range(4):job=research.reports.advance(job['job_id'])
        assert job['snapshot_id']!=old['snapshot_id'],job
        accepted=client.get('/api/company-research/snapshots/'+job['snapshot_id']).json()
        assert accepted['rejections'][0]['code']=='UNKNOWN_CITATION'
        assert research.analysis_run(job['analysis_run_id'])['status']=='PARTIAL'
        packet=research.reports.input(job['input_id'])
        assert packet['payload']['snapshot']==accepted
        assert client.get('/api/company-research/companies/'+issuer['company_id']+'/daily').json()['snapshot']==accepted
        assert packet['payload']['facts'][-1]['value_type']=='NUMBER'
        assert client.get('/api/account').json()['version']==0


def test_report_comparison_keeps_peer_facts_in_their_own_company_context(tmp_path,monkeypatch):
    from roll.research.company.reports import ReportCommand
    from roll.research.company import MaterialCommand,FactCommand,AnalysisCommand
    from test_analysis_snapshots import candidate
    monkeypatch.delenv('ROLL_CODEX_AUTH_FILE',raising=False)
    research=service(tmp_path)
    issuer=research.register(company());main=published(research,issuer)
    peer=research.register(company('国际同业有限公司',['国际同业'],[dict(exchange='HKEX',code='00345',share_class='H',currency='HKD')]))
    from test_shared_evidence import material_input
    metadata=material_input(peer['company_id']);metadata.update(subject_name=peer['legal_name'],source_url='https://issuer.example/peer.json',media_type='application/json')
    material=research.import_material(MaterialCommand(**metadata),b'{"revenue":100,"gross_margin":0.3}')
    facts=[]
    for metric,value,unit in [('revenue','100','HKD_MILLION'),('gross_margin','0.3','ratio')]:
        metadata.update(unit=unit,currency='HKD' if metric=='revenue' else None)
        material=research.import_material(MaterialCommand(**metadata),b'{"revenue":100,"gross_margin":0.3}')
        facts.append(research.add_fact(FactCommand(company_id=peer['company_id'],material_id=material['material_id'],metric=metric,business='PLANT_BEVERAGE',value=value,
            unit=unit,currency='HKD' if metric=='revenue' else None,scope='CONSOLIDATED',period_start='2025-01-01',period_end='2025-12-31',table=metric,change_reason='METHOD exact peer raw JSON')))
    from roll.accounts.ledger import now
    packet=research.freeze_analysis(AnalysisCommand(company_id=peer['company_id'],as_of=now(),fact_version_ids=[f['version_id'] for f in facts]))
    snapshot=research.apply_analysis_candidate(packet['input_id'],candidate(packet,facts[0]))
    job=research.reports.start(ReportCommand(company_id=issuer['company_id'],snapshot_id=main['snapshot_id'],peer_snapshot_ids=[snapshot['snapshot_id']],
        as_of='2026-02-01T00:00:00+00:00',source_mode='REUSE',idempotency_key='peer'))
    for _ in range(4):job=research.reports.advance(job['job_id'])
    frozen=research.reports.input(job['input_id'])
    assert frozen['payload']['peer_facts'][0]['company_id']==peer['company_id']
    assert frozen['payload']['facts'][0]['company_id']==issuer['company_id']
    assert frozen['payload']['coverage']['peer_count']==1
    assert frozen['payload']['coverage']['international_peer_count']==1
    assert frozen['payload']['coverage']['peer_complete'] is False
    assert research.analysis_snapshot(main['snapshot_id'])==main


def test_report_cutoff_rejects_a_pinned_snapshot_with_later_reporting_period(tmp_path):
    import pytest
    from fastapi import HTTPException
    from roll.research.company.reports import ReportCommand
    research=service(tmp_path);issuer=research.register(company());snapshot=published(research,issuer)
    # This instant is Dec30 in Shanghai despite the input's Dec31 date.
    with pytest.raises(HTTPException) as error:
        research.reports.start(ReportCommand(company_id=issuer['company_id'],snapshot_id=snapshot['snapshot_id'],
            as_of='2025-12-31T00:30:00+14:00',source_mode='REUSE',idempotency_key='future-period'))
    assert error.value.detail['code']=='REPORT_PERIOD_AFTER_CUTOFF'


@pytest.mark.parametrize('media_type',['text/plain','application/pdf'])
def test_new_company_can_build_shared_business_research_from_verified_original_quote(tmp_path,monkeypatch,media_type):
    import json,httpx
    from roll.research.company.reports import ReportCommand
    worker=tmp_path/'method-source-analysis.py'
    worker.write_text('''import json,sys
c=json.loads(sys.stdin.readline());p=json.loads(c['prompt']);fid=p['evidence']['facts'][0]['version_id']
claim=dict(text='The issuer discloses beverage manufacturing',fact_version_ids=[fid],gap_reason=None)
v=dict(company_id=p['company_id'],input_sha256=p['packet_sha256'],business_structure=[claim],attention_reasons=[claim],counterevidence=[],hypotheses=[],insufficient_hypotheses_reason='Single disclosed operating quote',limitations=['Unknown units and unverified forecasts'],valuation_unavailable_reason='No numeric valuation facts')
print(json.dumps(dict(kind='thread',model=c['model'],provider='METHOD',thread_id='method',instruction_sources=[])),flush=True)
print(json.dumps(dict(kind='completed',status='completed',output=json.dumps(v),error_info=None)),flush=True)
''',encoding='utf-8')
    auth=tmp_path/'method-auth.json';auth.write_text(json.dumps(dict(auth_mode='chatgpt',tokens=dict(access_token='METHOD_ONLY'))))
    monkeypatch.setenv('ROLL_CODEX_AUTH_FILE',str(auth))
    research=service(tmp_path/'data');research.analysis_worker=worker
    issuer=research.register(company('新饮品公司',['新饮品'],[dict(exchange='SZSE',code='000848',share_class='A',currency='CNY')]))
    original=b'The issuer manufactures plant beverages. No forward volume guidance.'
    if media_type=='application/pdf':
        from pypdf import PdfWriter
        from pypdf.generic import NameObject,DictionaryObject,DecodedStreamObject
        import io
        writer=PdfWriter();page=writer.add_blank_page(width=600,height=800)
        stream=DecodedStreamObject();stream.set_data(b'BT /F1 12 Tf 50 740 Td (The issuer manufactures plant beverages.) Tj ET')
        page[NameObject('/Contents')]=writer._add_object(stream)
        page[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')})})})
        buffer=io.BytesIO();writer.write(buffer);original=buffer.getvalue()
    research.evidence.transport=httpx.MockTransport(lambda request:httpx.Response(200,content=original))
    material=dict(company_id=issuer['company_id'],source_id='issuer-primary',origin_root_id='primary-2025',source_url='https://static.cninfo.com.cn/finalpage/2026-01-01/primary.txt',
        subject_name=issuer['legal_name'],media_type=media_type,period_start='2025-01-01',period_end='2025-12-31')
    job=research.reports.start(ReportCommand(company_id=issuer['company_id'],as_of='2026-02-01T00:00:00+00:00',idempotency_key='new-business',
        sources=[dict(material=material,category='本体披露',identity_basis='METHOD explicit original issuer text')],
        source_quotes=[dict(source_index=0,page=1,quote='The issuer manufactures plant beverages.',business='PLANT_BEVERAGE')]))
    for _ in range(5):job=research.reports.advance(job['job_id'])
    assert job['snapshot_id'] and job['input_id'],job
    snapshot=research.analysis_snapshot(job['snapshot_id'])
    fact=research.fact(snapshot['fact_version_ids'][0])
    assert fact['value']=='The issuer manufactures plant beverages.' and fact['kind']=='DISCLOSED'
    assert fact['unit'] is None and fact['currency'] is None and fact['scope'] is None
    assert research.daily_view(issuer['company_id'])['snapshot']==snapshot
    assert research.reports.input(job['input_id'])['payload']['snapshot']==snapshot


def test_risk_workpaper_uses_host_arithmetic_and_does_not_self_approve_clear(tmp_path):
    from roll.research.company import MaterialCommand,FactCommand,AnalysisCommand
    from roll.research.company.reports import ReportCommand
    from roll.accounts.ledger import now
    from test_shared_evidence import material_input
    from test_analysis_snapshots import candidate
    research=service(tmp_path);issuer=research.register(company())
    metadata=material_input(issuer['company_id']);metadata.update(media_type='application/json')
    material=research.import_material(MaterialCommand(**metadata),b'{"goodwill":40,"equity":100}')
    facts=[]
    for metric,value in [('goodwill','40'),('equity','100')]:
        facts.append(research.add_fact(FactCommand(company_id=issuer['company_id'],material_id=material['material_id'],metric=metric,business='FINANCIAL_STATEMENT',
            value=value,unit='CNY_MILLION',currency='CNY',scope='CONSOLIDATED',period_start='2025-01-01',period_end='2025-12-31',table='/'+metric,change_reason='METHOD literal raw JSON')))
    packet=research.freeze_analysis(AnalysisCommand(company_id=issuer['company_id'],as_of=now(),fact_version_ids=[f['version_id'] for f in facts]))
    snapshot=research.apply_analysis_candidate(packet['input_id'],candidate(packet,facts[0]))
    job=research.reports.start(ReportCommand(company_id=issuer['company_id'],snapshot_id=snapshot['snapshot_id'],as_of=now(),source_mode='REUSE',idempotency_key='risk',
        risk_workpaper=[dict(number=7,fact_version_ids=[f['version_id'] for f in facts],candidate_outcome='CLEAR',reason='METHOD candidate incorrectly says clear')]))
    for _ in range(5):job=research.reports.advance(job['job_id'])
    frozen=research.reports.input(job['input_id'])
    item=next(i for i in frozen['payload']['landmines'] if i['number']==7)
    assert item['outcome']=='HIT'
    assert item['calculation']['ratio']=='0.4'
    assert item['workpaper_kind']=='DERIVED_WORKPAPER'
    assert any(i['outcome']=='UNKNOWN' for i in frozen['payload']['landmines'])


@pytest.mark.parametrize('text,expected',[
    ('本年度审计意见为标准的无保留意见。','UNKNOWN'),
    ('本年度审计意见为标准的无保留意见；审计机构本年度无变更；审计费用与上期相同。','CLEAR')])
def test_disclosure_screening_requires_all_item_topics_and_preserves_derived_status(tmp_path,text,expected):
    from roll.research.company import MaterialCommand,FactCommand,AnalysisCommand
    from roll.research.company.reports import ReportCommand
    from roll.accounts.ledger import now
    from test_shared_evidence import material_input
    from test_analysis_snapshots import candidate
    research=service(tmp_path);issuer=research.register(company())
    metadata=material_input(issuer['company_id']);metadata.update(unit=None,currency=None)
    material=research.import_material(MaterialCommand(**metadata),text.encode())
    fact=research.add_fact(FactCommand(company_id=issuer['company_id'],material_id=material['material_id'],metric='audit_opinion',business='AUDIT',
        value=text,value_type='TEXT',unit=None,currency=None,scope='CONSOLIDATED',period_start='2025-01-01',period_end='2025-12-31',table='RAW_TEXT_EXACT_QUOTE',change_reason='METHOD literal audit quotation'))
    packet=research.freeze_analysis(AnalysisCommand(company_id=issuer['company_id'],as_of=now(),fact_version_ids=[fact['version_id']]))
    snapshot=research.apply_analysis_candidate(packet['input_id'],candidate(packet,fact))
    row=dict(number=12,fact_version_ids=[fact['version_id']],candidate_outcome='CLEAR',review_method='DISCLOSURE_REVIEW',
        reason='按本年度披露核对意见类型、机构变更与费用，缺失信息必须保留未知，不能外推整个公司无风险。',
        disclosure_scope_reason='仅依据本年度公司合并审计披露的逐字原文；不是独立审计，也不是对公司未来风险背书。')
    job=research.reports.start(ReportCommand(company_id=issuer['company_id'],snapshot_id=snapshot['snapshot_id'],as_of=now(),source_mode='REUSE',idempotency_key='audit',risk_workpaper=[row]))
    for _ in range(5):job=research.reports.advance(job['job_id'])
    item=next(i for i in research.reports.input(job['input_id'])['payload']['landmines'] if i['number']==12)
    assert item['outcome']==expected
    assert item['workpaper_kind']=='DERIVED_WORKPAPER'
    assert item['coverage_outcome']==('PASS' if expected=='CLEAR' else 'UNKNOWN')


def test_model_markdown_subheads_are_kept_below_host_owned_structure(tmp_path,monkeypatch):
    import json
    from roll.research.company.reports import ReportCommand
    worker=tmp_path/'method-subhead-worker.py'
    worker.write_text('''import json,sys
c=json.loads(sys.stdin.readline());p=json.loads(c['prompt'])
v=dict(section_id=p['section_id'],input_sha256=p['input_sha256'],paragraphs=[dict(text='## Company view\\nEvidence remains incomplete.',fact_version_ids=[])],gaps=[])
print(json.dumps(dict(kind='thread',model=c['model'],provider='METHOD',thread_id='method',instruction_sources=[])),flush=True)
print(json.dumps(dict(kind='completed',status='completed',output=json.dumps(v),error_info=None)),flush=True)
''',encoding='utf-8')
    auth=tmp_path/'method-auth.json';auth.write_text(json.dumps(dict(auth_mode='chatgpt',tokens=dict(access_token='METHOD_ONLY'))))
    monkeypatch.setenv('ROLL_CODEX_AUTH_FILE',str(auth))
    research=service(tmp_path/'data');research.reports.worker=worker
    issuer=research.register(company());snapshot=published(research,issuer)
    job=research.reports.start(ReportCommand(company_id=issuer['company_id'],snapshot_id=snapshot['snapshot_id'],as_of='2026-02-01T00:00:00+00:00',source_mode='REUSE',idempotency_key='subhead'))
    for _ in range(5):job=research.reports.advance(job['job_id'])
    section=research.reports.sections(job)[0]
    assert section['status']=='COMPLETE'
    assert section['rendered'].startswith('#### Company view')
    assert '\n## ' not in section['rendered']


@pytest.mark.parametrize('text,expected',[
    ('WACC > g is a method condition.','COMPLETE'),
    ('需要五年数据，第九章解释方法。','COMPLETE'),
    ('利润率百分之四十，市值三百亿元。','FAILED')])
def test_chapter_comparisons_and_structural_counts_cannot_hide_chinese_financial_numbers(tmp_path,monkeypatch,text,expected):
    import json
    from roll.research.company.reports import ReportCommand
    worker=tmp_path/'method-number-worker.py'
    worker.write_text('''import json,sys
c=json.loads(sys.stdin.readline());p=json.loads(c['prompt'])
v=dict(section_id=p['section_id'],input_sha256=p['input_sha256'],paragraphs=[dict(text=TEXT,fact_version_ids=[])],gaps=[])
print(json.dumps(dict(kind='thread',model=c['model'],provider='METHOD',thread_id='method',instruction_sources=[])),flush=True)
print(json.dumps(dict(kind='completed',status='completed',output=json.dumps(v),error_info=None)),flush=True)
'''.replace('TEXT',repr(text)),encoding='utf-8')
    auth=tmp_path/'method-auth.json';auth.write_text(json.dumps(dict(auth_mode='chatgpt',tokens=dict(access_token='METHOD_ONLY'))))
    monkeypatch.setenv('ROLL_CODEX_AUTH_FILE',str(auth))
    research=service(tmp_path/'data');research.reports.worker=worker
    issuer=research.register(company());snapshot=published(research,issuer)
    job=research.reports.start(ReportCommand(company_id=issuer['company_id'],snapshot_id=snapshot['snapshot_id'],as_of='2026-02-01T00:00:00+00:00',source_mode='REUSE',idempotency_key='number'))
    for _ in range(5):job=research.reports.advance(job['job_id'])
    section=research.reports.sections(job)[0]
    assert section['status']==expected
    if expected=='FAILED':
        run=research.analysis.read('report_runs','run_id',section['run_id'])
        assert run['error']['code']=='UNBOUND_FINANCIAL_NUMBER'
        assert run['error']['context']['paragraph_index']==0


def test_frozen_chapter_payload_can_be_reviewed_locally_without_auth_or_model(tmp_path,monkeypatch):
    from roll.research.company.reports import ReportCommand
    monkeypatch.setenv('ROLL_CODEX_AUTH_FILE',str(tmp_path/'absent-auth.json'))
    research=service(tmp_path);issuer=research.register(company());snapshot=published(research,issuer)
    job=research.reports.start(ReportCommand(company_id=issuer['company_id'],snapshot_id=snapshot['snapshot_id'],as_of='2026-02-01T00:00:00+00:00',source_mode='REUSE',idempotency_key='preview'))
    for _ in range(4):job=research.reports.advance(job['job_id'])
    preview=research.reports.chapter_preview(job['job_id'],'1')
    assert preview['command']['tools']==[]
    assert preview['command']['model']=='gpt-6.1-sol'
    assert preview['input_sha256']==research.reports.input(job['input_id'])['packet_sha256']
    assert preview['command']['output_schema']['properties']['section_id']['type']=='string'
    assert research.reports.sections(job)==[]
    assert research.reports.get(job['job_id'])==job


@pytest.mark.parametrize('financial',[False,True])
def test_economic_coverage_distinguishes_explicit_baseline_and_valid_method_non_applicability(tmp_path,monkeypatch,financial):
    from test_economic_review import operating_request
    from roll.research.company.reports import ReportCommand
    from roll.accounts.ledger import now
    monkeypatch.delenv('ROLL_CODEX_AUTH_FILE',raising=False)
    research=service(tmp_path);command,_=operating_request(research)
    if financial:command.economic_basis['applicability']['category']='FINANCIAL'
    result=research.calculate_operating_valuation(command)
    job=research.reports.start(ReportCommand(company_id=result['company_id'],snapshot_id=result['snapshot_id'],as_of=now(),source_mode='REUSE',idempotency_key='econ-purpose',valuation_purpose='BASELINE_RESEARCH'))
    for _ in range(22):
        job=research.reports.advance(job['job_id'])
        if job['report_id']:break
    report=research.reports.read(job['report_id'])
    economic=next(r for r in report['quality']['host_rules'] if r['rule_id']=='roll-economic-use')
    assert economic['outcome']=='PASS'
    assert research.valuation_presentation(result['review_id'],'CURRENT_PRICING')['usable_range'] is False
    assert research.economic_review(result['review_id'])['status']==('blocked' if financial else 'conditional')
    assert report['completeness']=='PARTIAL'  # Other missing chapter/source coverage remains.


def test_shared_worker_yields_report_phases_to_daily_and_rotates_reports(tmp_path,monkeypatch):
    import time
    from roll.app import create_app
    from roll.market.directory import WatchCommand
    from roll.runtime.observation_updates import UpdateSettings,UpdateRequest
    from roll.research.company.reports import ReportCommand
    monkeypatch.delenv('ROLL_CODEX_AUTH_FILE',raising=False)
    app=create_app(tmp_path,runtime_role='API');research=app.state.company_research;reviews=app.state.reviews;market=app.state.market
    issuer=research.register(company());snapshot=published(research,issuer)
    market.watch(WatchCommand(instrument='SSE:600362',operation='ADD',expected_list_version=market.listing()['version']))
    app.state.observation_updates.configure('SSE:600362',UpdateSettings(enabled=True,expected_revision=1,basis='METHOD fairness observation'))
    jobs=[research.reports.start(ReportCommand(company_id=issuer['company_id'],snapshot_id=snapshot['snapshot_id'],as_of='2026-02-01T00:00:00+00:00',source_mode='REUSE',idempotency_key='fair-'+str(i))) for i in range(2)]
    reviews.worker_enabled=True;reviews.start()
    try:
        deadline=time.monotonic()+20
        while time.monotonic()<deadline:
            values=[research.reports.get(j['job_id']) for j in jobs]
            if all(v['section_ids'] for v in values):break
            time.sleep(.01)
        assert all(v['section_ids'] for v in values),values
        assert abs(len(values[0]['checkpoints'])-len(values[1]['checkpoints']))<=1
        daily=app.state.observation_updates.submit('SSE:600362',UpdateRequest(kind='RESEARCH',idempotency_key='during-report',basis='METHOD daily during chapter generation'))
        while time.monotonic()<deadline:
            saved=app.state.observation_updates.get(daily['job_id'])
            if saved['status'] in {'COMPLETE','PARTIAL','FAILED'}:break
            time.sleep(.01)
        assert saved['status']=='COMPLETE',saved
        assert not any(research.reports.get(j['job_id'])['report_id'] for j in jobs)
    finally:
        reviews.close();app.state.assistance.close()


def test_report_dead_owner_recovers_fixed_input_and_queue_is_bounded(tmp_path,monkeypatch):
    import json
    from fastapi import HTTPException
    from roll.research.company.service import record
    from roll.research.company.reports import ReportCommand
    monkeypatch.delenv('ROLL_CODEX_AUTH_FILE',raising=False)
    research=service(tmp_path);issuer=research.register(company());snapshot=published(research,issuer)
    command=dict(company_id=issuer['company_id'],snapshot_id=snapshot['snapshot_id'],as_of='2026-02-01T00:00:00+00:00',source_mode='REUSE')
    job=research.reports.start(ReportCommand(**command,idempotency_key='interrupted'))
    for _ in range(4):job=research.reports.advance(job['job_id'])
    fixed=job['input_id']
    # External durable-state fixture: the owner process died between checkpoints.
    broken={k:v for k,v in job.items() if k!='content_sha256'}
    broken.update(status='RUNNING',host_owner=dict(pid=4294967290,creation_ticks=1))
    with research.ledger.connection() as db:db.execute('UPDATE company_research_jobs SET value=? WHERE job_id=?',(json.dumps(record(broken)),job['job_id']))
    recovered=service(tmp_path)
    assert recovered.reports.get(job['job_id'])['status']=='INTERRUPTED'
    assert recovered.reports.retry(job['job_id'])['input_id']==fixed
    for i in range(15):recovered.reports.start(ReportCommand(**command,idempotency_key='bound-'+str(i)))
    with pytest.raises(HTTPException) as error:recovered.reports.start(ReportCommand(**command,idempotency_key='queue-overflow'))
    assert error.value.detail['code']=='QUEUE_FULL'
