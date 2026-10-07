"""09's actual linked-cash caller regression across native confirmation faults."""
import httpx
import pytest
from test_account_process import Server
from test_fill_process import BASELINE


@pytest.mark.parametrize('fault,version',[('before_commit',4),('after_commit',5),('after_receipt',5)])
def test_linked_tax_restatement_and_immutable_original_recover_atomically(tmp_path,fault,version):
    directory=tmp_path/'data'
    server=Server(directory)
    common={'effective_at':'2026-10-07T12:00:00+08:00','source':'合成恢复税款原件','basis':'关联金额皆为8元'}
    commands=[BASELINE,
        {'kind':'PENDING_ITEM','expected_account_version':1,'payload':{**common,'record_id':'tax','item_type':'TAX','amount':'10','instrument':None}},
        {'kind':'SETTLEMENT','expected_account_version':2,'payload':{**common,'effective_at':'2026-10-07T13:00:00+08:00','record_id':'paid','target_record_id':'tax','amount':'10','broker_available_after':None}},
        {'kind':'CASH_CORRECTION','expected_account_version':3,'payload':{**common,'effective_at':'2026-10-07T14:00:00+08:00','record_id':'paid-fixed','target_record_id':'paid','corrected_amount':'8','broker_available_after':None}}]
    for index,command in enumerate(commands):
        draft=server.client.post('/api/account/drafts',json=command).json()
        response=server.client.post('/api/account/confirm',json={'draft_id':draft['draft_id'],'idempotency_key':str(index)})
        assert response.status_code==200,response.text
    original=server.client.get('/api/account/versions/3').json()
    final={'kind':'CASH_CORRECTION','expected_account_version':4,'payload':{**common,
        'effective_at':'2026-10-07T15:00:00+08:00','record_id':'tax-fixed','target_record_id':'tax','corrected_amount':'8','broker_available_after':None}}
    draft=server.client.post('/api/account/drafts',json=final).json()
    assert draft['status']=='READY',draft
    request={'draft_id':draft['draft_id'],'idempotency_key':'final-tax'}
    server.stop()
    server=Server(directory,None if fault=='after_receipt' else fault)
    receipt=None
    try:
        if fault=='after_receipt':
            response=server.client.post('/api/account/confirm',json=request)
            assert response.status_code==200,response.text
            receipt=response.json()
        else:
            with pytest.raises(httpx.TransportError):server.client.post('/api/account/confirm',json=request)
            assert server.process.wait(timeout=10)==86
    finally:server.stop()
    recovered=Server(directory)
    try:
        client=recovered.client
        value=client.get('/api/account').json()
        assert value['version']==version and value['cash_balance']=='99992.00'
        assert value['pending_expenses']==('2.00' if version==4 else '0.00')
        final_receipt=client.post('/api/account/confirm',json=request).json()
        assert final_receipt['account_version']==5
        if receipt:assert final_receipt==receipt
        assert client.post('/api/account/confirm',json=request).json()==final_receipt
        assert client.get('/api/account').json()['pending_expenses']=='0.00'
        assert client.get('/api/account/replay').json()['cash_balance']=='99992.00'
        assert client.get('/api/account/versions/3').json()==original
    finally:recovered.stop()
