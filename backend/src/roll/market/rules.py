"""Small supported ordinary-A-share rule subset with archived original authority.

Calendar coverage is explicitly 2026 SSE/SZSE; nothing is inferred for BSE or
other years. Special stock statuses are separate facts, never name heuristics.
"""
import hashlib
import json
import os
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException

from roll.accounts.ledger import encode

# All adapted calendar/stage dates are in 2026, when Shanghai is UTC+08:00.
# Earlier DST years are outside this adapter rather than guessed with this offset.
SHANGHAI = timezone(timedelta(hours=8), 'Asia/Shanghai')
REFERENCE = Path(__file__).parent / 'reference'
BACKGROUND_INDICES = [
    {'instrument': 'SSE:000001', 'name': '上证指数', 'instrument_type': 'INDEX', 'purpose': 'BROAD_BACKGROUND', 'trading_capability': 'NONE'},
    {'instrument': 'SZSE:399001', 'name': '深证成指', 'instrument_type': 'INDEX', 'purpose': 'BROAD_BACKGROUND', 'trading_capability': 'NONE'},
    {'instrument': 'SZSE:399997', 'name': '中证白酒', 'instrument_type': 'INDEX', 'purpose': 'SECTOR_BACKGROUND',
     'trading_capability': 'NONE','related_instruments': ['SSE:600519'], 'basis_source': 'csi-399997-sector-basis',
     'basis_date': '2026-08-31', 'basis': '预固定一个相关行业指数；官网事实表成分列含600519，不作动态行业筛选'},
]
HOLIDAYS_2026 = [
    ('2026-01-01', '2026-01-03'), ('2026-02-15', '2026-02-23'),
    ('2026-04-04', '2026-04-06'), ('2026-05-01', '2026-05-05'),
    ('2026-06-19', '2026-06-21'), ('2026-09-25', '2026-09-27'),
    ('2026-10-01', '2026-10-07'),
]


class RuleCalendar:
    def __init__(self, ledger):
        self.directory = ledger.path.parent
        self.sources = {s['id']: s for s in json.loads((REFERENCE / 'sources.json').read_text(encoding='utf-8'))}
        with ledger.connection() as db:
            db.execute('CREATE TABLE IF NOT EXISTS market_sources(id TEXT PRIMARY KEY, source TEXT NOT NULL)')
            for source in self.sources.values():
                content = (REFERENCE / source['file']).read_bytes()
                if hashlib.sha256(content).hexdigest() != source['sha256']:
                    raise RuntimeError(f"市场规则原件指纹不一致: {source['id']}")
                relative = Path('raw') / (source['sha256'] + Path(source['file']).suffix)
                target = self.directory / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                if not target.exists():
                    temporary = target.with_name(target.name + '.' + str(uuid4()) + '.tmp')
                    with temporary.open('xb') as stream:
                        stream.write(content)
                        stream.flush()
                        os.fsync(stream.fileno())
                    os.replace(temporary, target)
                if hashlib.sha256(target.read_bytes()).hexdigest() != source['sha256']:
                    raise RuntimeError(f"市场规则归档损坏: {source['id']}")
                source['archive_path'] = relative.as_posix()
                db.execute('INSERT OR IGNORE INTO market_sources VALUES(?,?)', (source['id'], encode(source)))

    def source(self, source_id):
        if source_id not in self.sources:
            raise HTTPException(404, '规则来源不存在')
        return self.sources[source_id]

    def rule(self, exchange, board, instrument_type='STOCK', on=None):
        on = on or datetime.now(SHANGHAI).date()
        scopes = {('SSE', 'MAIN'): ('100', '100', '1000000', '1000000', '10'),
                  ('SSE', 'STAR'): ('200', '1', '100000', '50000', '20'),
                  ('SZSE', 'MAIN'): ('100', '100', '1000000', '1000000', '10'),
                  ('SZSE', 'CHINEXT'): ('100', '100', '300000', '150000', '20')}
        if (exchange, board) not in scopes or instrument_type != 'STOCK' or not date(2026, 7, 6) <= on <= date(2026, 12, 31):
            return {'exchange': exchange, 'board': board, 'instrument_type': instrument_type,
                    'implementation_status': 'UNSUPPORTED', 'source': None,
                    'reason': '未取得/适配该市场、板块、类型或日期范围的有效规则'}
        minimum, step, maximum, market_max, limit = scopes[(exchange, board)]
        return {'rule_id': f'{exchange}-{board}-A-2026-07-06', 'exchange': exchange, 'board': board,
                'instrument_type': instrument_type, 'implementation_status': 'ADAPTED',
                'effective_from': '2026-07-06', 'effective_to': None, 'adapted_date_range': ['2026-07-06', '2026-12-31'],
                'source': self.source(f'{exchange.lower()}-rules-text-2026'),
                'provisions': ['3.1.4', '3.3.8', '3.3.9', '3.3.11', '3.3.13'] +
                              (['6.6', '6.7'] if board == 'STAR' else []),
                'buy_minimum': minimum, 'buy_increment': step, 'limit_order_maximum': maximum,
                'market_order_maximum': market_max, 'sell_odd_lot': 'ENTIRE_REMAINDER_BELOW_MINIMUM',
                'price_tick_yuan': '0.01', 'normal_price_limit_percent': limit,
                'risk_warning_price_limit_percent': limit,
                'resale': 'NEXT_TRADING_DAY', 'price_limit_rounding': 'ROUND_HALF_UP',
                'required_status_evidence': ['suspension', 'risk_warning', 'listing_stage', 'ex_rights'],
                'unsupported_uses': ['SPECIAL_STOCK_EXECUTION', 'AUCTION_DETAIL_REPLAY', 'FEE_ESTIMATION'],
                'fees': {'state': 'UNKNOWN', 'reason': '费用须来自实际券商/税费依据，未知不作零费'},
                'applicability': '普通人民币现金账户A股基本规则；状态未知不证明该证券当日可执行'}

    def calendar(self, exchange: str, on: date, at: datetime | None = None):
        if at is not None:
            if at.tzinfo is None:
                raise HTTPException(422, 'at 需要带时区时间')
            at = at.astimezone(SHANGHAI)
            if at.date() != on:
                raise HTTPException(422, 'at 的上海日期必须与 date 一致')
        if exchange not in {'SSE', 'SZSE'} or on.year != 2026:
            return {'exchange': exchange, 'date': on.isoformat(), 'timezone': 'Asia/Shanghai',
                    'is_trading_day': None, 'phase': 'UNKNOWN', 'coverage': 'UNKNOWN', 'source': None,
                    'reason': '该交易所/年份日历尚未取得与适配，不按工作日推测'}
        holiday = any(date.fromisoformat(start) <= on <= date.fromisoformat(end) for start, end in HOLIDAYS_2026)
        trading = on.weekday() < 5 and not holiday  # both conditions are backed by exchange documents
        result = {'exchange': exchange, 'date': on.isoformat(), 'timezone': 'Asia/Shanghai',
                  'is_trading_day': trading, 'phase': 'TRADING_DAY' if trading else 'CLOSED',
                  'coverage': 'VERIFIED_ANNUAL_CALENDAR', 'calendar_version': f'{exchange}-2026',
                  'source': self.source(f'{exchange.lower()}-calendar-2026'),
                  'rules_source': self.source(f'{exchange.lower()}-rules-text-2026'),
                  'reason': 'HOLIDAY' if holiday else ('WEEKEND' if not trading else None),
                  'special_closure_check': '未接入盘中临时停市实时源；证券停牌另作事实，不等同交易所休市'}
        if trading and at is not None:
            clock = at.time().replace(tzinfo=None)
            boundaries = [(time(9,15), 'PRE_OPEN'), (time(9,25), 'OPENING_AUCTION'),
                          (time(9,30), 'PRE_CONTINUOUS'), (time(11,30), 'CONTINUOUS'),
                          (time(13), 'LUNCH_BREAK'), (time(14,57), 'CONTINUOUS'),
                          (time(15), 'CLOSING_AUCTION'), (time(15,5), 'POST_CLOSE_PREP'),
                          (time(15,30), 'FIXED_PRICE')]
            # The 2026 stage schedule is not projected back onto earlier 2026 rules.
            if on < date(2026, 7, 6):
                result['phase'] = 'UNKNOWN'
                result['reason'] = '日历已取得，但该日期的时段规则未适配'
            else:
                result['phase'] = next((phase for boundary, phase in boundaries if clock < boundary), 'AFTER_CLOSE')
        return result

    def next_trading_day(self, exchange: str, on: date):
        for offset in range(1, 15):
            candidate = on + timedelta(days=offset)
            status = self.calendar(exchange, candidate)['is_trading_day']
            if status is None:
                return None
            if status:
                return candidate.isoformat()
        return None
