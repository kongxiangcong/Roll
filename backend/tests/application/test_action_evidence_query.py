import httpx
from fastapi.testclient import TestClient
from roll.app import create_app
from test_sse_company_actions import actual_bodies,method_clock


def test_action_query_preserves_versions_and_partial_originals_at_cutoff(tmp_path,monkeypatch):
    method_clock(monkeypatch)
    bodies=actual_bodies();calls=[]
    def source(request):
        calls.append(request)
        return httpx.Response(200,content=bodies[request.url.params['sqlId']])
    transport=httpx.MockTransport(source)
    with TestClient(create_app(tmp_path,market_transport=transport,runtime_role='API')) as client:
        plan=client.post('/api/research/collections',json={'instrument':'SSE:600362','basis':'Isolated action query'}).json()
        base='/api/research/collections/'+plan['plan_id']
        receipt=client.post(base+'/sse-company-actions',json={'basis':'Saved original action evidence fixture'}).json()
        assessment=client.post(base+'/sse-action-assessments',json={'source_receipt_id':receipt['receipt_id'],'basis':'Explicit observed original schema'}).json()
        response=client.get(base+'/action-evidence',params={'known_by':'2026-10-11T21:00:00+08:00'})
        assert response.status_code==200,response.text
        value=response.json()
        assert value['assessment_ids']==[assessment['assessment_id']]
        saved=value['assessments'][0]
        assert saved['role_audits']['dividend']['missing_reported_rows']==1
        assert len(saved['candidates'])==5
        assert saved['candidates'][0]['payment_fulfilled'] is None
        assert not value['complete_action_coverage'] and not value['pending_older_obligations_complete']
        assert value['network_calls']==value['account_events_added']==0
        assert client.get(base+'/action-evidence',params={'known_by':'2026-10-11T20:59:59+08:00'}).json()['assessment_ids']==[]
        assert len(calls)==2
    with TestClient(create_app(tmp_path,market_transport=transport,runtime_role='API')) as client:
        assert client.get(base+'/action-evidence',params={'known_by':'2026-10-11T21:00:00+08:00'}).json()==value
        assert client.get('/api/account').json()['version']==0
