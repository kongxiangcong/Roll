"""Fresh closed legacy METHOD fixture for current default browser scope; no provider tasks."""
import json
import os
from pathlib import Path
import sqlite3

from fastapi.testclient import TestClient
from roll.app import create_app


def factory():
    if os.environ.get('ROLL_ENV')!='test':raise ValueError('CODEX_SCOPE_METHOD_TEST_ONLY')
    directory=Path(os.environ['ROLL_DATA_DIR'])
    if (directory/'roll.sqlite3').exists():raise ValueError('CODEX_SCOPE_METHOD_REQUIRES_FRESH_PROFILE')
    with TestClient(create_app(directory)) as client:
        draft=client.post('/api/account/drafts',json={'kind':'BASELINE','expected_account_version':0,
            'payload':{'effective_at':'2026-10-07T00:00:00+08:00','source':'Codex scope METHOD only',
                'cash_balance':'10000.00','broker_available':None,'broker_frozen':None,'withdrawable':None,
                'permission_profile':[],'positions':[{'instrument':'SSE:600519','quantity':'100',
                    'sellable_quantity':None,'reference_cost':None}]}})
        assert draft.status_code==201,draft.text
        confirmed=client.post('/api/account/confirm',json={'draft_id':draft.json()['draft_id'],'idempotency_key':'scope-baseline'})
        assert confirmed.status_code==200,confirmed.text
        request=client.post('/api/data/requests',json={'instruments':['SSE:600519'],'groups':['QUOTE'],
            'purpose':'OBSERVATION','start_date':'2026-10-07','end_date':'2026-10-07'})
        assert request.status_code==201,request.text
        request_id=request.json()['request_id']
    setting={'version':1,'backend':'DEEPSEEK','saved_at':'2026-10-08T00:00:00+00:00'}
    run={'run_id':'legacy-deepseek-method','request_id':request_id,'backend':'DEEPSEEK','model':'historical-method',
        'status':'CANCELLED','evidence_kind':'METHOD_CASE_LEGACY_ARCHIVE','started_at':'2026-10-08T00:00:00+00:00',
        'finished_at':'2026-10-08T00:00:01+00:00','backend_settings':setting,
        'config_fingerprint':'historical-method-fingerprint','question':'依据？','tools':[],'gaps':[]}
    # The first writer is closed; these bytes represent an old persisted setting/record.
    with sqlite3.connect(directory/'roll.sqlite3') as db:
        db.execute('INSERT INTO agent_settings VALUES(1,?)',(json.dumps(setting),))
        db.execute('INSERT INTO retrieval_runs VALUES(?,?,?)',(run['run_id'],request_id,json.dumps(run)))
    return create_app(directory)
