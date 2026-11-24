from decimal import Decimal
import pytest
from roll.risk import position_exposure


@pytest.mark.parametrize("value,expected", [(5500,None), (6000,None), (6500,"500")])
def test_balanced_cap_applies_only_to_excess(value, expected):
    result = position_exposure(Decimal(10000-value), [Decimal(value)], Decimal("0.60"))
    assert result["overage_amount"] == expected
    assert result["overage_percentage_points"] == ("5" if expected else None)


def test_real_account_lots_and_same_day_frozen_risk(tmp_path):
    import json
    from datetime import date,timedelta
    from roll.accounts.ledger import Ledger,DraftCommand,ConfirmCommand
    from roll.market.calendar import is_session
    from roll.market.daily import initialize_market
    from roll.market.inputs import initialize_inputs
    from roll.reports import freeze_report, read_report
    from roll.risk import risk_at
    ledger = Ledger(tmp_path)
    def post(kind, version, payload):
        draft = ledger.draft(DraftCommand(kind=kind,expected_account_version=version,payload=payload))
        ledger.confirm(ConfirmCommand(draft_id=draft["draft_id"],idempotency_key=kind+str(version)))
    post("BASELINE",0,{"effective_at":"2025-06-03T10:00:00+08:00","source":"基线",
         "cash_balance":"5000","positions":[],"permission_profile":[],"broker_available":None,
         "broker_frozen":None,"withdrawable":None})
    for version,day,quantity in [(1,"2025-07-31","100"),(2,"2025-08-01","200")]:
        post("FILL",version,{"effective_at":day+"T10:00:00+08:00","source":"交割单",
             "record_id":str(version),"instrument":"SSE:600362","direction":"BUY","quantity":quantity,
             "price":"10","behavior_context":"OFFLINE","fee":{"status":"KNOWN","amount":"0",
             "reserve_amount":None,"basis":"成交单"},"fill_id":str(version),"order_id":None,"broker_available_after":None})
    with ledger.connection() as db:
        initialize_market(db)
        initialize_inputs(db)
        db.execute("CREATE TABLE watchlist_config(id INTEGER PRIMARY KEY,items TEXT)")
        db.execute("INSERT INTO watchlist_config VALUES(1,?)", (json.dumps([{"code":"600362.SH","name":"江西铜业",
                   "sector_etf":"512400.SH","max_position_pct":0.20,"atr_stop_multiplier":2.2}]),))
        days = []
        d = date(2025,8,1)
        while len(days)<21:
            if is_session(d): days.append(str(d))
            d -= timedelta(days=1)
        for day in days:
            close = "10" if day==days[0] else "12"
            db.execute("INSERT INTO daily_bars VALUES(?,?,?,?,?,?)",("600362.SH",day,close,close,close,close))
            db.execute("INSERT INTO daily_bars VALUES(?,?,?,?,?,?)",("000300.SH",day,"100","100","100","100"))
            db.execute("INSERT INTO market_inputs VALUES('etf_bars','512400.SH',?,?)",
                       (day,json.dumps({"close":"2" if day==days[0] else "1"})))
    day="2025-08-01"
    risk=risk_at(tmp_path,day)
    card,=risk["cards"]
    assert risk["portfolio"]["position_fraction"] == "0.6" and risk["portfolio"]["position_cap"] is None
    assert card["single_overage"]=="2000" and card["reference_shares"]==100
    assert card["sellable_quantity"]=="100" and card["below_low20"] and card["atr_stop_breached"]
    assert card["sector_excess_return20"]=="1" and card["highest_close_since_entry"]=="12"
    assert card["account_confirmed_at"] and card["trade_date"]==day and not card["price_stale"]
    assert freeze_report(tmp_path,day)["risk"]==risk
    with ledger.connection() as db:
        db.execute("UPDATE daily_bars SET close_raw='11' WHERE symbol='600362.SH' AND trade_date=?",(day,))
    assert risk_at(tmp_path,day)["cards"][0]["close"]=="11"
    assert read_report(tmp_path,day)["risk"]==risk
