"""Background workbench adapter for the local ETF market sync."""

from datetime import date, time, timedelta
import threading

from roll.market.calendar import is_session, latest_session
from roll.v3.etf_basket import FIXED_BASKET_VERSION, get_fixed_basket, member_applies
from roll.v3.etf_sources import sync_etf_market
from roll.v3.market import utc_timestamp
from roll.v3.storage import database, instant


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
        if day > last_closed or not is_session(day):
            raise ValueError('请选择已收盘的交易日')
        members = get_fixed_basket(basket_version)['members']
        chosen = [member['symbol'] for member in members if member_applies(member, trade_date)]
        if not chosen:
            raise ValueError('该交易日没有适用的篮子基金')
        with self._lock:
            if self._state['status'] == 'running':
                return dict(self._state)
            self._state.update(status='running', trade_date=trade_date, basket_version=basket_version,
                               error=None, appended=0, fields={}, failures=[])
            started = dict(self._state)

        def progress(update):
            with self._lock:
                self._state.update(update)

        def worker():
            try:
                result = sync_etf_market(self._data_dir, symbols=chosen, start=trade_date, end=trade_date,
                                         refresh=refresh, on_progress=progress)
                failures = result['failures']
                succeeded = any(field['succeeded'] for field in result['fields'].values())
                status = 'done' if not failures else 'partial' if succeeded else 'error'
                with self._lock:
                    self._state.update(
                        status=status, last_synced_at=utc_timestamp(None),
                        error=f'{len(failures)} 项未取得可用数据' if failures else None,
                    )
            except Exception as error:
                with self._lock:
                    self._state.update(status='error', error=str(error))

        threading.Thread(target=worker, name='roll-etf-sync', daemon=True).start()
        return started
