import httpx
import pytest
from test_account_process import Server
from test_fill_process import BASELINE


@pytest.mark.parametrize('kind',['CORRECTION','RECONCILIATION'])
@pytest.mark.parametrize('fault,expected_version',[('before_commit',2),('after_commit',3),('after_receipt',3)])
def test_rebuild_and_material_resolution_are_atomic_across_real_process_fault(tmp_path,kind,fault,expected_version):
    directory=tmp_path/'data'
    server=Server(directory)
    interest={'kind':'INTEREST','expected_account_version':1,'payload':{'effective_at':'2026-10-07T11:00:00+08:00','source':'合成实际利息凭证','record_id':'interest','amount':'10.00','instrument':None,'basis':'到账流水','broker_available_after':None}}
    receipts=[]
    for command,key in [(BASELINE,'baseline'),(interest,'interest')]:
        draft=server.client.post('/api/account/drafts',json=command).json()
        receipts.append(server.client.post('/api/account/confirm',json={'draft_id':draft['draft_id'],'idempotency_key':key}).json())
    old=server.client.get('/api/account/versions/2').json()
    invalid={**interest,'expected_account_version':2,'payload':{**interest['payload'],'record_id':'unknown-material','amount':None}}
    pending=server.client.post('/api/account/drafts',json=invalid).json()
    payload={'effective_at':'2026-10-07T12:00:00+08:00','source':'用户核对凭证','record_id':'fixed','reason':'原件金额错误，保留原件追加核对'}
    if kind=='CORRECTION':
        payload.update(target_event_id=receipts[-1]['event_ids'][0],replacement={'kind':'INTEREST','payload':{**interest['payload'],'amount':'20.00'}})
    else:
        payload.update(snapshot={'cash_balance':'100020.00','broker_available':'100020.00','broker_frozen':'0.00','withdrawable':None,'positions':[],'pending_items':[],'investment_income':'10.00','investment_expenses':'0.00'},resolved_draft_ids=[pending['draft_id']])
    draft=server.client.post('/api/account/drafts',json={'kind':kind,'expected_account_version':2,'payload':payload}).json()
    assert draft['status']=='READY',draft
    command={'draft_id':draft['draft_id'],'idempotency_key':'atomic-rebuild'}
    server.stop()
    server=Server(directory,None if fault=='after_receipt' else fault)
    original=None
    try:
        if fault=='after_receipt':
            response=server.client.post('/api/account/confirm',json=command)
            assert response.status_code==200
            original=response.json()
        else:
            with pytest.raises(httpx.TransportError):server.client.post('/api/account/confirm',json=command)
            assert server.process.wait(timeout=10)==86
    finally:server.stop()
    recovered=Server(directory)
    try:
        client=recovered.client
        assert client.get('/api/account').json()['version']==expected_version
        if kind=='RECONCILIATION':assert client.get('/api/account/drafts/'+pending['draft_id']).json()['status']==('QUARANTINED' if expected_version==2 else 'RESOLVED')
        receipt=client.post('/api/account/confirm',json=command).json()
        assert receipt['account_version']==3
        assert client.post('/api/account/confirm',json=command).json()==receipt
        if original:assert receipt==original
        account=client.get('/api/account').json()
        assert account['cash_balance']=='100020.00'
        assert client.get('/api/account/replay').json()['cash_balance']==account['cash_balance']
        assert client.get('/api/account/versions/2').json()==old
        assert client.get('/api/account/drafts/'+pending['draft_id']).json()['command']==invalid
        assert len(client.get('/api/account/events').json())==4
    finally:recovered.stop()
