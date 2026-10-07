import httpx
import pytest
from test_account_process import Server
from test_fill_process import BASELINE


@pytest.mark.parametrize('fault,count',[('valuation_before_commit',0),('valuation_after_commit',1),('after_receipt',1)])
def test_valuation_anchor_and_version_are_atomic_and_replay_after_native_restart(tmp_path,fault,count):
    directory=tmp_path/'data'
    server=Server(directory)
    draft=server.client.post('/api/account/drafts',json=BASELINE).json()
    server.client.post('/api/account/confirm',json={'draft_id':draft['draft_id'],'idempotency_key':'baseline'})
    account=server.client.get('/api/account').json()
    server.stop()
    server=Server(directory,None if fault=='after_receipt' else fault)
    command={'baseline_account_version':1,'origin_at':BASELINE['payload']['effective_at'],'as_of':'2026-10-07T16:00:00+08:00'}
    original=None
    try:
        if fault=='after_receipt':
            response=server.client.post('/api/account/valuations',json=command)
            assert response.status_code==201,response.text
            original=response.json()
        else:
            with pytest.raises(httpx.TransportError):server.client.post('/api/account/valuations',json=command)
            assert server.process.wait(timeout=10)==86
    finally:server.stop()
    recovered=Server(directory)
    try:
        client=recovered.client
        versions=client.get('/api/account/valuations').json()
        assert len(versions)==count
        if not versions:
            versions=[client.post('/api/account/valuations',json=command).json()]
        value=versions[0]
        assert value['facts']['net_assets']=='100000.00'
        assert client.post('/api/account/valuations/'+value['valuation_id']+'/replay').json()==value
        if original:assert value==original
        assert client.get('/api/account').json()==account
        assert client.get('/api/funding').json()['version']==0
    finally:recovered.stop()
