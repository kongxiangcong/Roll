"""Local market commands for ingestion, freezing and replay."""

from datetime import datetime, timezone
import json
from pathlib import Path

from roll.v3.market import (
    DEFAULT_SOURCE_PRIORITY, RECONSTRUCTED_RESEARCH, USE_MODES,
    append_observations, freeze_snapshot, get_snapshot, read_snapshot,
)


def _sync(args, data_dir):
    from roll.v3.market_sources import DEFAULT_SYMBOLS, sync_daily_market

    return sync_daily_market(data_dir, symbols=args.symbols or DEFAULT_SYMBOLS,
                             start=args.start, end=args.end, indices=args.index,
                             refresh=args.refresh, warmup=args.warmup)


def _import(args, data_dir):
    with Path(args.file).open(encoding='utf-8') as incoming:
        rows = json.load(incoming, parse_float=str)
    return append_observations(data_dir, rows)


def _freeze(args, data_dir):
    scope = [dict(series=series, symbol=symbol, start=args.start, end=args.end)
             for series in args.series or ('daily_bar', 'daily_open') for symbol in args.symbols]
    return freeze_snapshot(data_dir, as_of=args.as_of or datetime.now(timezone.utc),
                           use_mode=args.use_mode, scope=scope,
                           source_priority=args.source_priority or DEFAULT_SOURCE_PRIORITY)


def _show(args, data_dir):
    return get_snapshot(data_dir, args.snapshot_id)


def _read(args, data_dir):
    return read_snapshot(data_dir, args.snapshot_id, series=args.series, symbol=args.symbol,
                         start=args.start, end=args.end, cutoff=args.cutoff, warmup=args.warmup)


def register(subparsers):
    market = subparsers.add_parser('market', help='行情同步与数据快照')
    action = market.add_subparsers(required=True)

    sync = action.add_parser('sync', help='同步扶摇原始日线和除权因子并冻结快照')
    sync.add_argument('symbols', nargs='*')
    sync.add_argument('--start', default='2020-01-02')
    sync.add_argument('--end')
    sync.add_argument('--index', action='append', default=[], help='将指定证券代码按指数同步')
    sync.add_argument('--refresh', action='store_true', help='重新查询已有行情以获取新修订')
    sync.add_argument('--warmup', type=int, default=0)
    sync.set_defaults(handler=_sync)

    ingest = action.add_parser('import', help='追加 JSON 格式的来源观察版本')
    ingest.add_argument('file')
    ingest.set_defaults(handler=_import)

    freeze = action.add_parser('freeze', help='冻结观察水位、输入范围及选源规则')
    freeze.add_argument('symbols', nargs='+')
    freeze.add_argument('--start', required=True)
    freeze.add_argument('--end', required=True)
    freeze.add_argument('--as-of')
    freeze.add_argument('--use-mode', choices=USE_MODES, default=RECONSTRUCTED_RESEARCH)
    freeze.add_argument('--series', action='append', default=None)
    freeze.add_argument('--source-priority', action='append')
    freeze.set_defaults(handler=_freeze)

    show = action.add_parser('show', help='查看冻结的快照引用')
    show.add_argument('snapshot_id')
    show.set_defaults(handler=_show)

    read = action.add_parser('read', help='离线读取快照并报告行情覆盖')
    read.add_argument('snapshot_id')
    read.add_argument('--series', default='daily_bar')
    read.add_argument('--symbol')
    read.add_argument('--start')
    read.add_argument('--end')
    read.add_argument('--cutoff')
    read.add_argument('--warmup', type=int, default=0)
    read.set_defaults(handler=_read)
