from fastapi.testclient import TestClient
from roll.app import create_app
from test_policy_successors import predecessor,register,migration,position
from test_successor_shadow import freeze_successor,frame


def test_saved_entry_stress_delays_partial_lots_and_original_prefix(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        previous=predecessor(client,tmp_path);proposal=register(client,previous).json();frozen=freeze_successor(client,proposal).json()
        parent=client.get('/api/research/protocols/'+previous['protocol_id']).json()
        child=client.post('/api/research/protocols',json={'dataset_id':parent['dataset_id'],'predecessor_id':parent['protocol_id'],'basis':'Entry-only grid before METHOD outcomes'}).json()
        base='/api/research/policy-successor-freezes/'+frozen['successor_freeze_id']
        protocol=client.post(base+'/complete-protocol',json={'protocol_id':child['protocol_id'],'expected_protocol_fingerprint':child['protocol_fingerprint'],'expected_successor_fingerprint':frozen['successor_fingerprint'],'idempotency_key':'parameters','basis':'Frozen entry stress grid'}).json()
        for day in range(1,25):
            command=frame(day);command['bars'][0]['close_yuan']='10.20'
            response=client.post(base+'/shadow/advance',json=command);assert response.status_code==201,response.text
        state=client.get(base+'/shadow').json()
        stress=client.post(base+'/cost-stress',json={'expected_complete_protocol_fingerprint':protocol['complete_protocol_fingerprint'],'expected_revision':24,'idempotency_key':'cost-source','basis':'Immutable entry diagnostic source'}).json()
        route='/api/research/successor-cost-stresses/'+stress['stress_id']+'/entry-stress';command={'idempotency_key':'entries','basis':'Entry-only; no early SELL/horizon stress or qualification'}
        response=client.post(route,json=command);assert response.status_code==201,response.text
        saved=response.json();identifier=saved['diagnostic_id'];scenarios={s['scenario_id']:s for s in saved['scenarios']}
        assert len(scenarios)==6 and saved['base_matches_saved_prefix'] is True
        full=scenarios['NEXT_OPEN:1'];close=scenarios['NEXT_CLOSE:1'];delay=scenarios['ONE_MORE_SESSION_OPEN:1'];partial=scenarios['NEXT_OPEN:0.50']
        assert full['result']==state
        assert full['result']['events'][0]['session']==2 and full['result']['events'][0]['point']=='open_yuan'
        assert close['result']['events'][0]['session']==2 and close['result']['events'][0]['point']=='close_yuan'
        assert close['result']['events'][0]['price_yuan']!=full['result']['events'][0]['price_yuan']
        assert delay['result']['events'][0]['session']==3
        assert any(e['kind']=='SELL_FILL' and e['session']==23 for e in delay['result']['events'])
        assert partial['result']['events'][0]['quantity']==100
        assert any(e['kind']=='SELL_FILL' and e['session']==22 and e['quantity']==100 for e in partial['result']['events'])
        assert any(t['reason']=='PARTIAL_BELOW_MINIMUM_LOT' for t in partial['entry_attempts'])
        for name in ('NEXT_OPEN:0','OUTSIDE_ALLOWED_PRICE_NO_FILL:1'):
            assert not any(e['kind']=='BUY_FILL' for e in scenarios[name]['result']['events'])
            assert scenarios[name]['result']['cash_yuan']=='10000.00'
        assert all(len(s['curve'])==25 for s in scenarios.values())
        from decimal import Decimal
        for scenario in scenarios.values():
            result=scenario['result']
            assert Decimal(result['cash_yuan'])==Decimal('10000')+sum((Decimal(e['cash_delta_yuan']) for e in result['events'] if 'cash_delta_yuan' in e),Decimal(0))
        assert saved['G5_status'] in {'FAIL','INCONCLUSIVE'} and saved['statistical_pass'] is False
        assert client.post(route,json=command).json()==saved and client.get(route).json()==[saved]
        assert client.get(base+'/shadow').json()==state and client.get('/api/account').json()['version']==0
        assert client.get('/api/research/complete-freezes/'+previous['freeze_id']).json()==previous
        assert client.post(base+'/shadow/advance',json=frame(26,expected_revision=24,calendar_previous_session=25)).status_code==201
        sparse=client.post(base+'/cost-stress',json={'expected_complete_protocol_fingerprint':protocol['complete_protocol_fingerprint'],'expected_revision':25,'idempotency_key':'sparse','basis':'Keep gap25'}).json()
        changed=client.post('/api/research/successor-cost-stresses/'+sparse['stress_id']+'/entry-stress',json=command)
        assert changed.status_code==201,changed.text
        assert all(s['curve'][25]['nav_yuan'] is None and s['economics']['net_return'] is None for s in changed.json()['scenarios'])
        assert client.post('/api/research/successor-entry-stresses/'+identifier+'/replay').json()['matches_original'] is True
    with TestClient(create_app(tmp_path)) as client:
        assert client.get('/api/research/successor-entry-stresses/'+identifier).json()==saved
        assert client.post('/api/research/successor-entry-stresses/'+identifier+'/replay').json()['matches_original'] is True


def test_default_state_parity_with_migration_add_early_sell_horizon_and_unknowns(tmp_path):
    from roll.research.successor_entry_engine import simulate
    with TestClient(create_app(tmp_path)) as client:
        previous=predecessor(client,tmp_path);proposal=register(client,previous).json()
        receipt=migration(client,proposal,'SSE:600519',100,4).json()
        frozen=freeze_successor(client,proposal,[position('SSE:600519',100,receipt,4)]).json()
        base='/api/research/policy-successor-freezes/'+frozen['successor_freeze_id'];commands=[]
        for day in (1,2,3,4,5,6,7,9,10):
            command=frame(day,'0.40' if day in (6,7) else '0.80',expected_revision=len(commands))
            if day==5:command['bars'][0]['market_state']='UNKNOWN'
            response=client.post(base+'/shadow/advance',json=command);assert response.status_code==201,response.text
            commands.append(command);assert simulate(frozen,commands)==response.json()
        events=response.json()['events']
        assert any(e['kind']=='BUY_FILL' and e['session']==3 for e in events)
        assert any(e['kind']=='SELL_FILL' and e['session']==4 for e in events)
        assert any(e['kind']=='SELL_FILL' and e['session']==7 for e in events)
        # Delayed entry cannot jump over an undeclared intermediate slot.
        empty={**frozen,'baseline':{**frozen['baseline'],'positions':[]}}
        delayed=simulate(empty,[frame(1),frame(3,expected_revision=1)],{'delay':'ONE_MORE_SESSION_OPEN','fill_fraction':'1'})
        assert not any(e['kind']=='BUY_FILL' for e in delayed['events'])
        assert delayed['entry_stress_trace'][0]['reason']=='MISSED_NEXT_SESSION_NO_DISTANT_BAR_SUBSTITUTION'
        # Unknown executable input remains a no-fill rather than a fabricated price.
        unknown=frame(2);unknown['bars'][0]['company_actions']='UNKNOWN'
        result=simulate(empty,[frame(1),unknown],{'delay':'NEXT_CLOSE','fill_fraction':'1'})
        assert result['positions']==[] and result['entry_stress_trace'][0]['reason']=='MISSING_OR_UNKNOWN_EXECUTION_INPUT'
