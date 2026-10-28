"""METHOD: new report builds a valuation; no pre-existing valuation/review is supplied."""
import copy
import json
import pytest
from test_shared_evidence import service
from test_economic_review import operating_request


def test_report_builds_and_pins_operating_valuation_from_frozen_facts(tmp_path, monkeypatch):
    from roll.research.company.reports import ReportCommand
    research = service(tmp_path / 'data')
    candidate, parent = operating_request(research)
    assert parent['valuation_ids'] == [] and not parent.get('economic_review_ids')
    # Candidate model output is a METHOD fixture, not a pre-published model/result.
    payload = candidate.model_dump(exclude={'snapshot_id', 'idempotency_key', 'parent_version_id'})
    payload['config']['metadata']['as_of'] = parent['as_of']
    payload['economic_basis']['wacc']['as_of'] = parent['as_of'][:10]
    payload['economic_basis']['limitations'] = []  # Host must still retain its conditional limit.
    stress = copy.deepcopy(payload['drivers']['scenarios'][0])
    stress['name'] = 'stress'
    for year in stress['years']:
        year['operating_margin'] = .18
    payload['economic_basis']['terminal']['roic'] = dict(base=.3, stress=.27)
    payload['drivers']['scenarios'].append(stress)
    for key, value in list(payload['drivers']['provenance'].items()):
        if key.startswith('scenarios/0/'):
            payload['drivers']['provenance'][key.replace('scenarios/0/', 'scenarios/1/')] = value
            audit = payload['economic_basis']['assumption_basis'].get('drivers/' + key)
            if audit:
                payload['economic_basis']['assumption_basis']['drivers/' + key.replace('scenarios/0/', 'scenarios/1/')] = audit
    origin = payload['drivers']['provenance'].pop('basis/terminal/roic')
    audit = payload['economic_basis']['assumption_basis'].pop('drivers/basis/terminal/roic')
    for name in ['base', 'stress']:
        payload['drivers']['provenance']['basis/terminal/roic/' + name] = origin
        payload['economic_basis']['assumption_basis']['drivers/basis/terminal/roic/' + name] = audit
    wire = tmp_path / 'candidate.json'
    wire.write_text(json.dumps(payload), encoding='utf-8')
    worker = tmp_path / 'method-valuation.py'
    worker.write_text('''import json,sys
c=json.loads(sys.stdin.readline());p=json.loads(c['prompt'])
assert c['tools']==[]
print(json.dumps({'kind':'thread','model':c['model'],'provider':'METHOD','thread_id':'method','instruction_sources':[]}),flush=True)
if 'valuation_contract' in p:
    value=json.load(open(%r,encoding='utf-8'))
    value['config']['metadata']['as_of']=p['snapshot']['as_of']
    value['economic_basis']['wacc']['as_of']=p['snapshot']['as_of'][:10]
    for a in value['assumptions']: a['hypothesis_version_ids']=p['snapshot']['hypothesis_version_ids']
    output=dict(snapshot_id=p['snapshot']['snapshot_id'],input_sha256=p['input_sha256'],command_json=json.dumps(value),gaps=[])
elif 'section_id' in p:
    output=dict(section_id=p['section_id'],input_sha256=p['input_sha256'],paragraphs=[],gaps=['METHOD no prose'])
else:
    claim=dict(text='Sourced business evidence remains subject to financial assumptions',fact_version_ids=[p['evidence']['facts'][0]['version_id']],gap_reason=None)
    output=dict(company_id=p['company_id'],input_sha256=p['packet_sha256'],business_structure=[claim],attention_reasons=[claim],counterevidence=[],hypotheses=[],insufficient_hypotheses_reason='METHOD bounded evidence',limitations=['METHOD only'],valuation_unavailable_reason='Pending controlled valuation phase')
print(json.dumps({'kind':'completed','status':'completed','output':json.dumps(output)}),flush=True)
''' % str(wire), encoding='utf-8')
    auth = tmp_path / 'method-auth.json'
    auth.write_text(json.dumps(dict(auth_mode='chatgpt',tokens={'access_token':'METHOD_NOT_A_CREDENTIAL'})))
    monkeypatch.setenv('ROLL_CODEX_AUTH_FILE', str(auth))
    research.reports.worker = worker
    job = research.reports.start(ReportCommand(company_id=parent['company_id'],snapshot_id=parent['snapshot_id'],
        as_of=parent['as_of'],source_mode='REUSE',valuation_purpose='BASELINE_RESEARCH',idempotency_key='new-report'))
    for _ in range(25):
        job = research.reports.advance(job['job_id'])
        if job['report_id']: break
    assert job['snapshot_id'] != parent['snapshot_id'], job
    child = research.analysis_snapshot(job['snapshot_id'])
    assert child['parent_snapshot_id'] == parent['snapshot_id']
    assert child['economic_review_ids'] and child['valuation_ids']
    report = research.reports.read(job['report_id'])
    daily = research.daily_view(parent['company_id'],child['snapshot_id'])
    packet = research.reports.input(report['input_id'])['payload']
    assert report['core'] == daily['snapshot']['core'] == child['core']
    assert packet['valuation_binding']['baseline']['scenarios'][0]['per_share'] == pytest.approx(13)
    assert packet['valuation_presentation']['status'] == daily['valuation']['status'] == 'blocked'
    assert packet['valuation_binding']['valuation_ids'] == child['valuation_ids']
    assert daily['valuation']['diagnostic_valuation_id'] == child['valuation_ids'][0]
    assert research.valuation(daily['valuation']['diagnostic_valuation_id'])['result']['scenarios'][0]['per_share'] == pytest.approx(13)
    assert research.reports.valuation_preview(job['job_id'])['snapshot_id'] == parent['snapshot_id']
    assert research.analysis_snapshot(parent['snapshot_id']) == parent
    assert research.economic_review(child['economic_review_ids'][0])['status'] == 'conditional'

    # A new archived source triggers real shared analysis, then a new valuation;
    # neither the preceding report nor its shared core is overwritten.
    from roll.research.company import MaterialCommand, FactCommand
    from test_shared_evidence import material_input
    metadata = material_input(parent['company_id'])
    metadata.update(source_id='METHOD-new-disclosure')
    material = research.import_material(MaterialCommand(**metadata), b'METHOD new audited business disclosure; scope unchanged')
    fact = research.add_fact(FactCommand(company_id=parent['company_id'], material_id=material['material_id'],
        metric='business_scope_update', business='BUSINESS_SCOPE', value='Manufacturing only; no scope change', value_type='TEXT',
        unit=metadata['unit'], currency=metadata['currency'], scope='CONSOLIDATED', period_start='2025-01-01',
        period_end='2025-12-31', change_reason='New source evidence'))
    research.analysis_worker = worker
    research.reports.collectors = []
    from roll.accounts.ledger import now
    refreshed = research.reports.start(ReportCommand(company_id=parent['company_id'], as_of=now(),
        source_mode='REFRESH', valuation_purpose='BASELINE_RESEARCH', idempotency_key='refresh'))
    for _ in range(25):
        refreshed = research.reports.advance(refreshed['job_id'])
        if refreshed['report_id']: break
    new = research.analysis_snapshot(refreshed['snapshot_id'])
    source = research.analysis_snapshot(new['parent_snapshot_id'])
    assert source['parent_snapshot_id'] == child['snapshot_id']
    assert fact['version_id'] in new['fact_version_ids']
    assert new['valuation_ids'] != child['valuation_ids'] and source['valuation_ids'] == []
    assert research.reports.read(job['report_id']) == report
    assert research.analysis_snapshot(child['snapshot_id']) == child
    assert research.daily_view(parent['company_id'])['snapshot'] == new
    assert research.reports.read(refreshed['report_id'])['core'] == new['core']

    from roll.runtime.backups import Backups, restore_at_start
    backups = Backups(tmp_path / 'data')
    bundle = backups.export(backups.create()['backup_id'])
    restored = Backups(tmp_path / 'restored')
    restored.stage_restore(bundle)
    restore_at_start(restored)
    recovered = service(tmp_path / 'restored')
    assert recovered.reports.read(job['report_id']) == report
    assert recovered.reports.read(refreshed['report_id']) == research.reports.read(refreshed['report_id'])
    assert recovered.analysis_snapshot(new['snapshot_id']) == new


@pytest.mark.parametrize('mode,expected', [('wrong-binding','INPUT_CHANGED'),
    ('foreign-source','ASSUMPTION_INVALID'), ('missing-capex','PROVENANCE_REQUIRED'),
    ('unavailable','Missing sourced investment/capital/discount assumptions')])
def test_report_keeps_unusable_valuation_explicit_and_preserves_source(tmp_path, monkeypatch, mode, expected):
    from roll.research.company.reports import ReportCommand
    research = service(tmp_path / 'data')
    candidate, source = operating_request(research)
    payload = candidate.model_dump(exclude={'snapshot_id', 'idempotency_key', 'parent_version_id'})
    payload['config']['metadata']['as_of'] = source['as_of']
    payload['economic_basis']['wacc']['as_of'] = source['as_of'][:10]
    payload['drivers']['scenarios'].append(dict(payload['drivers']['scenarios'][0], name='stress'))
    for path, value in list(payload['drivers']['provenance'].items()):
        if path.startswith('scenarios/0/'):
            payload['drivers']['provenance'][path.replace('scenarios/0/', 'scenarios/1/')] = value
    if mode == 'foreign-source':
        payload['assumptions'][0]['anchor_fact_version_ids'] = ['other-company-fact']
    if mode == 'missing-capex':
        payload['drivers']['scenarios'][0]['years'][0].pop('maintenance_capex')
    fixture = tmp_path / 'response.json'
    fixture.write_text(json.dumps(dict(snapshot_id='other-snapshot' if mode == 'wrong-binding' else source['snapshot_id'],
        input_sha256=source['content_sha256'], command_json=None if mode == 'unavailable' else json.dumps(payload),
        gaps=['Missing sourced investment/capital/discount assumptions'] if mode == 'unavailable' else [])), encoding='utf-8')
    worker = tmp_path / 'negative-worker.py'
    worker.write_text('''import json,sys
c=json.loads(sys.stdin.readline())
print(json.dumps(dict(kind='thread',model=c['model'],provider='METHOD',thread_id='method',instruction_sources=[])),flush=True)
print(json.dumps(dict(kind='completed',status='completed',output=open(%r,encoding='utf-8').read())),flush=True)
''' % str(fixture), encoding='utf-8')
    auth = tmp_path / 'method-auth.json'
    auth.write_text(json.dumps(dict(auth_mode='chatgpt', tokens=dict(access_token='METHOD_ONLY'))))
    monkeypatch.setenv('ROLL_CODEX_AUTH_FILE', str(auth))
    research.reports.worker = worker
    job = research.reports.start(ReportCommand(company_id=source['company_id'], snapshot_id=source['snapshot_id'],
        as_of=source['as_of'], source_mode='REUSE', idempotency_key=mode))
    preview = research.reports.valuation_preview(job['job_id'])
    assert preview['model_calls'] == preview['network_calls'] == 0
    assert json.loads(preview['command']['prompt'])['valuation_purpose'] == 'CURRENT_PRICING'
    for _ in range(4):
        job = research.reports.advance(job['job_id'])
    result = job['valuation_build']
    assert result['status'] in {'FAILED', 'BLOCKED'} and expected in result['gaps']
    assert job['snapshot_id'] == source['snapshot_id']
    assert research.analysis_snapshot(source['snapshot_id']) == source
    packet = research.reports.input(job['input_id'])
    assert packet['payload']['valuation_presentation']['scenarios'] == []
    assert packet['payload']['valuation_purpose'] == 'CURRENT_PRICING'
    assert expected in packet['payload']['source_gaps']
