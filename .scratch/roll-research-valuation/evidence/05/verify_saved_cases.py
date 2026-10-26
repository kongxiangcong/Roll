"""Reopen and restore actual ticket05 records without network/model calls."""
import argparse
import hashlib
import json
from pathlib import Path
from roll.accounts.ledger import Ledger
from roll.market.directory import MarketDirectory
from roll.market.evidence import EvidenceStore
from roll.research.company import CompanyResearch
from roll.runtime.backups import Backups, restore_at_start

HERE = Path(__file__).resolve().parent


def service(path):
    ledger = Ledger(Path(path))
    return CompanyResearch(EvidenceStore(ledger, MarketDirectory(ledger)))


def main():
    p = argparse.ArgumentParser(); p.add_argument('--restore-directory', required=True); p.add_argument('--output', required=True)
    args = p.parse_args()
    receipt = json.loads((HERE / 'real-lulu-receipt.json').read_text(encoding='utf-8'))
    research = service(receipt['data_directory']); ids = receipt['result']
    snapshot = research.analysis_snapshot(ids['snapshot_id'])
    assert snapshot == research.analysis_snapshot(ids['snapshot_id'], 'REPORT')
    model = research.operating_model(ids['operating_model_id']); review = research.economic_review(ids['review_id'])
    assert review['policy_version'] == 'economic-review-2' and review['policy_archive'] == model['algorithm_archive']
    installed = (Path(__file__).resolve().parents[4] / 'backend/src/roll/research/company/economics.py').read_bytes()
    assert hashlib.sha256(installed).hexdigest() == review['policy_archive']['sha256']
    assert research.replay_valuation(ids['valuation_id'])['matches_saved_result']
    baseline = research.valuation_presentation(ids['review_id'], 'BASELINE_RESEARCH')
    current = research.valuation_presentation(ids['review_id'])
    assert baseline['status'] == 'conditional' and baseline['usable_range']
    assert current['status'] == 'blocked' and not current['usable_range'] and current['scenarios'] == []
    backups = Backups(research.ledger.path.parent); backup = backups.create()
    target = Path(args.restore_directory)
    if target.exists(): raise RuntimeError('Choose a new restore directory')
    recovery = Backups(target); recovery.stage_restore(backups.export(backup['backup_id'])); restore_at_start(recovery)
    restored = service(target)
    assert restored.analysis_snapshot(ids['snapshot_id']) == snapshot
    assert restored.operating_model(ids['operating_model_id']) == model
    assert restored.economic_review(ids['review_id']) == review
    assert restored.valuation_presentation(ids['review_id'], 'BASELINE_RESEARCH') == baseline
    assert restored.replay_valuation(ids['valuation_id'])['matches_saved_result']
    legacy = json.loads((HERE / 'attempt05-incomplete-audit/real-lulu-receipt.json').read_text(encoding='utf-8'))
    old = service(legacy['data_directory'])
    legacy_view = old.valuation_presentation(legacy['result']['review_id'], 'BASELINE_RESEARCH')
    assert legacy_view['status'] == 'blocked' and not legacy_view['usable_range']
    value = dict(status='PASS', shared_snapshot_equal=True, restored_refs_and_hashes=True, real_raw_calculator_replay=True,
        policy_version=review['policy_version'], policy_sha256=review['policy_archive']['sha256'], legacy_policy_prices_hidden=True,
        baseline_status=baseline['status'], current_status=current['status'], backup_id=backup['backup_id'],
        restore_directory=str(target), network_calls=0, model_calls=0, account_version=restored.ledger.account()['version'])
    Path(args.output).write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(value))


if __name__ == '__main__': main()
