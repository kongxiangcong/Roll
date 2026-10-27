"""Sourceful appendix and honest per-category source bookkeeping public seams."""
from test_shared_evidence import service,company,material_input
from test_daily_research import published
from roll.research.company.reports import ReportCommand
import pytest


def test_reuse_ledger_distinguishes_no_check_from_an_actual_failed_attempt(tmp_path):
    import httpx
    research=service(tmp_path);issuer=research.register(company());snapshot=published(research,issuer)
    def request(key,**extra):
        job=research.reports.start(ReportCommand(company_id=issuer['company_id'],snapshot_id=snapshot['snapshot_id'],as_of='2026-02-01T00:00:00+00:00',idempotency_key=key,**extra))
        for _ in range(4):job=research.reports.advance(job['job_id'])
        return job,research.reports.input(job['input_id'])
    reused,packet=request('reuse-ledger',source_mode='REUSE')
    book=packet['payload']['source_coverage']
    assert set(book['categories'])=={'本体披露','行业时序','产业链','同业对照','估值序列','研报','官方监管'}
    assert all(not c['attempts'] for c in book['categories'].values())
    assert '已试当前已配置来源' not in book['ledger_markdown']
    assert '本次未发起' in book['ledger_markdown']
    research.evidence.transport=httpx.MockTransport(lambda r:httpx.Response(503))
    metadata=material_input(issuer['company_id']);metadata.update(source_url='https://www.stats.gov.cn/report.txt')
    failed,packet=request('failed-ledger',sources=[dict(material=metadata,category='行业时序',identity_basis='METHOD explicitly scoped statistical source attempt')])
    row=packet['payload']['source_coverage']['categories']['行业时序']
    assert row['state']=='FAILED'
    assert len(row['attempts'])==1 and row['attempts'][0]['status']=='FAILED'
    assert row['attempts'][0]['check_id']==failed['acquisition']['receipts'][0]['check_id']
    assert row['attempts'][0]['relation']=='CURRENT_JOB'
    assert packet['payload']['source_coverage']['categories']['产业链']['state']=='NOT_CHECKED'


def test_verified_source_quotes_enable_appendix_topics_without_model_self_certification(tmp_path,monkeypatch):
    from roll.research.company import MaterialCommand,AnalysisCommand
    from test_analysis_snapshots import candidate
    monkeypatch.delenv('ROLL_CODEX_AUTH_FILE',raising=False)
    research=service(tmp_path);issuer=research.register(company())
    topics=['company_history','capital_event','ownership_structure','governance','capacity_technology','channel_structure','staff_structure']
    statements=['公司由原厂改制成立，沿革及主体承接关系按本期报告列示。','本期未发行新股，股本及现金分红方案按原文披露。','控股股东的持股范围和股权关系按原文披露，不外推控制风险。','董事会及审计委员会的职责按本期治理规则列示，不构成独立治理评价。','公司生产工艺和产线配置按本期披露列示，不外推未来投产能力。','公司通过经销渠道及直销网络销售产品，地区口径按本期披露。','本期员工人员结构按岗位与学历列示，不把人数直接当作劳动生产率。']
    quotes={topic:'METHOD '+statement+' 仅用于工程测试，未声称真实发行人事实。' for topic,statement in zip(topics,statements)}
    metadata=material_input(issuer['company_id']);material=research.import_material(MaterialCommand(**metadata),'\n'.join(quotes.values()).encode())
    quotes['term_definition']='测试术语：本条是工程资料中的专门定义，不是实际公司事实或评级。'
    # Keep the exact definition inside the registered original, with a separate literal proof.
    metadata['source_id']='METHOD-appendix-with-definition'
    material=research.import_material(MaterialCommand(**metadata),'\n'.join(quotes.values()).encode())
    source_job=research.reports.start(ReportCommand(company_id=issuer['company_id'],as_of='2026-02-01T00:00:00+00:00',source_mode='REUSE',idempotency_key='appendix-quotes',source_quotes=[dict(material_id=material['material_id'],page=1,metric=topic,business='METHOD_ISSUER_DISCLOSURE',quote=text) for topic,text in quotes.items()]))
    source_job=research.reports.advance(source_job['job_id'])
    for _ in quotes:source_job=research.reports.advance(source_job['job_id'])
    assert source_job['stage']=='SHARED_FACTS'
    facts=[research.fact(r['fact_version_id']) for r in source_job['quote_receipts']]
    from roll.accounts.ledger import now
    analysis=research.freeze_analysis(AnalysisCommand(company_id=issuer['company_id'],as_of=now(),fact_version_ids=[f['version_id'] for f in facts]))
    proposed=candidate(analysis,facts[0])
    for claim in [*proposed['business_structure'],*proposed['attention_reasons']]:
        claim['text']+=' 测试术语仅用于本合成案例。';claim['fact_version_ids'].append(facts[-1]['version_id'])
    snapshot=research.apply_analysis_candidate(analysis['input_id'],proposed)
    research.reports.cancel(source_job['job_id'])
    job=research.reports.start(ReportCommand(company_id=issuer['company_id'],snapshot_id=snapshot['snapshot_id'],as_of='2026-02-01T00:00:00+00:00',source_mode='REUSE',idempotency_key='appendix-publish',parent_job_id=source_job['job_id']))
    for _ in range(4):job=research.reports.advance(job['job_id'])
    packet=research.reports.input(job['input_id'])
    # A forged book with recomputed hashes and a newly archived payload still needs a real quote job.
    import copy,json
    from roll.accounts.ledger import encode
    from roll.research.company.service import record,fingerprint
    from roll.research.company.report_archive import archive
    from roll.runtime.backups import Backups,restore_at_start
    from fastapi import HTTPException
    broken=copy.deepcopy(packet);book=broken['payload']['source_coverage'];book['quote_proofs'][0]['job_id']='unregistered-source-job'
    broken['payload']['source_coverage']=record({k:v for k,v in book.items() if k!='content_sha256'})
    broken['packet_sha256']=fingerprint(broken['payload']);broken['input_archive']=archive(research.evidence,encode(broken['payload']).encode(),'METHOD_FORGED_REPORT_INPUT')
    broken=record({k:v for k,v in broken.items() if k!='content_sha256'})
    with research.transaction() as db:db.execute('UPDATE company_research_report_inputs SET value=? WHERE input_id=?',(encode(broken),packet['input_id']))
    with pytest.raises(HTTPException) as bad:Backups(tmp_path).create()
    assert bad.value.detail['code']=='RESEARCH_REFERENCE_INVALID'
    with research.transaction() as db:db.execute('UPDATE company_research_report_inputs SET value=? WHERE input_id=?',(encode(packet),packet['input_id']))
    for _ in range(23):
        job=research.reports.advance(job['job_id'])
        if job['report_id']:break
    assert job['status']=='PARTIAL',job
    packet=research.reports.input(job['input_id']);report=research.reports.read(job['report_id']);md=research.reports.markdown(report['report_id'])
    assert packet['payload']['source_coverage']['appendices']=={'A':'PASS','B':'PASS','C':'PASS'}
    for topic,text in quotes.items():assert text in md
    for key,next_key in [('A','B'),('B','C'),('C','D')]:
        appendix=md.split('# 附录 '+key+' ')[1].split('# 附录 '+next_key+' ')[0]
        assert '/api/company-research/materials/'+material['material_id']+'/original' in appendix
        assert '尚未取得足够有据资料' not in appendix
    glossary=md.split('# 附录 H ')[1].split('# 附录 I ')[0]
    assert 'FCFF' in glossary and '9.3' in glossary
    assert '测试术语' in glossary and '定义原件' in glossary
    assert '/api/company-research/materials/'+material['material_id']+'/original' in glossary
    assert 'EV/EBITDA' not in glossary  # unused terms are not padding
    assert report['core_sha256']==snapshot['core_sha256']
    assert research.ledger.account()['version']==0
    backup=Backups(tmp_path);bundle=backup.export(backup.create()['backup_id']);target=tmp_path.with_name(tmp_path.name+'-recovered')
    restore=Backups(target);restore.stage_restore(bundle);restore_at_start(restore);recovered=service(target)
    assert recovered.reports.read(report['report_id'])==report
    assert recovered.reports.markdown(report['report_id'])==md


def test_explicit_parent_final_receipt_is_history_not_current_or_unrelated_latest(tmp_path):
    import httpx
    research=service(tmp_path);issuer=research.register(company());snapshot=published(research,issuer)
    research.evidence.transport=httpx.MockTransport(lambda r:httpx.Response(200,content=b'METHOD primary source retained without numeric inference'))
    source=dict(material={**material_input(issuer['company_id']),'source_url':'https://static.cninfo.com.cn/report.txt'},category='本体披露',identity_basis='METHOD fixed explicit source registration')
    parent=research.reports.start(ReportCommand(company_id=issuer['company_id'],snapshot_id=snapshot['snapshot_id'],as_of='2026-02-01T00:00:00+00:00',idempotency_key='history-source',sources=[source]))
    parent=research.reports.advance(parent['job_id']);receipt=parent['acquisition']['receipts'][0]
    material=research.material(receipt['material_id']);assert material['upstream']['acquisition']['status']=='FAILED'
    research.reports.cancel(parent['job_id'])
    research.evidence.transport=httpx.MockTransport(lambda r:httpx.Response(503))
    unrelated=research.reports.start(ReportCommand(company_id=issuer['company_id'],snapshot_id=snapshot['snapshot_id'],as_of='2026-02-01T00:00:00+00:00',idempotency_key='unrelated-source',sources=[source]))
    research.reports.advance(unrelated['job_id']);research.reports.cancel(unrelated['job_id'])
    job=research.reports.start(ReportCommand(company_id=issuer['company_id'],snapshot_id=snapshot['snapshot_id'],as_of='2026-02-01T00:00:00+00:00',source_mode='REUSE',parent_job_id=parent['job_id'],additional_material_ids=[material['material_id']],idempotency_key='history-reuse'))
    for _ in range(4):job=research.reports.advance(job['job_id'])
    book=research.reports.input(job['input_id'])['payload']['source_coverage'];attempts=book['categories']['本体披露']['attempts']
    assert len(attempts)==1 and attempts[0]['check_id']==receipt['check_id']
    assert attempts[0]['status']=='SUCCESS' and attempts[0]['relation']=='EXPLICIT_PARENT_HISTORY'
    assert '原材料登记的中间状态 FAILED 保留' in book['ledger_markdown']
    assert '本次未发起' in book['ledger_markdown']
    assert research.material(material['material_id'])==material


def test_registered_collector_empty_is_a_real_check_without_new_records_not_risk_clear(tmp_path):
    research=service(tmp_path);issuer=research.register(company());snapshot=published(research,issuer)
    class Collector:
        async def collect(self,instrument,command):return dict(run_id='METHOD-empty-run',status='EMPTY',network_calls=0,evidence_kind='METHOD_CASE')
    research.reports.collectors=[dict(service=Collector(),command=lambda **kw:kw,source_id='akshare-financial-supplement')]
    job=research.reports.start(ReportCommand(company_id=issuer['company_id'],snapshot_id=snapshot['snapshot_id'],as_of='2026-02-01T00:00:00+00:00',idempotency_key='collector-empty'))
    for _ in range(4):job=research.reports.advance(job['job_id'])
    book=research.reports.input(job['input_id'])['payload']['source_coverage'];row=book['categories']['本体披露']
    assert row['state']=='CHECKED_NO_NEW_RECORDS' and row['attempts'][0]['source_status']=='EMPTY'
    assert row['attempts'][0]['evidence_kind']=='METHOD_CASE'
    assert '已查无新增记录' in book['ledger_markdown']
    assert '经营未变' in book['ledger_markdown'] and '不代表经营未变' in book['ledger_markdown']


def test_external_valuation_legacy_default_role_cannot_support_issuer_coverage(tmp_path):
    from roll.research.company import MaterialCommand,FactCommand
    from test_analysis_snapshots import freeze,candidate
    research=service(tmp_path);issuer=research.register(company())
    metadata=material_input(issuer['company_id']);metadata.update(unit='ratio',currency=None)
    material=research.import_material(MaterialCommand(**metadata),b'METHOD external rate source; issuer subject is legacy metadata, not evidence of issuer disclosure')
    fact=research.add_fact(FactCommand(company_id=issuer['company_id'],material_id=material['material_id'],business='EXTERNAL_VALUATION_INPUT',metric='risk_free',value='.04',unit='ratio',currency=None,scope='CONSOLIDATED',period_start='2025-01-01',period_end='2025-12-31',page='JSON /rate',change_reason='METHOD external context'))
    packet=freeze(research,issuer,fact);snapshot=research.apply_analysis_candidate(packet['input_id'],candidate(packet,fact))
    job=research.reports.start(ReportCommand(company_id=issuer['company_id'],snapshot_id=snapshot['snapshot_id'],as_of='2026-02-01T00:00:00+00:00',source_mode='REUSE',idempotency_key='external-role'))
    for _ in range(4):job=research.reports.advance(job['job_id'])
    packet=research.reports.input(job['input_id']);book=packet['payload']['source_coverage']
    assert packet['payload']['references'][0]['source_role']=='EXTERNAL_VALUATION_INPUT'
    assert packet['payload']['references'][0]['source_subject'] is None # legacy issuer subject cannot establish who authored an external rate
    assert packet['payload']['references'][0]['declared_subject_name']==issuer['legal_name']
    assert book['fact_source_roles'][fact['version_id']]=='EXTERNAL_VALUATION_INPUT'
    assert book['categories']['本体披露']['material_ids']==[]
    assert book['categories']['估值序列']['material_ids']==[material['material_id']]
    assert '不是发行人披露' in book['ledger_markdown'] and '不等于完整历史价格' in book['ledger_markdown']


@pytest.mark.parametrize('literal_verified',[False,True])
def test_topic_label_or_literal_unknown_does_not_complete_appendix(tmp_path,literal_verified):
    from roll.research.company import MaterialCommand,FactCommand
    from test_analysis_snapshots import freeze,candidate
    research=service(tmp_path);issuer=research.register(company())
    text='公司成立及沿革资料本期未提供；这一逐字来源只能说明资料缺口，不能充作完整历史核查。'
    material=research.import_material(MaterialCommand(**material_input(issuer['company_id'])),text.encode())
    parent=None
    if literal_verified:
        source=research.reports.start(ReportCommand(company_id=issuer['company_id'],as_of='2026-02-01T00:00:00+00:00',source_mode='REUSE',idempotency_key='unknown-quote',source_quotes=[dict(material_id=material['material_id'],page=1,metric='company_history',business='METHOD_ISSUER',quote=text)]))
        source=research.reports.advance(source['job_id']);source=research.reports.advance(source['job_id'])
        fact=research.fact(source['quote_receipts'][0]['fact_version_id']);research.reports.cancel(source['job_id']);parent=source['job_id']
    else:
        fact=research.add_fact(FactCommand(company_id=issuer['company_id'],material_id=material['material_id'],metric='company_history',business='METHOD_ISSUER',value=text,value_type='TEXT',unit=material['unit'],currency=material['currency'],scope=material['scope'],period_start=material['period_start'],period_end=material['period_end'],table='RAW_TEXT_EXACT_QUOTE',change_reason='METHOD merely declares a quote without a registered host proof'))
    analysis=freeze(research,issuer,fact);snapshot=research.apply_analysis_candidate(analysis['input_id'],candidate(analysis,fact))
    job=research.reports.start(ReportCommand(company_id=issuer['company_id'],snapshot_id=snapshot['snapshot_id'],as_of='2026-02-01T00:00:00+00:00',source_mode='REUSE',idempotency_key='unknown-appendix',parent_job_id=parent))
    for _ in range(4):job=research.reports.advance(job['job_id'])
    book=research.reports.input(job['input_id'])['payload']['source_coverage']
    assert len(book['quote_proofs'])==int(literal_verified)
    assert book['appendices']['A']=='UNKNOWN' and book['appendix_rows']['A']==[]
