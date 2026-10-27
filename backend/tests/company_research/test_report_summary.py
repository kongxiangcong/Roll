"""Host summary reads fixed evidence; it neither invents data nor revalues the core."""
from test_shared_evidence import service,company
from test_daily_research import published
from roll.research.company.reports import ReportCommand


def test_core_backed_part_and_overview_do_not_default_to_missing_everywhere(tmp_path,monkeypatch):
    monkeypatch.delenv('ROLL_CODEX_AUTH_FILE',raising=False)
    research=service(tmp_path);issuer=research.register(company());snapshot=published(research,issuer)
    job=research.reports.start(ReportCommand(company_id=issuer['company_id'],snapshot_id=snapshot['snapshot_id'],as_of='2026-02-01T00:00:00+00:00',source_mode='REUSE',idempotency_key='overview'))
    for _ in range(23):
        job=research.reports.advance(job['job_id'])
        if job['report_id']:break
    md=research.reports.markdown(job['report_id']);overview=md.split('# 第一部分')[0]
    for title in ['核心经营模型','优势','风险','公司档案卡','尚未核实']:
        assert title in overview
    assert snapshot['core']['hypotheses'][0]['invalidation_conditions'][0] in overview
    first=md.split('# 第一部分')[1].split('## 1.')[0]
    assert snapshot['core']['business_structure'][0]['text'] in first
    assert '证据覆盖不足，相关结论须保留条件和未完成项。' not in first
    assert '未形成有源分部利润贡献' in overview  # business text is not segment attribution
    assert research.reports.read(job['report_id'])['core_sha256']==snapshot['core_sha256']


def test_invalid_sensitivity_is_not_success_and_absent_reverse_does_not_force_blocked(tmp_path):
    import copy
    from test_economic_review import operating_request
    from roll.accounts.ledger import now
    from roll.research.company.report_values import typed_packet
    research=service(tmp_path);command,_=operating_request(research)
    command.config['sensitivity']=dict(scenario='base',wacc=[.01],terminal_g=[.02])
    for path in ['sensitivity/wacc/0','sensitivity/terminal_g/0']:
        command.provenance[path]=dict(command.provenance['wacc'])
        command.economic_basis['assumption_basis']['config/'+path]={**command.economic_basis['assumption_basis']['config/wacc'],'reason':'METHOD alternate diagnostic grid parameter anchored to the same known rate input, not a new observed rate'}
    result=research.calculate_operating_valuation(command)
    raw=research.valuation(result['valuation_id']);assert raw['result']['sensitivity'][0]['status']=='NOT_APPLICABLE'
    job=research.reports.start(ReportCommand(company_id=result['company_id'],snapshot_id=result['snapshot_id'],as_of=now(),source_mode='REUSE',idempotency_key='error-grid'))
    for _ in range(4):job=research.reports.advance(job['job_id'])
    packet=research.reports.input(job['input_id'])
    assert '未形成有效敏感性网格' in packet['payload']['valuation_subsections']['6']
    assert 'WACC_NOT_ABOVE_G' in packet['payload']['valuation_subsections']['6']
    # METHOD renderer contract: a frozen safe current presentation is independent of optional reverse.
    view=copy.deepcopy(packet);view['payload']['valuation_presentation']={**packet['payload']['valuation_binding']['baseline'],'purpose':'CURRENT_PRICING','usable_range':True,'status':'conditional'}
    rendered=typed_packet(view)['payload']['valuation_subsections']['7']
    assert '仍blocked' not in rendered and 'conditional' in rendered
    assert '未请求' in rendered or '未形成' in rendered
    assert research.reports.input(job['input_id'])==packet  # renderer never changes saved qualification


def test_supplied_peer_context_is_presented_in98_without_independent_value_claim(tmp_path):
    from roll.accounts.ledger import now
    research=service(tmp_path);issuer=research.register(company());main=published(research,issuer)
    peer=research.register(company('提供资料的合成同业',['资料同业'],[dict(exchange='HKEX',code='00345',share_class='H',currency='HKD')]))
    other=published(research,peer)
    job=research.reports.start(ReportCommand(company_id=issuer['company_id'],snapshot_id=main['snapshot_id'],as_of=now(),source_mode='REUSE',idempotency_key='context98',peer_snapshot_ids=[other['snapshot_id']],peer_comparison_basis={other['snapshot_id']:'METHOD explicit business context only; financial period, currencies and scope still need independent reconciliation'}))
    for _ in range(4):job=research.reports.advance(job['job_id'])
    packet=research.reports.input(job['input_id']);body=packet['payload']['valuation_subsections']['8']
    assert peer['legal_name'] in body
    assert other['snapshot_id'] in body and '/api/company-research/materials/' in body
    assert '不构成独立估值验证' in body
    assert '未取得已核对同业/资产/历史分位外部对照' not in body


def test_accepted_source_observations_and_price_series_reach_summary_without_rewriting_core(tmp_path,monkeypatch):
    import json
    from roll.accounts.ledger import now
    from roll.research.company import MaterialCommand,FactCommand,AnalysisCommand
    from test_shared_evidence import material_input
    from test_analysis_snapshots import candidate
    research=service(tmp_path/'data');issuer=research.register(company())
    meta=material_input(issuer['company_id']);meta.update(unit=None,currency=None,scope=None,media_type='application/json',period_start='2023-01-01',period_end='2025-12-31')
    original=research.import_material(MaterialCommand(**meta),b'{"METHOD":"disclosed refining business and annual price/earnings observations, not real market evidence"}')
    anchor=research.add_fact(FactCommand(company_id=issuer['company_id'],material_id=original['material_id'],metric='business_structure',business='REFINING',value='METHOD disclosed refining business',value_type='TEXT',unit=None,currency=None,scope='CONSOLIDATED',period_start='2025-01-01',period_end='2025-12-31',table='/METHOD',change_reason='METHOD source anchor'))
    facts=[anchor]
    for metric in ['stock_price','eps']:
        for year in range(2023,2026):
            facts.append(research.add_fact(FactCommand(company_id=issuer['company_id'],material_id=original['material_id'],metric=metric,business='LISTING',value='1',unit='CNY/share',currency='CNY',scope='SSE:600362:A',period_start=f'{year}-01-01',period_end=f'{year}-12-31',table=f'/{metric}/{year}',change_reason='METHOD same annual listing basis; no real return claim')))
    packet=research.freeze_analysis(AnalysisCommand(company_id=issuer['company_id'],as_of=now(),fact_version_ids=[f['version_id'] for f in facts]));snapshot=research.apply_analysis_candidate(packet['input_id'],candidate(packet,anchor))
    worker=tmp_path/'method-summary-worker.py'
    worker.write_text('''import json,sys
c=json.loads(sys.stdin.readline());p=json.loads(c['prompt']);f=next(f for f in p['facts'] if f['metric']=='business_structure');fid=f['version_id']
rows=[('优势','披露业务可作为后续核查的业务锚。'),('风险','业务延续依赖后续原件持续支持。'),('最大证伪点','如后续原件否定业务延续，研究假设失效。'),('股价节奏','已有序列只能支持时序核对，尚未判断调整时长。')]
v=dict(section_id=p['section_id'],input_sha256=p['input_sha256'],paragraphs=[dict(text='#### '+h+'\\n'+t,fact_version_ids=[fid]) for h,t in rows],gaps=['METHOD only; independent verification is absent'])
print(json.dumps(dict(kind='thread',model=c['model'],provider='METHOD',thread_id='method',instruction_sources=[])),flush=True)
print(json.dumps(dict(kind='completed',status='completed',output=json.dumps(v))),flush=True)
''',encoding='utf-8')
    auth=tmp_path/'method-auth.json';auth.write_text(json.dumps(dict(auth_mode='chatgpt',tokens=dict(access_token='METHOD_ONLY'))))
    monkeypatch.setenv('ROLL_CODEX_AUTH_FILE',str(auth));research.reports.worker=worker
    job=research.reports.start(ReportCommand(company_id=issuer['company_id'],snapshot_id=snapshot['snapshot_id'],as_of=now(),source_mode='REUSE',idempotency_key='source-summary'))
    for _ in range(22):
        job=research.reports.advance(job['job_id'])
        if job['report_id']:break
    sections=research.reports.sections(job)
    assert len(sections)==12 and all(s['status']=='COMPLETE' for s in sections),sections
    assert all(s['observations'][0]['output_sha256']==s['output_archive']['sha256'] for s in sections)
    md=research.reports.markdown(job['report_id']);overview=md.split('# 第一部分')[0]
    assert '已有同口径价格与盈利时序' in overview
    assert '披露业务可作为后续核查的业务锚' in overview and '如后续原件否定业务延续' in overview
    assert '/api/company-research/materials/'+original['material_id']+'/original' in overview
    assert '第1节结论摘录' in md.split('# 第一部分')[1].split('## 1.')[0]
    assert research.reports.read(job['report_id'])['core_sha256']==snapshot['core_sha256']
    from roll.runtime.backups import Backups,restore_at_start
    backup=Backups(tmp_path/'data');bundle=backup.export(backup.create()['backup_id'])
    restored=Backups(tmp_path/'restored');restored.stage_restore(bundle);restore_at_start(restored)
    recovered=service(tmp_path/'restored')
    assert recovered.reports.markdown(job['report_id'])==md
