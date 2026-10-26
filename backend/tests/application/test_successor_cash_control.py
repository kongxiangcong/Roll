from fastapi.testclient import TestClient
from roll.app import create_app
from test_policy_successors import predecessor,register,migration,position
from test_successor_shadow import freeze_successor,frame


def test_cash_control_keeps_full_window_zero_exposure_and_candidate_unknowns(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        previous=predecessor(client,tmp_path);proposal=register(client,previous).json();frozen=freeze_successor(client,proposal).json()
        parent=client.get('/api/research/protocols/'+previous['protocol_id']).json()
        child=client.post('/api/research/protocols',json={'dataset_id':parent['dataset_id'],'predecessor_id':parent['protocol_id'],'basis':'Frozen zero-exposure cash control'}).json()
        base='/api/research/policy-successor-freezes/'+frozen['successor_freeze_id']
        protocol=client.post(base+'/complete-protocol',json={'protocol_id':child['protocol_id'],'expected_protocol_fingerprint':child['protocol_fingerprint'],'expected_successor_fingerprint':frozen['successor_fingerprint'],'idempotency_key':'parameters','basis':'Before METHOD frames'}).json()
        for day in (1,2,3):assert client.post(base+'/shadow/advance',json=frame(day)).status_code==201
        def cost(revision,key):
            response=client.post(base+'/cost-stress',json={'expected_complete_protocol_fingerprint':protocol['complete_protocol_fingerprint'],'expected_revision':revision,'idempotency_key':key,'basis':'Saved METHOD control source'})
            assert response.status_code==201,response.text
            return response.json()
        stress=cost(3,'costs3');route='/api/research/successor-cost-stresses/'+stress['stress_id']+'/cash-control';command={'idempotency_key':'cash','basis':'Same original cash/slots, zero exposure and interest'}
        response=client.post(route,json=command)
        assert response.status_code==201,response.text
        saved=response.json();identifier=saved['control_id']
        assert saved['cash']['economics']['net_return']==0 and saved['cash']['gross_exposure_fraction']=='0'
        assert [p['nav_yuan'] for p in saved['cash']['curve']]==['10000.00']*4
        assert saved['risk_matched'] is False and saved['G4_status']=='INCONCLUSIVE'
        assert saved['candidate']['economics']['net_return']==stress['base']['economics']['net_return']
        assert saved['interval_return_difference']==saved['candidate']['economics']['net_return']
        assert client.post(route,json=command).json()==saved
        assert client.get(route).json()==[saved]
        gap=frame(5,expected_revision=3,calendar_previous_session=4);gap['bars'][0].update(close_yuan=None,completion='UNKNOWN',market_state='UNKNOWN',company_actions='UNKNOWN')
        assert client.post(base+'/shadow/advance',json=gap).status_code==201
        sparse=cost(4,'costs4');result=client.post('/api/research/successor-cost-stresses/'+sparse['stress_id']+'/cash-control',json=command).json()
        assert result['declared_sessions']==[0,1,2,3,4,5]
        assert result['candidate']['missing_declared_sessions']==[4]
        assert result['candidate']['economics']['net_return'] is None and result['interval_return_difference'] is None
        assert result['cash']['economics']['net_return']==0 and len(result['cash']['curve'])==6
        high=frame(6,expected_revision=4);high['bars'][0].update(open_yuan='200.00',high_yuan='210.00',low_yuan='190.00',close_yuan='200.00',reference_close_yuan='200.00')
        assert client.post(base+'/shadow/advance',json=high).status_code==201
        risk_source=cost(5,'risk-source')
        risk=client.post('/api/research/successor-cost-stresses/'+risk_source['stress_id']+'/cash-control',json=command)
        assert risk.status_code==201,risk.text
        assert risk.json()['G4_status']=='FAIL' and 'MAXIMUM_EXPOSURE_EXCEEDED' in risk.json()['hard_failures']
        assert risk.json()['candidate']['economics']['net_return'] is None
        assert client.post('/api/research/successor-cash-controls/'+identifier+'/replay').json()['matches_original'] is True
        assert client.get(base+'/complete-protocol').json()==protocol
        # Initial holdings cannot be silently liquidated to manufacture CASH.
        other=register(client,previous,version='METHOD-cash-nonempty-v2',idempotency_key='other-proposal').json()
        receipt=migration(client,other,'SSE:600519',100,20).json()
        with_position=freeze_successor(client,other,[position('SSE:600519',100,receipt)]).json()
        second_child=client.post('/api/research/protocols',json={'dataset_id':parent['dataset_id'],'predecessor_id':parent['protocol_id'],'basis':'Preserve actual METHOD starting lot'}).json()
        second_base='/api/research/policy-successor-freezes/'+with_position['successor_freeze_id']
        second_protocol=client.post(second_base+'/complete-protocol',json={'protocol_id':second_child['protocol_id'],'expected_protocol_fingerprint':second_child['protocol_fingerprint'],'expected_successor_fingerprint':with_position['successor_fingerprint'],'idempotency_key':'second-parameters','basis':'No liquidation assumption'}).json()
        assert client.post(second_base+'/shadow/advance',json=frame(1)).status_code==201
        second_stress=client.post(second_base+'/cost-stress',json={'expected_complete_protocol_fingerprint':second_protocol['complete_protocol_fingerprint'],'expected_revision':1,'idempotency_key':'nonempty-cost','basis':'METHOD initial lot retained'}).json()
        refused=client.post('/api/research/successor-cost-stresses/'+second_stress['stress_id']+'/cash-control',json=command)
        assert refused.status_code==409 and 'NO_ASSUMED_LIQUIDATION' in str(refused.json())
        assert client.get('/api/account').json()['version']==0
    with TestClient(create_app(tmp_path)) as client:
        assert client.get('/api/research/successor-cash-controls/'+identifier).json()==saved
