"""Collect once into Roll's own PIT database; intended for a daily heartbeat."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'backend/src'))
from roll.app import create_app
from roll.market.directory import WatchCommand, IdentityCommand
from roll.research.prospective import CollectionCommand
from roll.accounts.ledger import now


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--data-dir', type=Path, default=ROOT/'.roll-data/pit')
    parser.add_argument('--instrument', default='SSE:600362', choices=['SSE:600362'])
    args = parser.parse_args()
    app = create_app(args.data_dir.resolve())
    market = app.state.market
    listing = market.listing()
    if not any(m['instrument'] == args.instrument for m in listing['members']):
        market.watch(WatchCommand(operation='ADD', instrument=args.instrument, expected_list_version=listing['version']))
    listing = market.listing()
    member = next(m for m in listing['members'] if m['instrument'] == args.instrument)
    if member['identity']['instrument_type'] != 'STOCK':
        market.identify(IdentityCommand(instrument=args.instrument, exchange='SSE', board='MAIN', instrument_type='STOCK',
            name='江西铜业', effective_at=now(), basis='延续ticket19明确单证券SSE:600362采集范围；仅当前身份，不回填历史状态'))
    plan = app.state.prospective.start(CollectionCommand(instrument=args.instrument,
        basis='2026-10-10用户决定从今开始自建PIT数据库，停止追寻旧PIT；数据与验证满足前不启用'))
    batch = app.state.prospective.collect(plan['plan_id'])
    readiness = app.state.prospective.readiness(plan['plan_id'])
    integrity = app.state.collection_sources.integrity()
    backup = app.state.backups.create(reason='PROSPECTIVE_COLLECTION') if integrity['consistent'] else None
    print(json.dumps({'data_dir': str(args.data_dir.resolve()), 'plan': plan, 'batch': batch,
                      'readiness': readiness, 'sources': app.state.collection_sources.listing(),
                      'integrity': integrity, 'backup': backup}, ensure_ascii=False, indent=2))
    if not integrity['consistent']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
