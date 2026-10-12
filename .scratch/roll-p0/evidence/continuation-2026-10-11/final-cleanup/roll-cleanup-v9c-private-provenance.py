"""Metadata/public-source analysis only. Never opens any private candidate endpoint."""
import ast
import json
import re
from pathlib import Path

OUT = Path(__file__).parent
ROOT = Path('D:/dsh-proj/Roll')
TREES = {
    'ticket26': ROOT / '.scratch/worktrees/ticket26',
    'ticket28': ROOT / '.scratch/worktrees/ticket28',
}
OIDS = {
    'ticket26': 'e708764af833baee970f34fcc4112146c2c33958',
    'ticket28': '83c9289db44a1d6d6d91542b638e22eb45f5a72f',
}
E28 = '.scratch/roll-p0/evidence/continuation-2026-10-11/ticket28'
E26 = '.scratch/roll-p0/evidence/ticket26'
sources = [
    ('ticket28', 'backend/tests/application/test_notifications.py'),
    ('ticket28', 'backend/tests/recovery/test_notification_process.py'),
    ('ticket26', 'backend/tests/application/test_capabilities.py'),
]
functions = {}
public_reads = []
for tree, relative in sources:
    path = TREES[tree] / relative
    body = path.read_text(encoding='utf-8-sig')
    public_reads.append(str(path))
    functions[tree, relative] = [
        (node, body.splitlines()) for node in ast.parse(body).body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith('test_')
    ]

coverage_path = OUT / 'roll-cleanup-v9c-coverage-only.json'
coverage = json.loads(coverage_path.read_text(encoding='utf-8-sig'))
candidates = [r for r in coverage['uncovered'] if r.get('private_candidate')]
assert len(candidates) == 115
assert len({r['source'].casefold() for r in candidates}) == 115
assert {r['tree'] for r in candidates} == set(TREES)

def ref(tree, relative, first, last=None, role=None):
    return {'path': str(TREES[tree] / relative), 'source_oid': OIDS[tree],
            'line_start': first, 'line_end': last or first, 'role': role}

def receipt(tree):
    return str(ROOT / f'.scratch/roll-p0/evidence/continuation-2026-10-11/{tree}-independent/acceptance.md')

rows = []
for candidate in candidates:
    tree = candidate['tree']
    relative = candidate['relative'].replace('\\', '/')
    expected = str(TREES[tree] / relative).replace('/', '\\')
    assert candidate['source'].replace('/', '\\').casefold() == expected.casefold()
    row = {
        'source': candidate['source'], 'relative': relative, 'tree': tree,
        'bytes_from_prior_metadata': candidate['bytes'], 'source_oid': OIDS[tree],
        'contents_read': False, 'hashed': False, 'copied': False,
        'private_endpoint_stat_performed': False,
        'accepted_receipt': receipt(tree),
        'disposal_authorized': False, 'cleanup_gate_changed': False,
        'status': 'UNKNOWN', 'kind': 'UNKNOWN', 'source_provenance': [],
    }
    if tree == 'ticket26':
        assert relative == 't26-final1/test_archived_review_producer_0/auth.json'
        source = 'backend/tests/application/test_capabilities.py'
        match = [x for x in functions[tree, source] if x[0].name == 'test_archived_review_producer_proof_reuse_detects_changed_original_input']
        assert len(match) == 1
        node, lines = match[0]
        assert "monkeypatch.setenv('ROLL_ENV', 'test')" in '\n'.join(lines[node.lineno-1:node.end_lineno])
        assert "auth = tmp_path / 'auth.json'" in lines[303]
        assert 'METHOD_CASE_ONLY' in lines[304] and 'auth.write_text' in lines[304]
        row.update(status='PROVEN_PUBLIC_METHOD_WRITER_AND_CASE', kind='METHOD_AUTH_METADATA',
                   fixture_case=node.name,
                   path_binding='PYTEST_TMP_PATH_CASE_METADATA_AND_LITERAL_AUTH_WRITER',
                   source_provenance=[ref(tree, source, 301, 306, 'test-only auth writer; literal METHOD_CASE_ONLY')],
                   owner_scope_receipt=str(TREES[tree] / E26 / 'acceptance.md'))
    else:
        filename = relative.rsplit('/', 1)[1]
        assert filename in ('channel.json', 'channel.lock')
        row['source_provenance'] = [
            ref(tree, 'backend/src/roll/app.py', 888, 891, 'channel directory is SQLite ledger parent'),
            ref(tree, 'backend/src/roll/app.py', 900, 910, 'public config POST invokes channel.save'),
            ref(tree, 'backend/src/roll/runtime/notification_channel.py', 45, 47, 'exact notification-private paths'),
            ref(tree, 'backend/src/roll/runtime/notification_channel.py', 52, 61, 'channel.lock creation and locking'),
            ref(tree, 'backend/src/roll/runtime/notification_channel.py', 85, 106, 'validated config persisted to channel.json'),
            ref(tree, 'backend/src/roll/runtime/backups.py', 40, 49, 'atomic persist/private-directory helper'),
        ]
        row['owner_scope_receipt'] = str(TREES[tree] / E28 / 'acceptance.md')
        if relative.startswith('backend/.test-tmp-notifications-browser-green2/'):
            row.update(
                proposed_kind='METHOD_NOTIFICATION_PRIVATE_METADATA',
                fixture_case='station explicit read, old link current state and disabled private channel settings',
                unknown_reason='No inspected public receipt binds the exact browser-green2 dataDir to this browser run. Static synthetic writer and dataDir seam are proven; the exact runtime caller binding remains unproven.',
                path_binding='UNPROVEN_EXACT_BROWSER_PROFILE_CALLER',
                candidate_browser_run_log=str(TREES[tree] / E28 / '24-browser-green.log'),
            )
            row['source_provenance'] += [
                ref(tree, 'frontend/tests/e2e/notifications.spec.ts', 3, 38, 'synthetic disabled channel UI writer'),
                ref(tree, 'frontend/src/components/notification-channel-panel.tsx', 8, 13, 'settings save submits channel POST'),
                ref(tree, 'frontend/playwright.config.ts', 5, 10, 'caller dataDir env seam passed as ROLL_DATA_DIR; ROLL_ENV=test'),
            ]
        else:
            parts = relative.split('/')
            assert len(parts) == 6 and parts[3:] == ['data', 'notification-private', filename]
            assert re.fullmatch(r'\.test-tmp-notifications-\d{2}', parts[1])
            case_directory = parts[2]
            prefix = re.sub(r'\d+$', '', case_directory).rstrip('_')
            matches = [(source, node, lines) for (t, source), values in functions.items()
                       if t == tree for node, lines in values if node.name.startswith(prefix)]
            assert len(matches) == 1, (relative, [(v[0], v[1].name) for v in matches])
            source, node, lines = matches[0]
            fragment = '\n'.join(lines[node.lineno-1:node.end_lineno])
            assert re.search(r"monkeypatch\.setenv\('ROLL_ENV',\s*'test'\)", fragment), (relative, node.name, 'missing literal test env')
            assert re.search(r"tmp_path\s*/\s*'data'", fragment)
            assert "'/api/notification-channel'" in fragment
            if node.name == 'test_invalid_config_unknown_fields_and_storage_failure_never_echo_synthetic_secret':
                assert filename == 'channel.lock'
                assert 'SYNTHETIC_CHANNEL_FAILURE_CANARY' in fragment and "'enabled':False" in fragment
                assert "monkeypatch.setattr('roll.runtime.notification_channel.persist', broken_storage)" in fragment
            else:
                assert 'ntfy.example.test' in fragment or 'method-loopback' in fragment, (relative, node.name, 'missing known public synthetic server')
            markers = []
            for n in range(node.lineno, node.end_lineno + 1):
                line = lines[n-1]
                if any(m in line for m in ('ROLL_ENV', 'tmp_path', "'/api/notification-channel'", 'ntfy.example.test', 'method-loopback', 'MockTransport')):
                    markers.append(ref(tree, source, n, role='literal test-only caller/config/transport'))
            row.update(status='PROVEN_PUBLIC_METHOD_WRITER_AND_CASE', kind='METHOD_NOTIFICATION_PRIVATE_METADATA',
                       fixture_case=node.name, fixture_case_directory=case_directory,
                       path_binding='PYTEST_TMP_PATH_UNIQUE_CASE_METADATA_AND_PUBLIC_DATA_WRITER',
                       historical_run_result='NOT_RECLASSIFIED; existing historical red/green remain separate')
            row['source_provenance'] = [ref(tree, source, node.lineno, node.end_lineno, 'unique public METHOD fixture case')] + markers + row['source_provenance']
    rows.append(row)

summary = {
    'exact_candidates': len(rows),
    'proven_public_method_writer_and_case': sum(r['status'].startswith('PROVEN') for r in rows),
    'unknown': sum(r['status'] == 'UNKNOWN' for r in rows),
    'notification_private_metadata': sum(r['kind'] == 'METHOD_NOTIFICATION_PRIVATE_METADATA' for r in rows),
    'auth_metadata': sum(r['kind'] == 'METHOD_AUTH_METADATA' for r in rows),
    'private_contents_read': 0, 'private_hashes': 0, 'private_copies': 0,
    'private_endpoint_stats': 0, 'tests': 0, 'sqlite_connections': 0,
    'cim_calls': 0, 'git_mutations': 0, 'cleanup_or_release_actions': 0,
}
assert summary['proven_public_method_writer_and_case'] == 113 and summary['unknown'] == 2
result = {'scope': 'EXACT_115_METADATA_AND_PUBLIC_SOURCE_ONLY', 'summary': summary,
          'input_coverage_metadata': str(coverage_path),
          'source_identity_kind': 'previously read-only verified source HEAD; no body hashes here',
          'private_endpoint_io': 'No candidate source endpoint opened, hashed, copied or statted by this script.',
          'authority': 'Provenance mapping only; no disposal or release authorization and no new business acceptance.',
          'public_source_reads_by_this_script': public_reads, 'rows': rows}
destination = OUT / 'roll-cleanup-v9c-private-provenance.json'
destination.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'output': str(destination), 'summary': summary}, ensure_ascii=False))
