"""CLI entry points for the ETF observation and replay path."""

import json
from pathlib import Path

from roll.v3.etf import freeze_etf_snapshot, read_etf_day
from roll.v3.etf_observations import ETF_SERIES
from roll.v3.market import LIVE_RUN, USE_MODES, append_observations


def _sync(args, data_dir):
    from roll.v3.etf_sources import sync_etf_market

    return sync_etf_market(data_dir, symbols=args.symbols, start=args.start, end=args.end,
                           refresh=args.refresh)


def _import(args, data_dir):
    with Path(args.file).open(encoding='utf-8') as incoming:
        rows = json.load(incoming, parse_float=str)
    if not isinstance(rows, list) or any(not isinstance(row, dict) or row.get('series') not in ETF_SERIES for row in rows):
        raise ValueError('ETF 导入需要由份额、单位净值或份额折算观察项组成的 JSON 数组')
    return append_observations(data_dir, rows)


def _freeze(args, data_dir):
    return freeze_etf_snapshot(data_dir, symbols=args.symbols, start=args.start, end=args.end,
                               as_of=args.as_of, use_mode=args.use_mode)


def _read(args, data_dir):
    return read_etf_day(data_dir, args.snapshot_id, symbol=args.symbol, trade_date=args.date, cutoff=args.cutoff)


def register_etf(subparsers):
    etf = subparsers.add_parser('etf', help='ETF 日终份额、单位净值与净申赎估算')
    commands = etf.add_subparsers(required=True)

    sync = commands.add_parser('sync', help='同步交易所份额及扶摇单位净值，冻结可用结果')
    sync.add_argument('symbols', nargs='+', help='如 510300.SH 或 159915.SZ')
    sync.add_argument('--start', required=True)
    sync.add_argument('--end', required=True)
    sync.add_argument('--refresh', action='store_true', help='复查已有观察项以发现更正')
    sync.set_defaults(handler=_sync)

    ingest = commands.add_parser(
        'import', help='追加 ETF 观察项 JSON',
        description='导入 market 观察项数组。series 为 etf_shares/etf_nav/etf_split，'
        'unit 分别为份、元/份、新份/旧份。payload.value 为十进制原值换算后的字符串，'
        'payload.verified 表示已核对来源、所属日和单位。'
        '用 source_ref、available_evidence、received_at 保存定位、依据和实际取得时刻，'
        '在 payload 中保留原始日期、数值和单位。'
    )
    ingest.add_argument('file')
    ingest.set_defaults(handler=_import)

    freeze = commands.add_parser('freeze', help='为指定交易日区间冻结 ETF 输入')
    freeze.add_argument('symbols', nargs='+')
    freeze.add_argument('--start', required=True)
    freeze.add_argument('--end', required=True)
    freeze.add_argument('--as-of')
    freeze.add_argument('--use-mode', choices=USE_MODES, default=LIVE_RUN)
    freeze.set_defaults(handler=_freeze)

    read = commands.add_parser('read', help='凭快照离线复算单日净申赎')
    read.add_argument('snapshot_id')
    read.add_argument('symbol')
    read.add_argument('--date', required=True)
    read.add_argument('--cutoff')
    read.set_defaults(handler=_read)
