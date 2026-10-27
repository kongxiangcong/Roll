"""Public host rendering seam, independently bound append-only report revisions."""
import pytest
from fastapi import HTTPException
from test_shared_evidence import service, company
from test_daily_research import published


def packet_with_fact(tmp_path, unit='unit', currency='CNY'):
    from roll.research.company.reports import ReportCommand
    research=service(tmp_path);issuer=research.register(company());snapshot=published(research,issuer)
    job=research.reports.start(ReportCommand(company_id=issuer['company_id'],snapshot_id=snapshot['snapshot_id'],as_of='2026-02-01T00:00:00+00:00',source_mode='REUSE',idempotency_key='render'))
    for _ in range(4):job=research.reports.advance(job['job_id'])
    packet=research.reports.input(job['input_id'])
    fact=packet['payload']['facts'][0]
    fact.update(value='802208126.13',value_type='NUMBER',unit=unit,currency=currency)
    material=next(m for m in packet['payload']['materials'] if m['material_id']==fact['material_id'])
    material['limitations']=['unit=unit means whole CNY with unchanged numeric scale; share means individual shares']
    return research,job,packet,fact


def test_literal_money_keeps_evidenced_currency_scale_in_prose_and_table(tmp_path):
    from roll.research.company.report_runtime import ReportRuntime
    research,job,packet,fact=packet_with_fact(tmp_path)
    token='{{fact:'+fact['version_id']+'}}'
    candidate=dict(section_id='1',input_sha256=packet['packet_sha256'],paragraphs=[dict(text='披露金额为'+token+'。\n|项目|值|\n|---|---|\n|金额|'+token+'|',fact_version_ids=[fact['version_id']])],gaps=[])
    rendered,refs=ReportRuntime(research.reports).validate(candidate,packet,'1')
    assert rendered.count('802208126.13 元（CNY）')==2
    assert '802208126.13 unit' not in rendered


@pytest.mark.parametrize('text',['定义最小观察单位为同规格产品的一罐，或规格固定的一箱。销量与单位毛利未知。','公司销售一箱产品。','公司利润率百分之四十。','公司毛利为三百万元。'])
def test_conceptual_unit_definition_is_distinct_from_company_quantity(tmp_path,text):
    from roll.research.company.report_runtime import ReportRuntime
    research,job,packet,fact=packet_with_fact(tmp_path)
    candidate=dict(section_id='2',input_sha256=packet['packet_sha256'],paragraphs=[dict(text=text,fact_version_ids=[])],gaps=[])
    if text.startswith('定义'):
        assert '一箱' in ReportRuntime(research.reports).validate(candidate,packet,'2')[0]
    else:
        with pytest.raises(HTTPException):ReportRuntime(research.reports).validate(candidate,packet,'2')


def test_revision_keeps_parent_and_frozen_input_and_uses_distinct_code_provenance(tmp_path,monkeypatch):
    from roll.research.company.report_revisions import RevisionCommand
    from roll.research.company.report_template import SECTIONS
    from roll.research.company.report_archive import archive
    from roll.research.company.service import record
    from roll.accounts.ledger import encode
    monkeypatch.delenv('ROLL_CODEX_AUTH_FILE',raising=False)
    research,parent,packet,fact=packet_with_fact(tmp_path)
    # Reload the immutable fixture rather than the local rendering-only mutations above.
    packet=research.reports.input(parent['input_id'])
    commands={sid:research.reports.chapter_preview(parent['job_id'],sid) for sid in SECTIONS}
    plan=record(dict(parent_job_id=parent['job_id'],input_id=packet['input_id'],input_sha256=packet['packet_sha256'],model=packet['model'],generation_code_hashes=packet['code_hashes'],commands={sid:dict(sha256=c['command_sha256'],archive=archive(research.evidence,encode(c['command']).encode(),'METHOD_COMMAND')) for sid,c in commands.items()}))
    digest=archive(research.evidence,encode(plan).encode(),'METHOD_PLAN')['sha256']
    cancelled=research.reports.cancel(parent['job_id']);original=research.reports.input(packet['input_id'])
    command=RevisionCommand(parent_job_id=parent['job_id'],command_plan_sha256=digest,idempotency_key='revision')
    job=research.reports.revise(command)
    assert research.reports.revise(command)==job
    revision=research.reports.revision(job['host_revision_id'])
    assert revision['generation_code_hashes']==packet['code_hashes']
    assert revision['host_version']=='08.5' and revision['missing_model_calls']==12
    assert research.reports.get(parent['job_id'])==cancelled
    assert research.reports.input(packet['input_id'])==original
    preview=research.reports.chapter_preview(job['job_id'],'9')
    import json
    assert json.loads(preview['command']['prompt'])['fixed_valuation_context']['source_input_sha256']==packet['packet_sha256']
    for _ in range(15):
        job=research.reports.advance(job['job_id'])
        if job['report_id']:break
    assert job['status']=='PARTIAL',job
    report=research.reports.read(job['report_id'])
    assert report['host_revision_id']==revision['revision_id']
    assert report['report_id']!=packet['report_id']
    markdown=research.reports.markdown(report['report_id'])
    assert revision['revision_id'] in markdown
    assert research.reports.get(parent['job_id'])==cancelled
    from roll.research.company.report_integrity import validate_reports
    with research.ledger.connection() as db:
        archives={row[0]:json.loads(row[1]) for row in db.execute('SELECT sha256,value FROM evidence_archives')}
        validate_reports(db,archives)


def test_revalidation_quarantines_bound_raw_location_without_changing_failed_attempt(tmp_path,monkeypatch):
    import json
    from roll.accounts.ledger import encode
    from roll.research.company.report_template import SECTIONS
    from roll.research.company.report_archive import archive
    from roll.research.company.service import record
    from roll.research.company.report_revisions import RevisionCommand
    research,parent,packet,fact=packet_with_fact(tmp_path/'data')
    packet=research.reports.input(parent['input_id'])
    worker=tmp_path/'method-worker.py'
    worker.write_text('''import json,sys
c=json.loads(sys.stdin.readline());p=json.loads(c['prompt'])
print(json.dumps({'kind':'thread','model':c['model'],'provider':'METHOD','thread_id':'method','instruction_sources':[]}),flush=True)
print(json.dumps({'kind':'completed','status':'completed','output':json.dumps({'section_id':p['section_id'],'input_sha256':p['input_sha256'],'paragraphs':[{'text':'公司利润率百分之四十。','fact_version_ids':[]},{'text':'研究仍需核对。','fact_version_ids':[]}],'gaps':[]})}),flush=True)
''',encoding='utf-8')
    auth=tmp_path/'method-auth.json';auth.write_text(json.dumps({'auth_mode':'chatgpt','tokens':{'access_token':'METHOD_NOT_A_REAL_CREDENTIAL'}}))
    monkeypatch.setenv('ROLL_CODEX_AUTH_FILE',str(auth));research.reports.worker=worker
    parent=research.reports.advance(parent['job_id']);old_section=research.reports.sections(parent)[0]
    assert old_section['status']=='FAILED'
    old_run=research.analysis.read('report_runs','run_id',old_section['run_id'])
    commands={sid:research.reports.chapter_preview(parent['job_id'],sid) for sid in SECTIONS}
    plan=record(dict(parent_job_id=parent['job_id'],input_id=packet['input_id'],input_sha256=packet['packet_sha256'],model=packet['model'],generation_code_hashes=packet['code_hashes'],commands={sid:dict(sha256=c['command_sha256'],archive=archive(research.evidence,encode(c['command']).encode(),'METHOD_COMMAND')) for sid,c in commands.items()}))
    digest=archive(research.evidence,encode(plan).encode(),'METHOD_PLAN')['sha256']
    parent=research.reports.cancel(parent['job_id'])
    finding=dict(section_id='1',output_sha256=old_section['output_archive']['sha256'],location='PARAGRAPH',index=0,reason='METHOD unsupported financial claim; quarantine rather than endorsement',missing_basis='No frozen original source supports the asserted margin')
    bad={**finding,'output_sha256':'0'*64}
    with pytest.raises(HTTPException):research.reports.revise(RevisionCommand(parent_job_id=parent['job_id'],command_plan_sha256=digest,idempotency_key='bad',findings=[bad]))
    duplicate={**finding,'index':1}
    with pytest.raises(HTTPException) as duplicated:
        research.reports.revise(RevisionCommand(parent_job_id=parent['job_id'],command_plan_sha256=digest,idempotency_key='duplicate-last',findings=[duplicate,duplicate]))
    assert duplicated.value.detail['code']=='REVISION_FINDING_INVALID'
    command=RevisionCommand(parent_job_id=parent['job_id'],command_plan_sha256=digest,idempotency_key='quarantine',findings=[finding])
    job=research.reports.revise(command);revision=research.reports.revision(job['host_revision_id'])
    assert revision['missing_model_calls']==11
    job=research.reports.advance(job['job_id']);section=research.reports.sections(job)[0]
    assert section['status']=='COMPLETE' and section['model_calls']==0
    assert section['run_id']==old_run['run_id'] and section['source_section_version_id']==old_section['section_version_id']
    assert '研究仍需核对' in section['rendered']
    assert '百分之四十' not in section['rendered'] and '研究限制' in section['rendered']
    assert research.analysis.read('report_runs','run_id',old_run['run_id'])==old_run
    assert research.analysis.read('report_sections','section_version_id',old_section['section_version_id'])==old_section
    assert research.reports.get(parent['job_id'])==parent
    from roll.research.company import report_revisions
    monkeypatch.setattr(report_revisions,'code_hashes',lambda:{'future-policy':'changed'})
    with pytest.raises(HTTPException):research.reports.chapter_preview(job['job_id'],'2')
    assert research.reports.sections(job)[0]==section
    from roll.research.company.report_integrity import validate_reports
    with research.ledger.connection() as db:
        archives={row[0]:json.loads(row[1]) for row in db.execute('SELECT sha256,value FROM evidence_archives')};validate_reports(db,archives)
        from roll.research.company.service import record
        def reject_changed(table,key,original,changes):
            changed=record({k:v for k,v in original.items() if k!='content_sha256'}|changes)
            db.execute('UPDATE company_research_'+table+' SET value=? WHERE '+key+'=?',(encode(changed),original[key]))
            with pytest.raises(HTTPException):validate_reports(db,archives)
            db.execute('UPDATE company_research_'+table+' SET value=? WHERE '+key+'=?',(encode(original),original[key]))
        reject_changed('jobs','job_id',job,dict(host_revision_archive=packet['input_archive']))
        reject_changed('report_revisions','revision_id',revision,dict(compiler_version='unarchived drift'))
        reject_changed('report_runs','run_id',old_run,dict(job_id='not-a-job',host_revision_id=revision['revision_id'],execution_code_hashes=revision['execution_code_hashes']))
        reject_changed('report_sections','section_version_id',section,dict(source_section_version_id='unregistered-source'))
        from roll.research.company.service import record
        corrupted=record({k:v for k,v in section.items() if k!='content_sha256'}|dict(host_revision_id='unknown'))
        db.execute('UPDATE company_research_report_sections SET value=? WHERE section_version_id=?',(encode(corrupted),section['section_version_id']))
        with pytest.raises(HTTPException):validate_reports(db,archives)


def test_fresh_report_preview_includes_only_its_fixed_model_and_typed_host_tables(tmp_path,monkeypatch):
    import json
    from test_economic_review import operating_request
    from roll.research.company.reports import ReportCommand
    from roll.accounts.ledger import now
    monkeypatch.delenv('ROLL_CODEX_AUTH_FILE',raising=False)
    research=service(tmp_path);command,_=operating_request(research)
    result=research.calculate_operating_valuation(command)
    job=research.reports.start(ReportCommand(company_id=result['company_id'],snapshot_id=result['snapshot_id'],as_of=now(),source_mode='REUSE',idempotency_key='context'))
    for _ in range(4):job=research.reports.advance(job['job_id'])
    packet=research.reports.input(job['input_id'])
    for sid in ['3','9','REVIEW']:
        preview=research.reports.chapter_preview(job['job_id'],sid);prompt=json.loads(preview['command']['prompt'])
        context=prompt['fixed_valuation_context']
        assert context['operating_model_id']==result['operating_model_id']
        assert context['source_input_sha256']==packet['packet_sha256']
        assert context['assumptions']==packet['payload']['valuation_binding']['fixed_operating_model']['assumptions']
        assert context['scenario_drivers'] and context['annual_cashflows']
        assert len(preview['command']['prompt'].encode())<262144 and preview['command']['tools']==[]
    assert packet['template']['version']=='08.5'
    assert '百万元（CNY）' in packet['payload']['valuation_subsections']['3']
    assert '百万股' in packet['payload']['valuation_subsections']['4']
    from roll.research.company.report_values import typed_packet
    # A legitimate generic-unit target must never inherit a million-source scale by association.
    import copy
    converted=copy.deepcopy(packet);converted['payload']['valuation_binding']['fixed_operating_model']['config']['metadata']['amount_unit']='unit'
    assert '单位/尺度未知（CNY）' in typed_packet(converted)['payload']['valuation_subsections']['3']
