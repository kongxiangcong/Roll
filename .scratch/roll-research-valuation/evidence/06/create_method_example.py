"""Create offline METHOD-only comparison and verify isolated restore via public services."""
import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path[:0] = [str(ROOT / 'backend/src'), str(ROOT / 'backend/tests/company_research')]
from test_shared_evidence import service
from test_economic_review import operating_request
from test_changes import quote_basis
from roll.research.company import ResearchContextCommand, ChangeSetCommand
from roll.research.company.change_calculator import compare_perpetuity
from roll.runtime.backups import Backups, restore_at_start


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--data-directory', type=Path, required=True)
    parser.add_argument('--restore-directory', type=Path, required=True)
    parser.add_argument('--output-directory', type=Path, required=True)
    args = parser.parse_args()
    for path in [args.data_directory, args.restore_directory]:
        if path.exists() and any(path.iterdir()):
            parser.error('Use a new empty store; existing stores are never overwritten')
    args.output_directory.mkdir(parents=True, exist_ok=True)
    research = service(args.data_directory)
    command, _ = operating_request(research)
    first = research.calculate_operating_valuation(command)
    snapshot = research.analysis_snapshot(first['snapshot_id'])
    old = research.freeze_research_context(ResearchContextCommand(snapshot_id=snapshot['snapshot_id'], quotes=quote_basis(research, snapshot, 10), change_reason='METHOD old nominal quotes, not actual company data'))
    command.snapshot_id = old['snapshot_id']; command.idempotency_key = 'method-mixed'
    command.config['wacc'] = .08
    command.economic_basis['wacc']['equity_risk_premium'] = .04
    for row in command.drivers['scenarios'][0]['years']: row['operating_margin'] = .22
    command.economic_basis['terminal']['roic'] = .33
    command.change_reason = 'METHOD explicit scenario/rate revision, not a market explanation'
    second = research.calculate_operating_valuation(command)
    snapshot = research.analysis_snapshot(second['snapshot_id'])
    new = research.freeze_research_context(ResearchContextCommand(snapshot_id=snapshot['snapshot_id'], quotes=quote_basis(research, snapshot, 12.5), change_reason='METHOD new nominal quotes, not actual company data'))
    result = research.compare_snapshots(ChangeSetCommand(old_snapshot_id=old['snapshot_id'], new_snapshot_id=new['snapshot_id'], presentation_purpose='BASELINE_RESEARCH', idempotency_key='method-mixed'))
    backup_service = Backups(args.data_directory)
    backup = backup_service.create()
    raw_backup = backup_service.export(backup['backup_id'])
    recovery = Backups(args.restore_directory); recovery.stage_restore(raw_backup); restore_at_start(recovery)
    restored = service(args.restore_directory)
    assert restored.change_set(result['change_set_id']) == result
    replay = restored.replay_change_set(result['change_set_id'])
    assert replay['matches_saved_comparison']
    assert restored.analysis_snapshot(new['snapshot_id'], 'DAILY') == restored.analysis_snapshot(new['snapshot_id'], 'REPORT')
    assert restored.replay_valuation(first['valuation_id'])['matches_saved_result']
    receipt = dict(classification='SYNTHETIC_METHOD_ONLY_NOT_ACTUAL_FINANCIAL_FORECAST_OR_QUOTE', network_calls=0, model_calls=0,
        old_snapshot_id=old['snapshot_id'], new_snapshot_id=new['snapshot_id'], change_set_id=result['change_set_id'],
        change_set_sha256=result['content_sha256'], comparison_archive=result['archive'], backup_sha256=hashlib.sha256(raw_backup).hexdigest(),
        restored_exact=True, replay=replay, account_version=restored.ledger.account()['version'],
        perpetual_example=compare_perpetuity(100, .1, 100, .08, 1000, 1250),
        source_files_04_unchanged=True,
        scenario_equity_minus_market=[s['model_equity_minus_market']['base'] for s in result['counterfactual']['steps']])
    for name, value in [('method-change-set.json', result), ('method-receipt.json', receipt)]:
        (args.output_directory / name).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8', newline='\n')
    print(json.dumps(receipt, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
