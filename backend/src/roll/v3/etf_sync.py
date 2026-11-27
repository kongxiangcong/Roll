"""Background workbench adapter for the local ETF market sync."""

from datetime import date, time, timedelta
import threading

from roll.market.calendar import extended_sessions, is_session, latest_session
from roll.v3.etf_basket import member_applies
from roll.v3.etf_basket_versions import FIXED_BASKET_VERSION, get_fixed_basket, resolve_comparison_basket
from roll.v3.etf_history import read_index_candles
from roll.v3.etf_sources import sync_etf_market
from roll.v3.market import LIVE_RUN, prepare_snapshot, utc_timestamp
from roll.v3.market_sources import sync_daily_market
from roll.v3.overview import BENCHMARK_SYMBOL
from roll.v3.storage import database, instant


def _requested_indexes(members):
    approved = {member['index_code']: member['index_symbol'] for member in get_fixed_basket()['members']}
    requested = {BENCHMARK_SYMBOL: BENCHMARK_SYMBOL}
    for member in members:
        code, symbol = member['index_code'], member['index_symbol']
        if symbol and approved.get(code) == symbol:
            requested[symbol] = symbol
        else:
            requested.setdefault(code, None)
    return requested


def _index_availability(data_dir, symbols, day):
    if not symbols:
        return set()
    with database(data_dir) as db:
        snapshot = prepare_snapshot(data_dir, as_of=instant(), use_mode=LIVE_RUN, db=db, scope=[
            {'series': 'daily_bar', 'symbol': symbol, 'start': day, 'end': day} for symbol in symbols
        ])
        return {symbol for symbol in symbols if read_index_candles(
            data_dir, snapshot, symbol, day, day, snapshot['as_of'], db,
        )}


def _sync_indexes(data_dir, requested, day, refresh):
    symbols = sorted({symbol for symbol in requested.values() if symbol})
    available = _index_availability(data_dir, symbols, day)
    pending = [symbol for symbol in symbols if refresh or symbol not in available]
    errors = {}
    appended = 0
    if pending:
        try:
            result = sync_daily_market(data_dir, symbols=pending, indices=pending, start=day, end=day,
                                       refresh=True)
            errors = {item['symbol']: item for item in result['failures']}
            appended = result['appended']
        except (OSError, ValueError) as error:
            errors = {symbol: {'error': str(error)} for symbol in pending}
        available = _index_availability(data_dir, symbols, day)

    failures = []
    for label, symbol in requested.items():
        if symbol in available:
            continue
        detail = errors.get(symbol, {})
        failures.append({
            'series': 'daily_bar', 'symbol': label, 'trade_date': day,
            'source': detail.get('source', 'fuyao' if symbol else 'unmapped'),
            'error': detail.get('error', '来源未返回可用日线' if symbol else '暂无已核验的日线同步映射'),
        })
    count = len(requested)
    fields = {'expected': count, 'completed': count, 'failed': len(failures), 'succeeded': count - len(failures)}
    return appended, failures, fields


class EtfSyncRunner:
    def __init__(self, data_dir):
        self._data_dir = data_dir
        self._lock = threading.Lock()
        self._state = {
            'status': 'idle', 'trade_date': None, 'basket_version': None, 'last_synced_at': None,
            'appended': 0, 'error': None, 'fields': {}, 'failures': [],
        }

    def status(self):
        with self._lock:
            return dict(self._state)

    def start(self, *, trade_date, basket_version=FIXED_BASKET_VERSION, refresh=False):
        day = date.fromisoformat(trade_date)
        now = instant()
        with database(self._data_dir) as db:
            last_closed, _ = latest_session(db, now.date() - timedelta(days=now.time() < time(15)))
            members = resolve_comparison_basket(db, cutoff=utc_timestamp(now), version=basket_version)['members']
            if day > last_closed or not is_session(day, extended_sessions(db)):
                raise ValueError('请选择已收盘的交易日')
        applicable = [member for member in members if member_applies(member, trade_date)]
        if not applicable:
            raise ValueError('该交易日没有适用的篮子基金')
        chosen = [member['symbol'] for member in applicable]
        requested_indexes = _requested_indexes(applicable)
        index_status = {'expected': len(requested_indexes), 'completed': 0, 'failed': 0, 'succeeded': 0}
        with self._lock:
            if self._state['status'] == 'running':
                return dict(self._state)
            self._state.update(status='running', trade_date=trade_date, basket_version=basket_version,
                               error=None, appended=0, fields={'daily_bar': index_status}, failures=[])
            started = dict(self._state)

        def progress(update):
            with self._lock:
                self._state.update({**update, 'fields': {**update['fields'], 'daily_bar': index_status}})

        def worker():
            try:
                result = sync_etf_market(self._data_dir, symbols=chosen, start=trade_date, end=trade_date,
                                         refresh=refresh, on_progress=progress)
                appended, index_failures, index_fields = _sync_indexes(
                    self._data_dir, requested_indexes, trade_date, refresh,
                )
                failures = [*result['failures'], *index_failures]
                fields = {**result['fields'], 'daily_bar': index_fields}
                succeeded = any(field['succeeded'] for field in fields.values())
                status = 'done' if not failures else 'partial' if succeeded else 'error'
                with self._lock:
                    self._state.update(
                        status=status, last_synced_at=utc_timestamp(None),
                        appended=result['appended'] + appended, fields=fields, failures=failures,
                        error=f'{len(failures)} 项未取得可用数据' if failures else None,
                    )
            except Exception as error:
                with self._lock:
                    self._state.update(status='error', error=str(error))

        threading.Thread(target=worker, name='roll-etf-sync', daemon=True).start()
        return started
