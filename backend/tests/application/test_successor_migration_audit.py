from fastapi.testclient import TestClient
from roll.app import create_app
from test_policy_successors import predecessor,register,migration,position
from test_successor_shadow import freeze_successor,frame


def test_migration_audit_keeps_blocked_original_deadline_and_new_lot_horizon(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        previous=predecessor(client,tmp_path);proposal=register(client,previous).json();receipt=migration(client,proposal,'SSE:600519',100,3).json()
        baseline=position('SSE:600519',100,receipt,3);baseline['sellable_quantity']=0
        frozen=freeze_successor(client,proposal,[baseline]).json()
        parent=client.get('/api/research/protocols/'+previous['protocol_id']).json();child=client.post('/api/research/protocols',json={'dataset_id':parent['dataset_id'],'predecessor_id':parent['protocol_id'],'basis':'Original lot/scope audit'}).json()
        base='/api/research/policy-successor-freezes/'+frozen['successor_freeze_id']
        protocol=client.post(base+'/complete-protocol',json={'protocol_id':child['protocol_id'],'expected_protocol_fingerprint':child['protocol_fingerprint'],'expected_successor_fingerprint':frozen['successor_fingerprint'],'idempotency_key':'parameters','basis':'Before migration observations'}).json()
        for day in range(1,6):assert client.post(base+'/shadow/advance',json=frame(day)).status_code==201
        state=client.get(base+'/shadow').json();source=client.post(base+'/cost-stress',json={'expected_complete_protocol_fingerprint':protocol['complete_protocol_fingerprint'],'expected_revision':5,'idempotency_key':'source','basis':'Saved migration timeline'}).json()
        route='/api/research/successor-cost-stresses/'+source['stress_id']+'/migration-audit';command={'idempotency_key':'audit','basis':'Original binding/deadlines, no transfer qualification'}
        response=client.post(route,json=command);assert response.status_code==201,response.text
        saved=response.json();identifier=saved['audit_id']
        assert saved['audit_status']=='CONSISTENT_METHOD_BINDINGS' and saved['binding_errors']==[]
        assert saved['registered_scope']['instruments']==['SSE:600519'] and saved['observed_instruments']==['SSE:600519']
        assert saved['scope_transfer_evidence']=='NOT_PROVEN' and saved['G5_status']=='INCONCLUSIVE'
        original=next(lot for lot in saved['lots'] if lot['baseline']);added=next(lot for lot in saved['lots'] if not lot['baseline'])
        assert original['expected_exit_session']==3 and original['migration_id']==receipt['migration_id']
        assert original['overdue_observed_sessions']==[3,4,5]
        assert [o['policy_migration_active'] for o in original['observations']]==[False,True,True,True,True]
        assert added['entry_session']==3 and added['expected_exit_session']==23
        assert all(o['exit_session']==23 for o in added['observations'])
        # Direct METHOD adapter adversaries, never persisted source mutations.
        import copy,json
        from roll.research.successor_migration import derive,METHOD
        payload=json.loads(client.app.state.evidence.raw(source['source']['sha256']).read_text(encoding='utf-8'));method=json.loads(METHOD.read_text(encoding='utf-8'))
        for row_index,baseline_lot in ((0,True),(2,False)):
            changed=copy.deepcopy(payload)
            target=next(p for p in changed['rows'][row_index][2]['result']['positions'] if p['baseline']==baseline_lot)
            target['position_id']='METHOD-REPLACED-POSITION'
            rejected=derive(source,changed,method)
            assert rejected['audit_status']=='INCONSISTENT_METHOD_BINDINGS'
            assert any('LOT_IDENTITY_OR_ORIGINAL_HORIZON_CHANGED' in error for error in rejected['binding_errors'])
            assert rejected['G5_status']=='INCONCLUSIVE'
        changed=copy.deepcopy(payload);changed['rows'][0][2]['result']['positions'][0]['quantity']=50
        assert any('LOT_REMAINING_QUANTITY_INCREASED' in error for error in derive(source,changed,method)['binding_errors'])
        assert client.post(route,json=command).json()==saved and client.get(route).json()==[saved]
        assert client.get(base+'/shadow').json()==state and client.get('/api/account').json()['version']==0
        assert client.post(base+'/shadow/advance',json=frame(6)).status_code==201
        assert client.post('/api/research/successor-migration-audits/'+identifier+'/replay').json()['matches_original'] is True
        raw=client.app.state.evidence.raw(saved['source_input']['sha256']);body=raw.read_bytes()
        try:
            raw.write_bytes(b'corrupt own migration source')
            assert client.get('/api/research/successor-migration-audits/'+identifier).status_code==409
        finally:raw.write_bytes(body)
    with TestClient(create_app(tmp_path)) as client:
        assert client.get('/api/research/successor-migration-audits/'+identifier).json()==saved
        assert client.post('/api/research/successor-migration-audits/'+identifier+'/replay').json()['matches_original'] is True
