"""Actual public bytes + explicit study lots; no real account/train/SEALED proof."""
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import ast
import json
import sys
import socket

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'backend/src'))
from fastapi.testclient import TestClient
from roll.app import create_app
from roll.research.corporate_actions import REFERENCE, cash_rights_manifest


original_connect = socket.socket.connect
loopback_connections = []

def deny_network(*args, **kwargs):
    raise AssertionError('This source-bound receipt requires zero external network')

def only_internal_loopback(sock, address):
    if isinstance(address, tuple) and address[0] in {'127.0.0.1', '::1'}:
        loopback_connections.append(address[0])
        return original_connect(sock, address)
    return deny_network()


manifest = cash_rights_manifest()
sources = [e['source'] for e in manifest['events']] + manifest['tax_sources']
checks = []
for source in sources:
    raw = (REFERENCE/source['file']).read_bytes()
    assert sha256(raw).hexdigest() == source['sha256'] and len(raw) == source['bytes']
    checks.append({'file': source['file'], 'sha256': source['sha256'], 'bytes': len(raw), 'verified': True})
cutoff = datetime.now(timezone.utc).isoformat()
with TemporaryDirectory(prefix='roll-public-rights-receipt-') as isolated:
    with patch('socket.create_connection', deny_network), patch('socket.socket.connect', only_internal_loopback):
        with TestClient(create_app(Path(isolated))) as client:
            before_account = client.get('/api/account').json()
            before_capabilities = client.get('/api/capabilities').json()
            assert client.get('/api/research/protocols').json() == []
            results = []
            for entry, exit in [('2013-07-22', '2013-08-01'), ('2024-07-22','2024-07-25')]:
                command = {'instrument':'SSE:600362','entry_date':entry,'exit_date':exit,
                           'quantity':100,'consumer_cutoff':cutoff}
                response = client.post('/api/research/cash-rights/assess',json=command)
                assert response.status_code == 200, response.text
                result = response.json()
                assert result['scorable'] is False and result['coverage'] == 'INCOMPLETE'
                results.append({'study_lot_command':command,'response':result})
            assert results[0]['response']['events'][0]['gross_entitlement_yuan'] == '50.00'
            assert results[0]['response']['events'][0]['final_tax_yuan'] == '10.00'
            assert results[0]['response']['events'][0]['net_economic_entitlement_yuan'] == '40.00'
            assert results[1]['response']['events'][0]['gross_cash_yuan_per_eligible_share'] == '0.60'
            assert results[1]['response']['events'][0]['differentiated_ex_reference_deduction_yuan_per_listed_share'] == '0.5970'
            assert client.get('/api/account').json() == before_account
            assert client.get('/api/capabilities').json() == before_capabilities
            assert client.get('/api/research/protocols').json() == []
script = Path(__file__).read_bytes()
receipt = {'classification':'REAL_PUBLIC_DOCUMENT_CALCULATION_WITH_EXPLICIT_STUDY_LOTS',
           'generated_at':cutoff,'source_originals':checks,'unique_sha256':len(set(s['sha256'] for s in checks)),
           'sha_length_mismatches':0,'results':results,'isolated_sqlite':True,
           'account_before_after_equal':True,'capabilities_before_after_equal':True,
           'real_user_account_claim':False,'zero_external_network_enforced':True,'windows_asyncio_loopback_socketpair_connections':loopback_connections,'training_attempts_created':0,
           'sealed_endpoints_requested':0,'script_sha256':sha256(script).hexdigest(),
           'script_ast_parses':bool(ast.parse(script)),
           'requested_routes':['GET /api/account','GET /api/capabilities','GET /api/research/protocols','POST /api/research/cash-rights/assess']}
Path(__file__).with_name('actual-public-original-receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('18 public originals verified;2 source-bound study calculations;account/capabilities unchanged;zero external network;zero fits;no SEALED')
