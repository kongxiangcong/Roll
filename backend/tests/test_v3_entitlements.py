import io
import json

from roll.v3.cli import run


SYMBOL = "600362.SH"
RECORD_DATE = "2025-07-21"
EX_DATE = "2025-07-22"
POST_DATE = "2025-07-24"
BOOK = "simulation"


def cli(tmp_path, *args):
    return run(args, data_dir=tmp_path)


def input_cli(tmp_path, monkeypatch, *args, payload):
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
    return cli(tmp_path, *args)


def seed(tmp_path, monkeypatch, *, book=BOOK, cash_per_share="1", shares_per_share="0", ex_price="9"):
    input_cli(tmp_path, monkeypatch, "account", "init", "--book-id", book, payload={
        "cash": "0",
        "available_cash": "0",
        "effective_at": f"{RECORD_DATE}T15:00:00+08:00",
        "known_at": f"{RECORD_DATE}T15:00:00+08:00",
        "lots": [{"lot_id": "registered-lot", "symbol": SYMBOL, "quantity": 100, "known_sellable": 100}],
    })
    action = {
        "series": "corporate_action",
        "item_id": "distribution",
        "trade_date": EX_DATE,
        "payload": {
            "record_date": RECORD_DATE,
            "ex_date": EX_DATE,
            "cash_per_share": cash_per_share,
            "shares_per_share": shares_per_share,
            "payment_date": POST_DATE,
            "listing_date": POST_DATE,
        },
    }
    bars = [
        {"series": "daily_bar", "trade_date": day, "payload": {"close": price}}
        for day, price in ((RECORD_DATE, "10"), (EX_DATE, ex_price), (POST_DATE, ex_price))
    ]
    observations = tmp_path / "observations.json"
    observations.write_text(json.dumps([
        {
            **row, "symbol": SYMBOL, "source": "exercise",
            "available_at": f"{row['trade_date']}T15:05:00+08:00" if row in bars else f"{RECORD_DATE}T15:00:00+08:00",
            "available_evidence": "controlled exercise",
            "received_at": f"{row['trade_date']}T15:05:00+08:00" if row in bars else f"{RECORD_DATE}T15:00:00+08:00",
        }
        for row in [action, *bars]
    ]))
    cli(tmp_path, "market", "import", str(observations))
    frozen = cli(tmp_path, "market", "freeze", SYMBOL, "--start", RECORD_DATE, "--end", POST_DATE,
                 "--as-of", f"{POST_DATE}T16:00:00+08:00", "--series", "daily_bar", "--series", "corporate_action")
    return frozen["snapshot_id"]


def close(tmp_path, day, snapshot_id, *, book=BOOK, simulated=True):
    mode = ["--simulated"] if simulated else []
    cli(tmp_path, "entitlements", "settle", "--book-id", book, "--snapshot-id", snapshot_id,
        "--as-of", f"{day}T16:00:00+08:00", *mode)
    return cli(tmp_path, "entitlements", "value", "--book-id", book, "--snapshot-id", snapshot_id,
               "--as-of", f"{day}T16:00:00+08:00")


def test_cash_dividend_preserves_nav_until_payment_and_credits_cash_once(tmp_path, monkeypatch):
    snapshot_id = seed(tmp_path, monkeypatch)
    pre_ex = close(tmp_path, RECORD_DATE, snapshot_id)
    pending = close(tmp_path, EX_DATE, snapshot_id)
    paid = close(tmp_path, POST_DATE, snapshot_id)

    assert pre_ex["valuation"]["nav"] == "1000"
    assert pending["valuation"] == {"cash": "0", "position_value": "900", "receivable_value": "100", "nav": "1000"}
    assert pending["account"]["available_cash"] == "0"
    assert pending["account"]["receivables"][0]["source_lot_id"] == "registered-lot"
    assert paid["valuation"] == {"cash": "100", "position_value": "900", "receivable_value": "0", "nav": "1000"}
    assert paid["account"]["available_cash"] == "100"
    assert not paid["account"]["receivables"]
    assert close(tmp_path, POST_DATE, snapshot_id) == paid


def test_bonus_shares_enter_sellable_holdings_on_listing(tmp_path, monkeypatch):
    snapshot_id = seed(tmp_path, monkeypatch, cash_per_share="0", shares_per_share="1", ex_price="5")
    pending = close(tmp_path, EX_DATE, snapshot_id)
    listed = close(tmp_path, POST_DATE, snapshot_id)

    assert pending["valuation"] == {"cash": "0", "position_value": "500", "receivable_value": "500", "nav": "1000"}
    assert pending["account"]["known_sellable"] == {SYMBOL: 100}
    assert pending["account"]["receivables"][0]["quantity"] == 100
    assert listed["valuation"] == {"cash": "0", "position_value": "1000", "receivable_value": "0", "nav": "1000"}
    assert listed["account"]["known_sellable"] == {SYMBOL: 200}
    assert listed["account"]["lots"][1]["source_lot_id"] == "registered-lot"
    assert close(tmp_path, POST_DATE, snapshot_id) == listed


def test_cash_due_later_that_day_cannot_fund_opening_orders(tmp_path, monkeypatch):
    snapshot_id = seed(tmp_path, monkeypatch)
    opening = cli(tmp_path, "entitlements", "settle", "--book-id", BOOK, "--snapshot-id", snapshot_id,
                  "--as-of", f"{POST_DATE}T09:30:00+08:00", "--simulated")["account"]
    assert opening["available_cash"] == "0"
    assert opening["receivables"][0]["amount"] == "100"


def test_broker_receipt_posted_before_ex_date_also_clears_the_entitlement(tmp_path, monkeypatch):
    snapshot_id = seed(tmp_path, monkeypatch, book="real")
    input_cli(tmp_path, monkeypatch, "entitlements", "confirm", payload={
        "symbol": SYMBOL,
        "action_id": "distribution",
        "kind": "cash",
        "broker_event_id": "broker-credit",
        "effective_at": f"{RECORD_DATE}T20:00:00+08:00",
        "known_at": f"{RECORD_DATE}T20:00:00+08:00",
        "actual": "98",
    })
    book = close(tmp_path, EX_DATE, snapshot_id, book="real", simulated=False)
    assert book["valuation"] == {"cash": "98", "position_value": "900", "receivable_value": "0", "nav": "998"}
