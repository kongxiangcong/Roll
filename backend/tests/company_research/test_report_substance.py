"""Meaningful numeric coverage: unknowns never manufacture series or peers."""
import json
import pytest
from test_shared_evidence import service,company,material_input
from roll.research.company import MaterialCommand,FactCommand

METRICS=['industry_production','industry_consumption','industry_imports','industry_exports','industry_inventory','industry_price']


def series(research,issuer,mode='valid'):
    meta=material_input(issuer['company_id']);meta.update(media_type='application/json',unit=None,currency=None,scope=None,period_start='2019-01-01',period_end='2025-12-31')
    material=research.import_material(MaterialCommand(**meta),json.dumps({'METHOD':'industry numeric source fixture','years':list(range(2020,2025))}).encode())
    facts=[]
    for metric in METRICS:
        for i,year in enumerate(range(2020,2025)):
            value=None if mode=='null' else '未披露' if mode=='text' else '0'
            scope=None if mode=='unknown_scope' else 'UNKNOWN' if mode=='unknown_scope_label' else 'REGION_A' if mode=='mixed_scope' and i<3 else 'REGION_B' if mode=='mixed_scope' else 'REGION_CN_METAL'
            facts.append(research.add_fact(FactCommand(company_id=issuer['company_id'],material_id=material['material_id'],metric=metric,business='METHOD_INDUSTRY',value=value,value_type='TEXT' if mode=='text' else 'NUMBER',unit='UNKNOWN' if mode=='unknown_unit_label' else 'ton' if metric!='industry_price' else 'CNY/ton',currency=None if metric!='industry_price' else 'CNY',scope=scope,period_start=f'{year}-01-01',period_end=f'{year}-12-31',table=f'/{metric}/{year}',change_reason='METHOD source with literal zero or explicit unknown; no real industry claim')))
    return facts,[material]


@pytest.mark.parametrize('mode',['null','text','unknown_scope','mixed_scope','unknown_scope_label','unknown_unit_label'])
def test_unknown_or_incompatible_industry_data_cannot_count_five_years(tmp_path,mode):
    from roll.research.company.report_data import prepare_data
    research=service(tmp_path);issuer=research.register(company());facts,materials=series(research,issuer,mode)
    result=prepare_data(research.evidence,facts,materials)
    assert result['coverage']['industry_complete'] is False
    assert all(n<5 for n in result['coverage']['industry_years'].values())
    if mode in {'null','text','unknown_scope','unknown_scope_label','unknown_unit_label'}:assert result['charts']==[]


def test_known_physical_units_and_literal_zero_form_real_comparable_series(tmp_path):
    from roll.research.company.report_data import prepare_data
    research=service(tmp_path);issuer=research.register(company());facts,materials=series(research,issuer)
    result=prepare_data(research.evidence,facts,materials)
    assert result['coverage']['industry_complete'] is True
    assert set(result['coverage']['industry_years'].values())=={5}
    assert len(result['charts'])==6 and all(len(c['data'])==5 for c in result['charts'])
    assert all('未知' not in c['title'] and all(row['value']=='0' for row in c['data']) for c in result['charts'])


@pytest.mark.parametrize('missing',[False,True])
def test_peer_count_needs_real_numeric_pair_and_distinct_companies(tmp_path,missing):
    from roll.accounts.ledger import now
    from roll.research.company import AnalysisCommand
    from roll.research.company.reports import ReportCommand
    from test_analysis_snapshots import candidate
    from test_daily_research import published
    research=service(tmp_path);issuer=research.register(company());main=published(research,issuer)
    peer=research.register(company('合成国际同业',['合成同业'],[dict(exchange='HKEX',code='00345',share_class='H',currency='HKD')]))
    meta=material_input(peer['company_id']);meta.update(subject_name=peer['legal_name'],unit=None,currency=None,media_type='application/json')
    material=research.import_material(MaterialCommand(**meta),b'{"METHOD":"peer context","revenue":null,"gross_margin":null}')
    facts=[]
    for metric,value,unit,currency in [('revenue',None if missing else '100','HKD_MILLION','HKD'),('gross_margin',None if missing else '0','ratio',None)]:
        facts.append(research.add_fact(FactCommand(company_id=peer['company_id'],material_id=material['material_id'],metric=metric,business='BEVERAGE',value=value,unit=unit,currency=currency,scope='CONSOLIDATED',period_start='2025-01-01',period_end='2025-12-31',table='/'+metric,change_reason='METHOD nullable or zero-valued peer financial fact')))
    # A real text anchor supports publishing an engineering snapshot even if financial cells are unknown.
    anchor=research.add_fact(FactCommand(company_id=peer['company_id'],material_id=material['material_id'],metric='business_structure',business='BEVERAGE',value='METHOD disclosed beverage business',value_type='TEXT',unit=None,currency=None,scope='CONSOLIDATED',period_start='2025-01-01',period_end='2025-12-31',table='/METHOD',change_reason='METHOD business anchor'))
    packet=research.freeze_analysis(AnalysisCommand(company_id=peer['company_id'],as_of=now(),fact_version_ids=[f['version_id'] for f in [anchor,*facts]]));snap=research.apply_analysis_candidate(packet['input_id'],candidate(packet,anchor))
    second=research.freeze_analysis(AnalysisCommand(company_id=peer['company_id'],as_of=now(),fact_version_ids=snap['fact_version_ids'],parent_snapshot_id=snap['snapshot_id']))
    proposed=candidate(second,anchor);proposed['hypotheses'][0]['previous_version_id']=snap['hypothesis_version_ids'][0]
    newer=research.apply_analysis_candidate(second['input_id'],proposed)
    job=research.reports.start(ReportCommand(company_id=issuer['company_id'],snapshot_id=main['snapshot_id'],as_of=now(),source_mode='REUSE',idempotency_key='peer-substance',peer_snapshot_ids=[snap['snapshot_id'],newer['snapshot_id']]))
    for _ in range(4):job=research.reports.advance(job['job_id'])
    data=research.reports.input(job['input_id'])['payload']
    assert data['coverage']['peer_count']==(0 if missing else 1)
    assert data['coverage']['international_peer_count']==(0 if missing else 1)
    assert data['coverage']['peer_complete'] is False
    assert len(data['peers'])==2  # explicit history is retained; qualification counts companies


def test_five_distinct_numeric_peers_with_two_international_can_complete_coverage(tmp_path):
    from roll.accounts.ledger import now
    from roll.research.company import AnalysisCommand
    from roll.research.company.reports import ReportCommand
    from test_analysis_snapshots import candidate
    from test_daily_research import published
    research=service(tmp_path);issuer=research.register(company());main=published(research,issuer);snapshots=[]
    for index in range(5):
        international=index<2;currency='HKD' if international else 'CNY'
        peer=research.register(company('合成可比公司'+str(index),['合成同行'+str(index)],[dict(exchange='HKEX' if international else 'SZSE',code=f'{345+index:05d}' if international else f'{848+index:06d}',share_class='H' if international else 'A',currency=currency)]))
        meta=material_input(peer['company_id']);meta.update(subject_name=peer['legal_name'],unit=None,currency=None,media_type='application/json')
        material=research.import_material(MaterialCommand(**meta),b'{"METHOD":"disclosed beverage business","revenue":100,"gross_margin":0}')
        facts=[]
        for metric,value,unit,ccy in [('revenue','100',currency+'_MILLION',currency),('gross_margin','0','ratio',None),('business_structure','METHOD disclosed beverage business',None,None)]:
            facts.append(research.add_fact(FactCommand(company_id=peer['company_id'],material_id=material['material_id'],metric=metric,business='BEVERAGE',value=value,value_type='TEXT' if metric=='business_structure' else 'NUMBER',unit=unit,currency=ccy,scope='CONSOLIDATED',period_start='2025-01-01',period_end='2025-12-31',table='/'+metric,change_reason='METHOD numeric peer coverage, not a real company comparison')))
        frozen=research.freeze_analysis(AnalysisCommand(company_id=peer['company_id'],as_of=now(),fact_version_ids=[f['version_id'] for f in facts]));snapshots.append(research.apply_analysis_candidate(frozen['input_id'],candidate(frozen,facts[-1])))
    job=research.reports.start(ReportCommand(company_id=issuer['company_id'],snapshot_id=main['snapshot_id'],as_of=now(),source_mode='REUSE',idempotency_key='five-peers',peer_snapshot_ids=[s['snapshot_id'] for s in snapshots],peer_comparison_basis={s['snapshot_id']:'METHOD same product, annual period and consolidated revenue/margin; original currencies retained, no value multiple inference' for s in snapshots}))
    for _ in range(4):job=research.reports.advance(job['job_id'])
    data=research.reports.input(job['input_id'])['payload']
    assert data['coverage']['peer_count']==5 and data['coverage']['international_peer_count']==2
    assert data['coverage']['peer_complete'] is True
