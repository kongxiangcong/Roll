"""Engineering fixtures only; real acceptance is recorded separately."""
import copy
import hashlib
import threading
from pathlib import Path

import pytest
from roll.accounts.ledger import Ledger, encode
from roll.research.exploratory import backtest
from roll.runtime.assistance import Assistance, AssistanceCommand
from roll.agents.assistance_runtime import publish


def prices():
    from datetime import date, timedelta
    return [{'date': (date(2026, 1, 1)+timedelta(days=i)).isoformat(), 'code': 'sh.600362',
             'open': str(10+i*.1), 'close': str(10+i*.1), 'high': str(11+i*.1), 'low': str(9+i*.1),
             'preclose': str(10+(i-1)*.1 if i else 10), 'volume': '10000000', 'adjustflag': '3', 'isST': '0', 'tradestatus': '1'} for i in range(45)]


def test_next_open_cash_conservation_and_same_cost_benchmark():
    r = backtest(prices())
    assert r['strategy'] == r['buy_hold']
    t = r['strategy']['trades'][0]
    assert t['signal_date'] < t['date']
    assert t['quantity'] % 100 == 0
    assert t['cash_after'] == round(100000-t['quantity']*t['price']-t['fee'], 2)
    assert t['fee'] > 0 and t['price'] > 12
    assert all(n['cash'] >= 0 for n in r['strategy']['nav'])


def test_future_price_does_not_change_previous_trades():
    rows = prices()
    before = backtest(rows)['strategy']
    rows[-1].update(close='12', low='11')
    after = backtest(rows)['strategy']
    assert before['trades'] == after['trades']
    assert before['nav'][:-1] == after['nav'][:-1]


def test_halts_limits_and_no_same_day_sale():
    rows = prices()
    rows[20]['tradestatus'] = '0'
    rows[21].update(open='13.31', high='13.5')  # >= 10% of prev close 12
    r = backtest(rows)['strategy']
    assert r['no_fills'][0]['reason'] == 'SUSPENDED_OR_ZERO_VOLUME'
    assert r['no_fills'][1]['reason'] == 'LIMIT_OR_ONE_PRICE_NO_FILL'
    assert r['trades'][0]['date'] == rows[22]['date']
    assert len({t['date'] for t in r['trades']}) == len(r['trades'])


def test_action_window_is_cut_or_refused_not_silent_dividend_loss():
    rows = prices()
    rows[5]['preclose'] = '9'
    assert len(backtest(rows)['excluded_before_action_free_tail']) == 5
    rows[40]['preclose'] = '9'
    with pytest.raises(ValueError, match='INSUFFICIENT_ACTION_FREE_TAIL'):
        backtest(rows)


@pytest.mark.parametrize('field,value', [('open', 'nan'), ('adjustflag', '2'), ('isST', '1')])
def test_critical_data_rejected(field, value):
    rows = prices()
    rows[2][field] = value
    with pytest.raises(ValueError):
        backtest(rows)


def test_unknown_model_reference_cannot_publish():
    material = {'sources': [{'source_id': 'sh.600362'}]}
    output = {'material_sha256': hashlib.sha256(encode(material).encode()).hexdigest(), 'bias': '中性', 'summary': 'fixture',
              'evidence': [{'source_id': 'invented', 'reason': 'fixture'}], 'counterevidence': ['fixture'],
              'change_conditions': ['fixture'], 'limitations': ['fixture']}
    with pytest.raises(ValueError, match='ASSESSMENT_UNKNOWN_CITATION'):
        publish(None, {}, material, {}, encode(output))


def test_failure_keeps_results_and_restart_reflection(tmp_path, monkeypatch):
    service = Assistance(Ledger(tmp_path))
    def source(run, symbol, cancel):
        if symbol != 'sh.600362':
            raise ValueError('TEST_NONCRITICAL_SOURCE_FAILURE')
        return {'source_id': symbol, 'rows': prices(), 'last_date': '2026-02-14'}
    monkeypatch.setattr(service, 'source', source)
    monkeypatch.delenv('ROLL_CODEX_AUTH_FILE', raising=False)
    run = {'run_id': 'fixture', 'sources': [], 'gaps': [], 'as_of': '2026-02-14', 'status': 'RUNNING'}
    service.execute(run, threading.Event())
    assert run['status'] == 'PARTIAL' and run['sources']
    assert 'backtest' not in run and 'assessment' not in run
    service.reflect('fixture', 'fixture acceptance reflection')
    restored = Assistance(Ledger(tmp_path)).get('fixture')
    assert restored['reflections'][0]['text'] == 'fixture acceptance reflection'
    assert restored['error']['code'] == 'CODEX_AUTH_NOT_CONFIGURED'


def test_start_commits_before_return_and_rejects_concurrent_job(tmp_path, monkeypatch):
    from fastapi import HTTPException
    monkeypatch.setattr(threading.Thread, 'start', lambda self: None)
    service = Assistance(Ledger(tmp_path))
    created = service.start(AssistanceCommand())
    assert service.get(created['run_id'])['status'] == 'RUNNING'
    with pytest.raises(HTTPException) as error:
        Assistance(Ledger(tmp_path)).start(AssistanceCommand())
    assert error.value.status_code == 409


def test_restart_marks_dead_job_interrupted_and_keeps_sources(tmp_path):
    service = Assistance(Ledger(tmp_path))
    service.save({'run_id': 'dead', 'status': 'RUNNING', 'sources': ['fixture'], 'host_owner': {'pid': 0, 'creation_ticks': 1}})
    restored = Assistance(Ledger(tmp_path)).get('dead')
    assert restored['status'] == 'INTERRUPTED' and restored['sources'] == ['fixture']
