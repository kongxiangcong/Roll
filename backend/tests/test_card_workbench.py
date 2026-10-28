"""Bounded contract tests: temporary ledger, no real providers or model."""
import threading
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from roll.accounts.ledger import Ledger
from roll.runtime.assistance import Assistance, AssistanceCommand
from test_assistance import prices

def test_idempotency_identity_and_global_exclusion(tmp_path, monkeypatch):
    monkeypatch.setattr(threading.Thread, 'start', lambda self: None)
    service=Assistance(Ledger(tmp_path))
    command=AssistanceCommand(instrument='SZSE:000001',idempotency_key='one')
    a=service.start(command)
    assert service.start(command)['run_id']==a['run_id']
    assert service.history()[0]['instrument']=='SZSE:000001'
    with pytest.raises(HTTPException, match='ASSISTANCE_IDEMPOTENCY_CONFLICT'):
        service.start(AssistanceCommand(instrument='SSE:601899',idempotency_key='one'))
    with pytest.raises(HTTPException, match='ASSISTANCE_ALREADY_RUNNING'):
        service.start(AssistanceCommand(instrument='SSE:601899',idempotency_key='two'))

@pytest.mark.parametrize('symbol',['BSE:830001','SSE:688001','SZSE:300001','SSE:000001','bad'])
def test_unsupported_scope_rejected(symbol):
    with pytest.raises(ValidationError):AssistanceCommand(instrument=symbol)

@pytest.mark.parametrize('instrument,symbol',[('SSE:601899','sh.601899'),('SZSE:000001','sz.000001')])
def test_source_material_result_identity_and_partial(tmp_path,monkeypatch,instrument,symbol):
    service=Assistance(Ledger(tmp_path));seen=[]
    def source(run,s,cancel):
        seen.append(s);rows=[{**r,'code':s} for r in prices()]
        return {'source_id':s,'rows':rows,'last_date':rows[-1]['date']}
    monkeypatch.setattr(service,'source',source)
    monkeypatch.delenv('ROLL_CODEX_AUTH_FILE',raising=False)
    run={'run_id':'fixture','instrument':instrument,'sources':[],'gaps':[],'as_of':'2026-02-14','status':'RUNNING'}
    service.execute(run,threading.Event())
    saved=service.get('fixture')
    assert seen==[symbol,'sh.000001','sh.000300','sz.399006']
    assert saved['material']['instrument']==instrument
    assert saved['instrument']==instrument and saved['status']=='PARTIAL'
    assert saved['backtest'] and saved['sources'][0]['source_id']==symbol

def test_cancel_keeps_partial_and_prevents_late_success(tmp_path,monkeypatch):
    service=Assistance(Ledger(tmp_path));event=threading.Event()
    run={'run_id':'cancel','instrument':'SSE:601899','sources':[],'gaps':[],'status':'RUNNING'}
    service.save(run)
    service.active['cancel']=(event,None)
    def source(run,s,cancel):
        service.cancel('cancel')
        return {'source_id':s,'rows':prices(),'last_date':'2026-02-14'}
    monkeypatch.setattr(service,'source',source)
    service.execute(run,event)
    saved=service.get('cancel')
    assert saved['status']=='CANCELLED' and saved['sources']
    service.save({**saved,'status':'COMPLETE','assessment':{'summary':'late'}})
    assert service.get('cancel')['status']=='CANCELLED'

def test_cancelled_restart_preserves_content(tmp_path):
    s=Assistance(Ledger(tmp_path))
    s.save({'run_id':'interrupted','status':'CANCEL_REQUESTED','sources':['kept'],'host_owner':{'pid':0,'creation_ticks':1}})
    value=Assistance(Ledger(tmp_path)).get('interrupted')
    assert value['status']=='INTERRUPTED' and value['sources']==['kept']
