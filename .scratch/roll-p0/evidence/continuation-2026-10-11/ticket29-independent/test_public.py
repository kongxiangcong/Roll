"""Independent literal read-only report checks on fresh byte copies only."""
import hashlib
import json
import shutil
from pathlib import Path
import httpx
from fastapi.testclient import TestClient
from roll.app import create_app
from report_method_app import copy_donor,FREEZE

ROOT=Path('D:/dsh-proj/Roll')
TREE=ROOT/'.scratch/worktrees/ticket29'
OWNER=TREE/'.scratch/roll-p0/evidence/continuation-2026-10-11/ticket29'
MANIFEST=json.loads((OWNER/'runtime-preservation.json').read_bytes())
OUT=ROOT/'.scratch/roll-p0/evidence/continuation-2026-10-11/ticket29-independent'
URL='/api/research/reports/'+FREEZE
def native(path):return Path(chr(92)*2+'?'+chr(92)+str(path.resolve()))

def public(name):return json.loads((OWNER/'public'/(name+'.json')).read_bytes())['result']

def clone(name,target):
    source=TREE/'.scratch/t29-final-api'/name/'data'
    assert not target.exists()
    selected=[r for r in MANIFEST['entries'] if Path(r['source']).is_relative_to(source)]
    assert selected
    for row in selected:
        original=Path(row['source']);relative=original.relative_to(source)
        assert 'notification-private' not in relative.parts and original.name.lower() not in {'auth.json','credentials.json','secrets.json','.env'}
        body=original.read_bytes()
        assert len(body)==row['bytes'] and hashlib.sha256(body).hexdigest()==row['sha256']
        saved=target/relative;native(saved.parent).mkdir(parents=True,exist_ok=True);shutil.copyfile(native(original),native(saved))
        assert native(saved).read_bytes()==body and original.read_bytes()==body
    return target

def offline(directory):
    calls=[]
    def forbidden(request):
        calls.append(str(request.url));raise AssertionError('Independent report query cannot send HTTP')
    app=create_app(directory,runtime_role='API',market_transport=httpx.MockTransport(forbidden),notification_transport=httpx.MockTransport(forbidden))
    return TestClient(app),calls

def record(name,value):
    (OUT/(name+'.json')).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')

def test_four_namespaces_and_all_server_exports_keep_research_authority(tmp_path):
    client,calls=offline(copy_donor(tmp_path/'donor-copy'))
    with client:
        shadow=client.get('/api/research/shadow/'+FREEZE).json()
        report=client.get(URL).json()
        assert set(report['namespaces'])=={'ACTUAL','HISTORICAL','SHADOW','ACCOUNT_CONDITIONAL'}
        assert report['platform']['state']['revision']==2 and report['platform']['state']==shadow
        assert report['actual']['net_assets'] is None and report['actual']['valuation'] is None
        assert report['curves']['HISTORICAL']['points']==report['curves']['ACCOUNT_CONDITIONAL']['points']==[]
        assert not report['curves']['HISTORICAL']['continuous_performance']
        assert report['source_kind']=='RESEARCH' and not report['system_usable']
        assert report['qualification']['capability']=='NOT_GRANTED' and not report['prepare_allowed']
        assert not report['notification_allowed'] and report['research_link']=='/#research='+FREEZE
        assert client.get(URL+'/export').json()==report
        text=client.get(URL+'/export?format=text').text
        assert all(v in text for v in ['ACTUAL','HISTORICAL','SHADOW','ACCOUNT_CONDITIONAL','NOT_COMPARABLE','NOT_GRANTED'])
        assert client.post('/api/actions/evaluate',json={'report_id':FREEZE,'probability':'.99'}).status_code==422
        assert client.post('/api/intents/prepare',json={'decision_id':FREEZE,'expected_evaluation_id':FREEZE,
            'expected_account_version':1,'expected_funding_version':0,'expected_grant_version':0,
            'price_yuan':'10','idempotency_key':'independent-research-refusal'}).status_code in [404,409]
        assert client.post('/api/notifications',json={'source':'RESEARCH','report_id':FREEZE,'action':'BUY'}).status_code==405
        assert client.post('/api/formal/evaluate',json={}).status_code==403
        assert client.get('/api/research/shadow/'+FREEZE).json()==shadow and not calls
        record('four-namespaces-authority',report)

def test_saved_actual_nav_and_late_fee_values_leave_original_shadow_unchanged(tmp_path):
    client,calls=offline(clone('test_saved_actual_nav_uses_hel0',tmp_path/'saved-copy'))
    evidence=public('actual-saved-nav-late-fees')
    old_id=evidence['original_report']['actual']['valuation']['valuation_id']
    pending_id=evidence['pending_fees']['valuation_id'];new_id=evidence['current_valuation']['valuation_id']
    with client:
        shadow=client.get('/api/research/shadow/'+FREEZE).json()
        old=client.get(URL,params={'valuation_id':old_id}).json()
        pending=client.get(URL,params={'valuation_id':pending_id}).json()
        new=client.get(URL,params={'valuation_id':new_id}).json()
        assert old['actual']['net_assets']=='103600.10'
        assert pending['actual']['net_assets'] is None
        assert new['actual']['net_assets']=='103785.10'
        assert old['curves']['ACTUAL']['points'][0]['valuation_id']==old_id
        assert old['comparison']['status']==new['comparison']['status']=='NOT_COMPARABLE'
        assert new['comparison']['return_difference'] is None and not new['comparison']['causal_attribution']
        assert client.get(URL,params={'valuation_id':old_id}).json()==old
        assert client.get('/api/research/shadow/'+FREEZE).json()==shadow and not calls
        record('actual-nav-old-late-fees',{'old':old,'pending':pending,'new':new})

def selectors(report):
    row=report['execution_deviations'][0]
    return {key:row[key] for key in ['decision_id','evaluation_id','intent_id']}

def test_saved_partial_unexecuted_and_outbound_chains_remain_unknown_without_new_actions(tmp_path):
    rows=[]
    for index,(name,profile) in enumerate([('partial-fill-late-report-300-seconds','test_report_projects_real_part0'),
                         ('unexecuted-unlinked','test_unexecuted_reason_and_unl0'),
                         ('outbound-original-and-explicit-station-read','test_report_preserves_actual_20')]):
        evidence=public(name)
        if name.startswith('outbound'):evidence=evidence['original']
        client,calls=offline(clone(profile,tmp_path/('p'+str(index))))
        params=selectors(evidence)
        with client:
            shadow=client.get('/api/research/shadow/'+FREEZE).json()
            report=client.get(URL,params=params).json()
            deviation=report['execution_deviations'][0]
            assert report['execution']['response_seconds'] is None and not report['comparison']['causal_attribution']
            assert deviation['same_strategy'] is False and deviation['causal_pnl'] is None
            if name.startswith('partial'):
                assert deviation['proposal']['quantity']=='200' and deviation['remaining_quantity']=='100'
                assert deviation['allocations'][0]['allocated_quantity']=='100'
                assert deviation['allocation_diagnostics'][0]['reported_after_occurrence']['seconds']==300
                assert deviation['allocation_diagnostics'][0]['fee_comparison']=='PARTIAL_FILL_NOT_FULL_PROPOSAL'
            elif name.startswith('unexecuted'):
                assert deviation['allocations']==[] and deviation['unexecuted_reason']=='METHOD user chose not to place this order'
                assert report['execution']['unlinked_fills'][0]['record_id']=='self-directed-after-research'
                assert report['execution']['unlinked_association']=='UNKNOWN'
            else:
                chain=report['execution']['notification_chain']
                assert any(n['external_status']=='CHANNEL_ACCEPTED' for n in chain['notification_timeline'])
                assert chain['time_chain']['delivered_at'] is None
                assert chain['original_intent_mutated'] is False
            assert client.get(URL+'/export',params=params).json()==report
            assert client.get('/api/research/shadow/'+FREEZE).json()==shadow and not calls
            rows.append(report)
    record('execution-saved-three-cases',rows)

def test_saved_monitoring_misfit_and_insufficient_evidence_are_read_only(tmp_path):
    reports=[]
    for missing,reason in [(0,'PRICE_OUTSIDE_FROZEN_WINDOW'),(5,'REQUIRED_FEATURE_COVERAGE_BELOW80_PERCENT')]:
        evidence=public('monitoring-missing-'+str(missing));check_id=evidence['monitoring']['checks'][0]['check_id']
        client,calls=offline(clone('test_report_reads_registered_e'+str(missing//5),tmp_path/('monitor-'+str(missing))))
        with client:
            before={path:client.get(path).json() for path in ['/api/capabilities/monitoring','/api/capabilities/grants','/api/capabilities/events']}
            report=client.get(URL,params={'monitoring_check_id':check_id}).json()
            check=report['monitoring']['checks'][0]
            assert check['status']=='RESTRICTED' and reason in check['reasons']
            assert check['reference']['bounds']['x']==[.99,98.01]
            assert check['confirmation_pass_look'] is False and check['historic_verdict_mutated'] is False
            assert report['monitoring']['recomputed'] is False and report['monitoring']['qualification_issued'] is False
            assert report['monitoring']['same_strategy'] is False
            assert reason in client.get(URL+'/export',params={'monitoring_check_id':check_id,'format':'text'}).text
            assert {path:client.get(path).json() for path in before}==before and not calls
            reports.append(report)
    record('monitoring-saved-readonly',reports)

def test_existing_run02_audit_locates_two_shadow_and_one_conditional_record(tmp_path):
    client,calls=offline(clone('test_run_audit_counts_existing0',tmp_path/'audit'))
    with client:
        tasks=client.get('/api/reviews/history').json()
        task=next(t for t in tasks if t.get('audit_id'))
        response=client.get('/api/reviews/audits/'+task['audit_id'])
        assert response.status_code==200,response.text
        metric=response.json()['metrics']['shadow_records']
        assert metric['status']=='CHECKED' and metric['value']==2 and metric['account_conditional_records']==1
        assert [r['revision'] for r in metric['records']]==[1,2]
        assert all(r['freeze_id']==FREEZE and r['namespace']=='SHADOW' and r['input_archive']['sha256'] for r in metric['records'])
        assert not calls
        record('run02-saved-typed-metric',metric)

def test_merged_report_and_saved_action_routes_share_readonly_api(tmp_path):
    client,calls=offline(copy_donor(tmp_path/'data'))
    with client:
        paths=client.get('/openapi.json').json()['paths']
        assert 'get' in paths['/api/research/reports/{freeze_id}']
        assert 'get' in paths['/api/research/collections/{plan_id}/sse-action-assessments/current']
        assert 'post' in paths['/api/research/collections/{plan_id}/sse-action-packets']
        report=client.get(URL).json()
        assert report['source_kind']=='RESEARCH' and not report['system_usable']
        assert report['platform']['state']['revision']==2
        source=client.get('/api/research/collections/nonexistent/sse-action-assessments/current')
        assert source.status_code==404 and not calls
        record('root-composition',{'source_status':source.status_code,'report_source_kind':report['source_kind'],'revision':2,'network_calls':0,'routes':sorted(p for p in paths if 'sse-action' in p or '/reports/' in p)})
