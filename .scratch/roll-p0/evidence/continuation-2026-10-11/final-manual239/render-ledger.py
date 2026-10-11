"""Render root's explicit clause decisions; never infer acceptance from code/counts."""
import argparse
import copy
import hashlib
import json
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', required=True)
    parser.add_argument('--historical', required=True)
    parser.add_argument('--decisions', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    root = Path(args.root).resolve()
    historical = Path(args.historical)
    decisions = json.loads(Path(args.decisions).read_text(encoding='utf-8-sig'))
    head = subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip()
    if head != decisions['target_root_oid']:
        raise SystemExit('Root HEAD changed; reconcile explicit decisions before rendering')
    for commit in decisions['accepted_dependency_commits']:
        subprocess.run(['git', '-C', str(root), 'merge-base', '--is-ancestor', commit, head], check=True)
    original_bytes = historical.read_bytes()
    original = json.loads(original_bytes.decode('utf-8-sig'))
    items = copy.deepcopy(original['items'])
    if len(items) != 239 or len({item['clause'] for item in items}) != 239:
        raise SystemExit('Historical ledger must contain239 unique literal clauses')
    by_clause = {item['clause']: item for item in items}
    updates = decisions['clause_updates']
    if not set(updates).issubset(by_clause):
        raise SystemExit('Unknown clause in explicit manual decisions')
    valid = set(original['status_definitions'])
    definitions = copy.deepcopy(original['status_definitions'])
    definitions['PENDING_OWNER_ACCEPTANCE'] = 'A required current implementation/consumer has not received independent acceptance; historical prerequisites do not close it.'
    for clause, update in updates.items():
        if update.get('status', by_clause[clause]['status']) not in valid:
            raise SystemExit(f'Unregistered status: {clause}')
        if not all(update.get(key) for key in ('current_evidence', 'actual_boundary', 'remaining', 'evidence_documents')):
            raise SystemExit(f'Explicit evidence/boundary/remaining/receipts required: {clause}')
        for relative in update['evidence_documents']:
            receipt = (root / relative).resolve()
            if not receipt.is_relative_to(root) or not receipt.is_file():
                raise SystemExit(f'Missing or out-of-root receipt: {relative}')
        by_clause[clause].update(update)
        by_clause[clause]['root_reconciliation'] = 'Explicit root clause decision from separate accepted finite receipts; no full-clause execution inferred.'
    for item in items:
        item['evidence_temporal_scope'] = (
            'Historical literal inputs/results remain at their original source. Root reread all239 clauses; '
            'only explicit clause_updates add accepted current finite evidence. No fresh239 behavior run.'
        )
    output = Path(args.output).resolve()
    if not output.is_relative_to(root) or output.exists():
        raise SystemExit('Output must be a new owned directory under root; do not overwrite historical ledger')
    output.mkdir(parents=True)
    result = {
        'classification': 'ROOT_MANUAL_CLAUSE_RECONCILIATION_NOT_FULL_PASS',
        'target_root_oid': head,
        'written_at_utc': datetime.now(timezone.utc).isoformat(),
        'historical_ledger_sha256': hashlib.sha256(original_bytes).hexdigest(),
        'historical_target_root_oid': original['target_root_oid'],
        'historical_metadata': {key: value for key, value in original.items() if key != 'items'},
        'historical_items': copy.deepcopy(original['items']),
        'method': 'Root manually reread239 existing literal clauses and applied explicit per-clause receipt decisions. Rendering is mechanical; acceptance is not derived from counts, names or ticket Completion.',
        'status_definitions': definitions,
        'clause_counts': original['clause_counts'],
        'status_counts': dict(Counter(item['status'] for item in items)),
        'explicitly_reconciled_clauses': list(updates),
        'unqualified_full_pass_count': 0,
        'fresh239_behavior_execution': False,
        'actual_codex_new_calls': 0,
        'actual_source_new_requests': 0,
        'external_notification_actual_sends': 0,
        'deepseek': 'EXCLUDED_CURRENT_AND_FUTURE_SCOPE_NOT_PASS',
        'statistical_state': 'FITTED_UNVALIDATED',
        'formal_qualification': 'NOT_GRANTED',
        'accepted_dependency_commits': decisions['accepted_dependency_commits'],
        'remaining_responsibilities': decisions['remaining_responsibilities'],
        'unnumbered_reconciliation': decisions.get('unnumbered_reconciliation', []),
        'items': items,
    }
    (output / 'ledger.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (output / 'historical-ledger.json').write_bytes(original_bytes)
    lines = [
        '# Final root manual clause ledger', '',
        f'Bound root snapshot: `{head}`.239 unique clauses:14 BR,125 P0,10 data invariants,90 AT.', '',
        'Root reread every historical literal row. Separate accepted finite checks are added only by explicit clause decisions. This is not a fresh239-case run or an unqualified full-spec PASS.', '',
        'Historical inputs, failed checks, source versions and limits remain in historical_items in ledger.json and the byte-identical historical-ledger.json. Actual approved95dd Codex review happened once earlier; this reconciliation makes0 new provider/source/notification calls. DeepSeek is excluded. FITTED_UNVALIDATED and NOT_GRANTED remain.', '',
        '## Remaining responsibilities', '',
        *[f'- {value}' for value in decisions['remaining_responsibilities']], '',
        '## All literal clauses', '',
        '| Clause | Status | Requirement | Evidence / boundary / remaining |',
        '| --- | --- | --- | --- |',
    ]
    def cell(value):
        return str(value).replace('|', '\\|').replace('\n', '<br>')
    for item in items:
        receipts = ' '.join(f'[{Path(path).name}]({root.as_posix()}/{path})' for path in item['evidence_documents'])
        detail = f"{item['current_evidence']}<br>Boundary: {item['actual_boundary']}<br>Remaining: {item['remaining']}<br>{receipts}"
        lines.append('| ' + ' | '.join(cell(value) for value in (item['clause'], item['status'], item['requirement'], detail)) + ' |')
    (output / 'ledger.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(json.dumps({'output': str(output), 'rows': len(items), 'explicit_updates': len(updates), 'status_counts': result['status_counts'], 'unqualified_full_pass_count': 0}))


if __name__ == '__main__':
    main()
