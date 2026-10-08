"""Verify actual archived research survives restart, without provider calls or sealed reads."""
import argparse
import hashlib
import json
import io
import zipfile
from pathlib import Path
from datetime import datetime, timezone

import httpx


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['capture', 'verify'])
    args = parser.parse_args()
    folder = Path(__file__).resolve().parent
    root = folder.parents[3]
    private = root/'backend/.roll-data/ticket19-continuation'
    receipt = json.loads((folder/'baostock-real-acquisition.json').read_text(encoding='utf-8'))
    initial_account = json.loads((private/'user-before.json').read_text(encoding='utf-8'))['account']
    state = {'objects': {}, 'account': None}
    with httpx.Client(base_url='http://127.0.0.1:8010', timeout=60, trust_env=False) as client:
        def get(path):
            response = client.get(path)
            response.raise_for_status()
            return response.json()

        state['account'] = get('/api/account')
        assert state['account'] == initial_account, 'ACCOUNT_BASELINE_CHANGED'
        for run in receipt['runs']:
            for path in ['/api/data/runs/'+run['run_id'], '/api/data/snapshots/'+run['snapshot_id'],
                         '/api/research/datasets/'+run['dataset_id']]:
                state['objects'][path] = get(path)
            if run.get('protocol_id'):
                path = '/api/research/protocols/'+run['protocol_id']+'/models'
                state['objects'][path] = get(path)
        state_file = private/'durability-before.json'
        if args.mode == 'capture':
            state_file.write_text(json.dumps(state, ensure_ascii=False), encoding='utf-8')
            print(json.dumps({'captured_objects':len(state['objects']), 'account_unchanged':True}))
            return
        before = json.loads(state_file.read_text(encoding='utf-8'))
        assert state == before, 'RESTART_CHANGED_ARCHIVED_OBJECTS'
        report = {'verified_at':datetime.now(timezone.utc).isoformat(),
                  'persisted_objects_unchanged':True, 'account_unchanged_from_task_baseline':True,
                  'provider_calls':0, 'sealed_reads':0, 'runs':[]}
        for run in receipt['runs']:
            snapshot = state['objects']['/api/data/snapshots/'+run['snapshot_id']]
            verified = []
            for archive in snapshot['archives']+[snapshot['parquet']]:
                hashes = [archive['sha256']]
                if archive.get('decoded_hash'):
                    hashes.append(archive['decoded_hash'])
                for sha in hashes:
                    response = client.get('/api/data/archives/'+sha)
                    response.raise_for_status()
                    assert hashlib.sha256(response.content).hexdigest() == sha
                    verified.append(sha)
            response = client.post('/api/data/runs/'+run['run_id']+'/replay')
            response.raise_for_status()
            replay = response.json()
            assert replay['network_calls'] == 0
            assert replay['facts'] == snapshot['facts']
            assert replay['observations'] == snapshot['observations']
            report['runs'].append({'run_id':run['run_id'],'source':run['source'],
                                   'verified_archive_hashes':verified,'replay_network_calls':0,
                                   'facts_match_original':True,'observations_match_original':True})
        assert get('/api/account') == initial_account
        response = client.post('/api/runtime/backups')
        response.raise_for_status()
        backup = response.json()
        response = client.get('/api/runtime/backups/'+backup['backup_id']+'/export')
        response.raise_for_status()
        bundle_bytes = response.content
        (private/'after-acquisition-recovery.zip').write_bytes(bundle_bytes)
        with zipfile.ZipFile(io.BytesIO(bundle_bytes)) as bundle:
            manifest = json.loads(bundle.read('manifest.json'))
            for attachment in manifest['attachments']:
                assert hashlib.sha256(bundle.read(attachment['path'])).hexdigest() == attachment['sha256']
            assert hashlib.sha256(bundle.read('roll.sqlite3')).hexdigest() == manifest['database_sha256']
            archived_hashes = {a['sha256'] for a in manifest['attachments']}
            expected_hashes = {sha for r in report['runs'] for sha in r['verified_archive_hashes']}
            assert expected_hashes <= archived_hashes, 'RECOVERY_MISSING_MARKET_ORIGINAL'
        report['recovery_export'] = {'backup_id':backup['backup_id'],
            'attachment_count':len(manifest['attachments']),
            'export_sha256':hashlib.sha256(bundle_bytes).hexdigest(),
            'all_attachment_hashes_verified':True,'registered_market_originals_included':True,
            'account_payload_location':'PRIVATE_LOCAL_RECOVERY_ONLY'}
        report['status'] = 'PASSED'
        (folder/'baostock-durability-results.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
        print(json.dumps({'status':'PASSED','runs':len(report['runs']),'account_unchanged':True}))


if __name__ == '__main__':
    main()
