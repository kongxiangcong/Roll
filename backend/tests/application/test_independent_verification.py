import hashlib
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from roll.app import create_app
from test_source_resolution import setup_request, quote_bytes, tencent_bytes, completed


def acquire(client, source='TENCENT'):
    request=client.post('/api/data/requests',json={'instruments':['SSE:600519'],'groups':['QUOTE'],
        'purpose':'OBSERVATION','start_date':'2026-09-30','end_date':'2026-09-30','quote_source':source}).json()
    run=client.post('/api/data/requests/'+request['request_id']+'/retrieve').json()
    return {'snapshot_id':run['snapshot_id'],'fact_index':0}


def command(refs, trigger='USER_SELECTED'):
    return {'trigger':trigger,'reason':'收盘价格影响重大盈亏归因，核对决定性价格',
        'facts':[{'fact_id':'decisive-close','field':'last','references':refs}]}


def test_routine_is_not_upgraded_and_two_supplier_quotes_do_not_prove_independence(tmp_path):
    def provider(r):
        return httpx.Response(200,content=quote_bytes() if r.url.host=='hq.sinajs.cn' else tencent_bytes())
    with TestClient(create_app(tmp_path,market_transport=httpx.MockTransport(provider))) as client:
        setup_request(client)
        before=client.get('/api/account').json()
        refs=[acquire(client),acquire(client,'SINA')]
        assert client.post('/api/data/verifications',json=command(refs,'ROUTINE')).status_code==422
        response=client.post('/api/data/verifications',json=command(refs))
        assert response.status_code==201,response.text
        value=response.json()
        assert value['result']=='INSUFFICIENT' and value['formal_judgment']=='DISABLED'
        fact=value['facts'][0]
        assert fact['result']=='INSUFFICIENT' and fact['attribution_status']=='DEFERRED'
        assert fact['independent_basis_count']==0 and 'INDEPENDENCE_UNPROVEN' in fact['gaps']
        assert [v['value'] for v in fact['evidence']]==['1258.62','1258.620']
        assert client.get('/api/data/verifications/'+value['verification_id']).json()==value
        assert client.get('/api/account').json()==before


def original_quote(origin, price='100.000', **context):
    return json.dumps({'instrument':'SSE:600519','method_case_status':'NORMAL',
        'upstream_at':'2026-09-30T15:00:00+08:00','basis':'METHOD_CASE synthetic separate original observation',
        'last':price,'_roll14_original_provenance':{'original_record':origin,
            'producer':origin.split(':')[0],'generation_basis':'METHOD_CASE independently generated source record',
            'origin_kind':'DIRECT_ORIGINAL'},**context}).encode()


def test_same_original_repeated_by_domains_counts_once_and_independent_equal_originals_verify(tmp_path):
    raw=[original_quote('A:first')]
    with TestClient(create_app(tmp_path,market_transport=httpx.MockTransport(lambda r:httpx.Response(200,content=raw[0])))) as client:
        setup_request(client)
        first=acquire(client)
        second=acquire(client)
        same=client.post('/api/data/verifications',json=command([first,second])).json()
        assert same['facts'][0]['independent_basis_count']==1
        assert same['result']=='INSUFFICIENT' and 'SAME_ORIGINAL_BASIS' in same['facts'][0]['gaps']
        raw[0]=original_quote('B:second','100.0')
        independent=acquire(client)
        verified=client.post('/api/data/verifications',json=command([first,independent])).json()
        assert verified['result']=='VERIFIED' and verified['evidence_kind']=='METHOD_CASE'
        fact=verified['facts'][0]
        assert fact['independent_basis_count']==2 and fact['attribution_status']=='READY'
        assert fact['comparisons'][0]['values']=='EQUAL_DECIMAL'
        assert fact['comparisons'][0]['comparable'] is True
        assert len(fact['evidence'])==2 and not fact['gaps']
        assert verified['formal_judgment']=='DISABLED'


def test_conflicting_values_defer_only_related_attribution_and_time_mismatch_is_insufficiency(tmp_path):
    raw=[original_quote('A:first')]
    with TestClient(create_app(tmp_path,market_transport=httpx.MockTransport(lambda r:httpx.Response(200,content=raw[0])))) as client:
        setup_request(client)
        first=acquire(client)
        raw[0]=original_quote('B:second','101')
        other=acquire(client)
        payload=command([first,other],'CRITICAL_CONFLICT')
        payload['facts'].append({'fact_id':'known-session','field':'trade_date','references':[first,other]})
        result=client.post('/api/data/verifications',json=payload).json()
        assert result['result']=='CONFLICT'
        assert result['facts'][0]['attribution_status']=='DEFERRED'
        assert result['facts'][1]['result']=='VERIFIED' and result['facts'][1]['attribution_status']=='READY'
        assert [v['value'] for v in result['facts'][0]['evidence']]==['100.000','101']
        raw[0]=original_quote('C:third','101',upstream_at='2026-09-30T14:59:00+08:00')
        different_time=acquire(client)
        time_result=client.post('/api/data/verifications',json=command([first,different_time])).json()
        assert time_result['result']=='INSUFFICIENT'
        assert 'UPSTREAM_AT_NOT_COMPARABLE' in time_result['facts'][0]['gaps']
        assert time_result['facts'][0]['comparisons'][0]['values']=='DIFFERENT'
        assert time_result['facts'][0]['comparisons'][0]['comparable'] is False


@pytest.mark.parametrize('replacement',['101','100.000'])
def test_same_versions_reuse_but_source_revision_invalidates_current_result_and_replay_keeps_old_values(tmp_path,replacement):
    raw=[original_quote('A:first')]
    with TestClient(create_app(tmp_path,market_transport=httpx.MockTransport(lambda r:httpx.Response(200,content=raw[0])))) as client:
        req=setup_request(client)
        first_run=client.post('/api/data/requests/'+req['request_id']+'/retrieve').json()
        first={'snapshot_id':first_run['snapshot_id'],'fact_index':0}
        resolution=completed(client,client.post('/api/data/requests/'+req['request_id']+'/resolve',
            json={'usage':'HISTORICAL_RESEARCH','allow_fallback':False,'basis_run_id':first_run['run_id']}).json()['resolution_id'])
        raw[0]=original_quote('B:second','100')
        other=acquire(client)
        payload=command([first,other])
        original=client.post('/api/data/verifications',json=payload).json()
        reused=client.post('/api/data/verifications',json=payload).json()
        assert reused['reuse_of']==original['verification_id'] and reused['network_calls']==0
        raw[0]=original_quote('A:first-revised',replacement)
        revised=completed(client,client.post('/api/data/requests/'+req['request_id']+'/resolve',
            json={'usage':'HISTORICAL_RESEARCH','allow_fallback':False,'use_cache':False,
                'revision_of':resolution['resolution_id']}).json()['resolution_id'])
        stale=client.get('/api/data/verifications/'+original['verification_id']).json()
        assert stale['dependency_status']=='INVALIDATED' and stale['current_result']=='INSUFFICIENT'
        assert stale['result']=='VERIFIED' and stale['facts'][0]['evidence'][0]['value']=='100.000'
        replay=client.post('/api/data/verifications/'+original['verification_id']+'/replay').json()
        assert replay['network_calls']==0 and replay['original_result']=='VERIFIED'
        assert replay['facts']==original['facts'] and replay['current_dependency_status']=='INVALIDATED'
        new_run=client.get('/api/data/runs/'+revised['attempts'][0]['run_id']).json()
        new_ref={'snapshot_id':new_run['snapshot_id'],'fact_index':0}
        changed=client.post('/api/data/verifications',json=command([new_ref,other])).json()
        assert changed['reuse_of'] is None and changed['result']==('CONFLICT' if replacement=='101' else 'VERIFIED')
        assert client.get('/api/data/verifications/'+reused['verification_id']).json()['dependency_status']=='INVALIDATED'
        recreated=client.post('/api/data/verifications',json=payload).json()
        assert recreated['dependency_status']=='INVALIDATED' and recreated['current_result']=='INSUFFICIENT'
        assert recreated['reuse_of'] is None


def test_later_acquired_evidence_cannot_be_rewritten_as_known_at_old_review_cutoff(tmp_path):
    raw=[original_quote('A:first')]
    with TestClient(create_app(tmp_path,market_transport=httpx.MockTransport(lambda r:httpx.Response(200,content=raw[0])))) as client:
        setup_request(client)
        a=acquire(client)
        raw[0]=original_quote('B:second')
        b=acquire(client)
        payload=command([a,b]);payload['knowledge_cutoff']='2026-09-30T16:00:00+08:00'
        response=client.post('/api/data/verifications',json=payload)
        assert response.status_code==201,response.text
        value=response.json()
        assert value['result']=='INSUFFICIENT'
        assert 'ACQUIRED_AFTER_REVIEW_KNOWLEDGE_CUTOFF' in value['facts'][0]['gaps']
        assert all(not e['known_at_review_cutoff'] for e in value['facts'][0]['evidence'])
        assert value['facts'][0]['evidence'][0]['available_at'].startswith('2026-10-')
        assert client.post('/api/data/verifications',json={**command([a,b]),'origin_id':'pretend-independent'}).status_code==422


def test_equal_reported_volume_with_unknown_unit_is_not_verified(tmp_path):
    raw=[original_quote('A:first',volume_reported='100')]
    with TestClient(create_app(tmp_path,market_transport=httpx.MockTransport(lambda r:httpx.Response(200,content=raw[0])))) as client:
        setup_request(client);a=acquire(client)
        raw[0]=original_quote('B:second',volume_reported='100');b=acquire(client)
        payload=command([a,b]);payload['facts'][0]['field']='volume_reported'
        result=client.post('/api/data/verifications',json=payload).json()
        assert result['result']=='INSUFFICIENT'
        assert 'UNIT_NOT_ESTABLISHED' in result['facts'][0]['gaps']
        assert all(e['field_unit']=='UNKNOWN' for e in result['facts'][0]['evidence'])


def test_extra_same_origin_and_equivalent_timezone_do_not_create_votes_or_false_conflict(tmp_path):
    raw=[original_quote('A:first')]
    with TestClient(create_app(tmp_path,market_transport=httpx.MockTransport(lambda r:httpx.Response(200,content=raw[0])))) as client:
        setup_request(client);a=acquire(client);duplicate=acquire(client)
        raw[0]=original_quote('B:second',upstream_at='2026-09-30T07:00:00+00:00');b=acquire(client)
        payload=command([a,duplicate,b]);payload['facts'][0]['field']='upstream_at'
        value=client.post('/api/data/verifications',json=payload).json()
        assert value['result']=='VERIFIED'
        assert value['facts'][0]['independent_basis_count']==2
        assert 'SAME_ORIGINAL_BASIS' in value['facts'][0]['limitations']
        assert all(c['values']=='EQUAL_INSTANT' for c in value['facts'][0]['comparisons'])


def test_corrupt_archive_prevents_reuse_but_unrelated_decisive_fact_can_continue(tmp_path):
    raw=[original_quote('A:first')]
    with TestClient(create_app(tmp_path,market_transport=httpx.MockTransport(lambda r:httpx.Response(200,content=raw[0])))) as client:
        setup_request(client);a=acquire(client)
        raw[0]=original_quote('B:second');b=acquire(client)
        value=client.post('/api/data/verifications',json=command([a,b])).json()
        sha=value['facts'][0]['evidence'][0]['raw_hash']
        (tmp_path/'raw'/(sha+'.raw')).write_bytes(b'METHOD_CASE explicit corrupt storage boundary')
        assert client.get('/api/data/verifications/'+value['verification_id']).status_code==409
        assert client.post('/api/data/verifications/'+value['verification_id']+'/replay').status_code==409
        history=client.get('/api/data/verifications')
        assert history.status_code==200,history.text
        assert history.json()[0]['dependency_status']=='UNREADABLE'
        assert history.json()[0]['current_result']=='INSUFFICIENT'
        raw[0]=original_quote('C:unrelated','300');c=acquire(client)
        raw[0]=original_quote('D:unrelated','300');d=acquire(client)
        other=client.post('/api/data/verifications',json=command([c,d]))
        assert other.status_code==201,other.text
        assert other.json()['result']=='VERIFIED' and other.json()['reuse_of'] is None


def test_registered_amount_field_retains_yuan_unit(tmp_path):
    raw=[original_quote('A:first',amount_yuan='123.450')]
    with TestClient(create_app(tmp_path,market_transport=httpx.MockTransport(lambda r:httpx.Response(200,content=raw[0])))) as client:
        setup_request(client);a=acquire(client)
        raw[0]=original_quote('B:second',amount_yuan='123.45');b=acquire(client)
        payload=command([a,b]);payload['facts'][0]['field']='amount_yuan'
        value=client.post('/api/data/verifications',json=payload).json()
        assert all(e['field_unit']=='CNY' for e in value['facts'][0]['evidence'])
        assert value['result']=='VERIFIED'


def test_invalid_source_basic_checks_cannot_become_verified_by_matching_close(tmp_path):
    origin=['A:first']
    def provider(r):
        return httpx.Response(200,json={'code':0,'data':{'sh600519':{'day':[['2026-09-30','100','100','90','80','100']],
            'qfqday':[['2026-09-30','100','100','90','80','100']]}},
            '_roll14_original_provenance':{'original_record':origin[0],'producer':origin[0].split(':')[0],
                'generation_basis':'METHOD_CASE separate generation','origin_kind':'DIRECT_ORIGINAL'}})
    with TestClient(create_app(tmp_path,market_transport=httpx.MockTransport(provider))) as client:
        request=setup_request(client,groups=['DAILY'],daily_source='TENCENT')
        first=client.post('/api/data/requests/'+request['request_id']+'/retrieve').json()
        origin[0]='B:second';second=client.post('/api/data/requests/'+request['request_id']+'/retrieve').json()
        payload=command([{'snapshot_id':r['snapshot_id'],'fact_index':0} for r in [first,second]])
        payload['facts'][0]['field']='close'
        result=client.post('/api/data/verifications',json=payload).json()
        assert result['result']=='INSUFFICIENT'
        assert 'SOURCE_BASIC_CHECK_FAILED' in result['facts'][0]['gaps']


def test_daily_raw_and_adjusted_values_are_not_comparable_even_when_equal(tmp_path):
    origin=['A:first']
    def provider(r):
        mode=r.url.params['param'].split(',')[-1]
        return httpx.Response(200,json={'code':0,'data':{'sh600519':{('qfqday' if mode else 'day'):
            [['2026-09-30','100','100','100','100','100']]}},
            '_roll14_original_provenance':{'original_record':origin[0],'producer':origin[0].split(':')[0],
                'generation_basis':'METHOD_CASE separate generation','origin_kind':'DIRECT_ORIGINAL'}})
    with TestClient(create_app(tmp_path,market_transport=httpx.MockTransport(provider))) as client:
        request=setup_request(client,groups=['DAILY'],daily_source='TENCENT')
        a=client.post('/api/data/requests/'+request['request_id']+'/retrieve').json()
        origin[0]='B:second';b=client.post('/api/data/requests/'+request['request_id']+'/retrieve').json()
        payload=command([{'snapshot_id':r['snapshot_id'],'fact_index':0} for r in [a,b]])
        payload['facts'][0]['field']='close'
        assert client.post('/api/data/verifications',json=payload).json()['result']=='VERIFIED'
        payload['facts'][0]['references'][1]['fact_index']=1
        result=client.post('/api/data/verifications',json=payload).json()
        assert result['result']=='INSUFFICIENT'
        assert 'ADJUSTMENT_NOT_COMPARABLE' in result['facts'][0]['gaps']
        assert result['facts'][0]['comparisons'][0]['values']=='EQUAL_DECIMAL'


def test_verification_payload_delivery_audits_sealed_fields_without_result_look(tmp_path):
    from test_research_protocol import engineering_archive
    dates=engineering_archive(tmp_path)
    def provider(r):
        mode=r.url.params['param'].split(',')[-1]
        return httpx.Response(200,json={'code':0,'data':{'sh600519':{('qfqday' if mode else 'day'):
            [[dates[160],'100','100','100','100','100']]}}})
    with TestClient(create_app(tmp_path,market_transport=httpx.MockTransport(provider))) as client:
        dataset=client.post('/api/research/datasets',json={'archive_id':'method-181','basis':'14 public input audit'}).json()
        protocol=client.post('/api/research/protocols',json={'dataset_id':dataset['dataset_id'],'basis':'14 only input exposure'}).json()
        request=setup_request(client,groups=['DAILY'],daily_source='TENCENT',purpose='RESEARCH',
            start_date=dates[160],end_date=dates[160])
        run=client.post('/api/data/requests/'+request['request_id']+'/retrieve').json()
        payload=command([{'snapshot_id':run['snapshot_id'],'fact_index':0}]);payload['facts'][0]['field']='close'
        response=client.post('/api/data/verifications',json=payload)
        assert response.status_code==201,response.text
        value=response.json();vid=value['verification_id']
        assert client.get('/api/data/verifications/'+vid).status_code==200
        assert client.get('/api/data/verifications').status_code==200
        assert client.post('/api/data/verifications/'+vid+'/replay').status_code==200
        from test_reviews import wait_result
        task=wait_result(client,client.post('/api/reviews/tasks',json={'mode':'ON_DEMAND'}).json()['task_id'])
        frozen=client.post('/api/reviews/tasks/'+task['task_id']+'/verification-request',json=payload).json()
        review_path='/api/reviews/verification-requests/'+frozen['request_id']
        assert client.post(review_path+'/verify').status_code==200
        assert client.get(review_path).status_code==200
        audit=client.get('/api/research/protocols/'+protocol['protocol_id']+'/audit').json()
        exposed=[e for e in audit if e['action']=='SEALED_MARKET_INPUT_EXPOSED' and e['route'].startswith('verification-')]
        assert {e['route'] for e in exposed}=={'verification-create','verification-query','verification-history','verification-replay',
            'verification-review-consume','verification-review-request'}
        assert all(e['confirmatory_pass_look'] is False and e['first_date']==dates[160] for e in exposed)
        assert client.get('/api/research/protocols/'+protocol['protocol_id']).json()==protocol


def test_frozen_review_request_consumes_once_and_links_original_audit_without_routine_upgrade(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from test_reviews import wait_result
    raw=[original_quote('A:first')]
    with TestClient(create_app(tmp_path,market_transport=httpx.MockTransport(lambda r:httpx.Response(200,content=raw[0])))) as client:
        request=setup_request(client);a=acquire(client)
        basis=completed(client,client.post('/api/data/requests/'+request['request_id']+'/resolve',json={
            'usage':'HISTORICAL_RESEARCH','allow_fallback':False}).json()['resolution_id'])
        raw[0]=original_quote('B:second');b=acquire(client)
        task=wait_result(client,client.post('/api/reviews/tasks',json={'mode':'ON_DEMAND'}).json()['task_id'])
        original=task['result'];audit_url='/api/reviews/audits/'+task['audit_id']
        assert client.get(audit_url).json()['critical_review']['status']=='NOT_REQUIRED'
        assert client.get('/api/data/verifications').json()==[]
        frozen=client.post('/api/reviews/tasks/'+task['task_id']+'/verification-request',json=command([a,b])).json()
        consume='/api/reviews/verification-requests/'+frozen['request_id']+'/verify'
        with ThreadPoolExecutor(max_workers=3) as pool:
            responses=list(pool.map(lambda _:client.post(consume),range(3)))
        assert all(r.status_code==200 for r in responses),[r.text for r in responses]
        identifiers={r.json()['verification_id'] for r in responses}
        assert len(identifiers)==1
        linked=client.get('/api/reviews/verification-requests/'+frozen['request_id']).json()
        vid=identifiers.pop();value=client.get('/api/data/verifications/'+vid).json()
        assert linked['status']=='CONSUMED' and linked['verification_id']==vid
        assert value['review_origin']=={k:frozen[k] for k in ['request_id','task_id','snapshot_id','audit_id']}
        from datetime import datetime
        assert datetime.fromisoformat(value['command']['knowledge_cutoff'])==datetime.fromisoformat(frozen['request']['knowledge_cutoff'])
        assert value['result']=='VERIFIED'
        assert client.get(audit_url).json()['critical_review']['verification_id']==vid
        assert len(client.get('/api/data/verifications').json())==1
        assert client.post('/api/reviews/tasks/'+task['task_id']+'/verification-request',json=command([a,b])).json()['verification_id']==vid
        raw[0]=original_quote('A:revised','101.000')
        completed(client,client.post('/api/data/requests/'+request['request_id']+'/resolve',json={
            'usage':'HISTORICAL_RESEARCH','allow_fallback':False,'use_cache':False,'revision_of':basis['resolution_id']}).json()['resolution_id'])
        current=client.post(consume).json()
        assert current['verification_id']==vid and current['dependency_status']=='INVALIDATED'
        assert current['current_result']=='INSUFFICIENT' and current['result']=='VERIFIED'
        assert client.get('/api/reviews/verification-requests/'+frozen['request_id']).json()['verification']['dependency_status']=='INVALIDATED'
        assert client.get('/api/reviews/tasks/'+task['task_id']).json()['result']==original
        assert client.get(audit_url).json()['critical_review']['verification_id']==vid
