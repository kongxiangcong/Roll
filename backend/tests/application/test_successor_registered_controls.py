from fastapi.testclient import TestClient
from roll.app import create_app
from test_policy_successors import predecessor,register
from test_successor_shadow import freeze_successor,frame


def test_registered_controls_keep_original_exit_rules_and_full_method_window(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        previous=predecessor(client,tmp_path);proposal=register(client,previous).json();frozen=freeze_successor(client,proposal).json()
        parent=client.get('/api/research/protocols/'+previous['protocol_id']).json()
        child=client.post('/api/research/protocols',json={'dataset_id':parent['dataset_id'],'predecessor_id':parent['protocol_id'],'basis':'Original registered controls, no new strategy search'}).json()
        base='/api/research/policy-successor-freezes/'+frozen['successor_freeze_id']
        protocol=client.post(base+'/complete-protocol',json={'protocol_id':child['protocol_id'],'expected_protocol_fingerprint':child['protocol_fingerprint'],'expected_successor_fingerprint':frozen['successor_fingerprint'],'idempotency_key':'parameters','basis':'Before all METHOD observations'}).json()
        for day in range(1,46):
            command=frame(day)
            if day>=22:command['bars'][0].update(open_yuan='11.00',high_yuan='11.00',low_yuan='10.50',close_yuan='11.00',reference_close_yuan='10.00' if day==22 else '11.00')
            response=client.post(base+'/shadow/advance',json=command)
            assert response.status_code==201,response.text
        state=client.get(base+'/shadow').json()
        stress=client.post(base+'/cost-stress',json={'expected_complete_protocol_fingerprint':protocol['complete_protocol_fingerprint'],'expected_revision':45,'idempotency_key':'cost-source','basis':'Saved original trajectory only'}).json()
        route='/api/research/successor-cost-stresses/'+stress['stress_id']+'/registered-controls';command={'idempotency_key':'controls','basis':'Same source/cash/costs/cap; preserve old comparator timing, no risk qualification'}
        response=client.post(route,json=command)
        assert response.status_code==201,response.text
        saved=response.json();identifier=saved['comparison_id']
        assert set(saved['controls'])=={'CASH','START_HOLD','MA5_MA20'}
        assert all(len(c['curve'])==46 for c in saved['controls'].values())
        assert saved['controls']['CASH']['economics']['net_return']==0
        start=saved['controls']['START_HOLD'];moving=saved['controls']['MA5_MA20']
        assert any(e['kind']=='BUY_FILL' for e in start['events']) and not any(e['kind']=='SELL_FILL' for e in start['events'])
        assert any(e['kind']=='BUY_FILL' for e in moving['events']) and any(e['kind']=='SELL_FILL' for e in moving['events'])
        assert [saved['label_to_method_session'][e['date']] for e in moving['events'] if e['kind']=='BUY_FILL']==[23]
        assert [saved['label_to_method_session'][e['date']] for e in moving['events'] if e['kind']=='SELL_FILL']==[42]
        assert moving['interval_return_difference'] is None and 'NO_PRERUN_MA_CONTEXT_FOR_ORIGINAL_FULL_WINDOW' in moving['eligibility_gaps']
        assert 'OBSERVATION_PLUS_20' in saved['timing_contrast']['MA5_MA20'] and 'ENTRY_PLUS_20' in saved['timing_contrast']['candidate']
        assert saved['risk_matched_qualification'] is False and saved['statistical_pass'] is False
        assert client.post(route,json=command).json()==saved and client.get(route).json()==[saved]
        assert client.get(base+'/shadow').json()==state
        assert client.get('/api/research/complete-freezes/'+previous['freeze_id']).json()==previous
        assert client.get('/api/account').json()['version']==0
        for session in (47,48,49):
            command_frame=frame(session,expected_revision=45+(session-47),calendar_previous_session=session-1)
            command_frame['bars'][0].update(open_yuan='11.00',high_yuan='11.00',low_yuan='10.50',close_yuan='11.00',reference_close_yuan='11')
            if session==47:command_frame['bars'][0].update(close_yuan=None,completion='UNKNOWN',market_state='UNKNOWN',company_actions='UNKNOWN')
            assert client.post(base+'/shadow/advance',json=command_frame).status_code==201
        sparse=client.post(base+'/cost-stress',json={'expected_complete_protocol_fingerprint':protocol['complete_protocol_fingerprint'],'expected_revision':48,'idempotency_key':'sparse-source','basis':'METHOD retain missing calendar and unknown close'}).json()
        sparse_response=client.post('/api/research/successor-cost-stresses/'+sparse['stress_id']+'/registered-controls',json=command)
        assert sparse_response.status_code==201,sparse_response.text
        changed=sparse_response.json()
        assert len(changed['declared_sessions'])==50 and changed['candidate']['missing_declared_sessions']==[46]
        assert changed['candidate']['economics']['net_return'] is None
        assert all(c['interval_return_difference'] is None for c in changed['controls'].values())
        assert {r['session'] for r in changed['adapter_rejections']}=={47,48}  # Decimal 11 equals 11.00 on recovered slot49.
        assert client.post('/api/research/successor-registered-controls/'+identifier+'/replay').json()['matches_original'] is True
    with TestClient(create_app(tmp_path)) as client:
        assert client.get('/api/research/successor-registered-controls/'+identifier).json()==saved
        assert client.post('/api/research/successor-registered-controls/'+identifier+'/replay').json()['matches_original'] is True
