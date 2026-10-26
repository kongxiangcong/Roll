from fastapi.testclient import TestClient
from roll.app import create_app
from test_policy_successors import predecessor,register
from test_successor_shadow import freeze_successor,frame


def test_joint_scenarios_keep_candidate_and_original_control_timing(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        previous=predecessor(client,tmp_path);proposal=register(client,previous).json();frozen=freeze_successor(client,proposal).json()
        parent=client.get('/api/research/protocols/'+previous['protocol_id']).json()
        child=client.post('/api/research/protocols',json={'dataset_id':parent['dataset_id'],'predecessor_id':parent['protocol_id'],'basis':'Paired fixed scenarios before METHOD results'}).json()
        base='/api/research/policy-successor-freezes/'+frozen['successor_freeze_id']
        protocol=client.post(base+'/complete-protocol',json={'protocol_id':child['protocol_id'],'expected_protocol_fingerprint':child['protocol_fingerprint'],'expected_successor_fingerprint':frozen['successor_fingerprint'],'idempotency_key':'parameters','basis':'Original comparator contracts'}).json()
        for day in range(1,46):
            observation=frame(day)
            if day>=22:observation['bars'][0].update(open_yuan='11.00',high_yuan='11.00',low_yuan='10.50',close_yuan='11.00',reference_close_yuan='10.00' if day==22 else '11.00')
            assert client.post(base+'/shadow/advance',json=observation).status_code==201
        state=client.get(base+'/shadow').json()
        def components(revision,key):
            source=client.post(base+'/cost-stress',json={'expected_complete_protocol_fingerprint':protocol['complete_protocol_fingerprint'],'expected_revision':revision,'idempotency_key':key,'basis':'Same paired METHOD prefix'}).json()
            route='/api/research/successor-cost-stresses/'+source['stress_id']
            controls=client.post(route+'/registered-controls',json={'idempotency_key':'controls','basis':'Original control contracts'}).json()
            entry=client.post(route+'/entry-stress',json={'idempotency_key':'entry','basis':'Same entry grid and source'}).json()
            return source,route,controls,entry
        source,route,controls,entry=components(45,'source')
        command={'controls_id':controls['comparison_id'],'entry_id':entry['diagnostic_id'],'idempotency_key':'joint','basis':'Paired scenario labels preserve original timing; no qualification'}
        response=client.post(route+'/joint-stress',json=command);assert response.status_code==201,response.text
        saved=response.json();identifier=saved['joint_id'];scenarios={s['scenario_id']:s for s in saved['scenarios']}
        assert len(scenarios)==12 and all(set(s['controls'])=={'CASH','START_HOLD','MA5_MA20'} for s in scenarios.values())
        default=scenarios['ENTRY:NEXT_OPEN:1'];half=scenarios['ENTRY:NEXT_OPEN:0.50']
        for name in controls['controls']:assert default['controls'][name]['curve']==controls['controls'][name]['curve']
        assert default['candidate']['curve']==source['base']['curve']
        moving=half['controls']['MA5_MA20'];reverse=controls['label_to_method_session']
        assert [(reverse[e['date']],e['quantity']) for e in moving['events'] if e['kind']=='BUY_FILL']==[(23,'100')]
        assert [reverse[e['date']] for e in moving['events'] if e['kind']=='SELL_FILL']==[42]
        assert moving['interval_return_difference'] is None and 'NO_PRERUN_MA_CONTEXT_FOR_ORIGINAL_FULL_WINDOW' in moving['eligibility_gaps']
        assert all(not any(e['kind']=='SELL_FILL' for e in s['controls']['START_HOLD']['events']) for s in scenarios.values())
        assert all(len(s['controls']['CASH']['curve'])==46 and s['risk_matched'] is False for s in scenarios.values())
        from decimal import Decimal
        assert Decimal(scenarios['COST:commission_scenario_rate=0.003']['controls']['START_HOLD']['fees_yuan'])>Decimal(default['controls']['START_HOLD']['fees_yuan'])
        assert saved['G5_status'] in {'FAIL','INCONCLUSIVE'} and saved['statistical_pass'] is False
        assert client.post(route+'/joint-stress',json=command).json()==saved and client.get(route+'/joint-stress').json()==[saved]
        assert client.get(base+'/shadow').json()==state and client.get('/api/account').json()['version']==0
        missing=frame(47,expected_revision=45);missing['bars'][0].update(close_yuan=None,completion='UNKNOWN',market_state='UNKNOWN',company_actions='UNKNOWN')
        assert client.post(base+'/shadow/advance',json=missing).status_code==201
        sparse,next_route,next_controls,next_entry=components(46,'sparse')
        assert client.post(next_route+'/joint-stress',json=command).status_code==409
        changed=client.post(next_route+'/joint-stress',json={**command,'controls_id':next_controls['comparison_id'],'entry_id':next_entry['diagnostic_id']})
        assert changed.status_code==201,changed.text
        assert all(s['candidate']['economics']['net_return'] is None and all(c['interval_return_difference'] is None for c in s['controls'].values()) for s in changed.json()['scenarios'])
        for day in (48,49,50):
            observation=frame(day,expected_revision=day-2)
            if day==50:observation['bars'][0].update(open_yuan='200.00',high_yuan='200.00',low_yuan='200.00',close_yuan='200.00',reference_close_yuan='200.00')
            assert client.post(base+'/shadow/advance',json=observation).status_code==201
        adverse,risk_route,risk_controls,risk_entry=components(49,'adverse')
        failed=client.post(risk_route+'/joint-stress',json={**command,'controls_id':risk_controls['comparison_id'],'entry_id':risk_entry['diagnostic_id']})
        assert failed.status_code==201,failed.text
        assert failed.json()['G5_status']=='FAIL'
        assert any('MAXIMUM_EXPOSURE_EXCEEDED' in s['candidate']['hard_failures'] for s in failed.json()['scenarios'])
        assert all(s['candidate']['economics']['net_return'] is None for s in failed.json()['scenarios'])
        archive=controls['input_archive'];raw=client.app.state.evidence.raw(archive['sha256']);original=raw.read_bytes()
        try:
            raw.write_bytes(b'corrupt nested control input')
            assert client.get('/api/research/successor-joint-stresses/'+identifier).status_code==409
            assert client.post('/api/research/successor-joint-stresses/'+identifier+'/replay').status_code==409
        finally:raw.write_bytes(original)
        assert client.post('/api/research/successor-joint-stresses/'+identifier+'/replay').json()['matches_original'] is True
    with TestClient(create_app(tmp_path)) as client:
        assert client.get('/api/research/successor-joint-stresses/'+identifier).json()==saved
        assert client.post('/api/research/successor-joint-stresses/'+identifier+'/replay').json()['matches_original'] is True
