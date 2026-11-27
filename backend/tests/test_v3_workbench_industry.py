"""Read the industry theme through the workbench after importing its source observations."""

import json
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from roll.v3.cli import run
from roll.v3.web import create_app


CAPTURE = Path(__file__).parent / "fixtures" / "market_industry_2026_11_26.json"
CLOCK = "2026-11-27T18:00:00+08:00"


def _import_rows(tmp_path, rows):
    incoming = tmp_path / "observations.json"
    incoming.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    run(("market", "import", str(incoming)), data_dir=tmp_path)


def test_industry_workbench_compares_published_level_one_index_with_the_same_session_benchmark(tmp_path):
    assert run(("market", "import", str(CAPTURE)), data_dir=tmp_path)["appended"] == 7
    assert run(("market", "import", str(CAPTURE)), data_dir=tmp_path)["appended"] == 0

    with TestClient(create_app(tmp_path)) as browser:
        response = browser.get("/api/market/industry", params={"trade_date": "2026-11-26", "as_of": CLOCK})
    assert response.status_code == 200, response.text
    report = response.json()
    assert report["trade_date"] == "2026-11-26"
    assert report["benchmark"]["symbol"] == "000300.SH"
    assert report["benchmark"]["bar"]["change_pct"] == pytest.approx(0.0592575111)

    group, = report["groups"]
    assert group["classification"] == "申万行业分类（2021版）"
    assert group["coverage"] == {"classified": 1, "expected": 31, "priced": 1, "comparable": 1}
    row, = group["rows"]
    assert (row["symbol"], row["name"], row["level"]) == ("801050.SI", "有色金属", 1)
    assert row["identity"]["effective_start"] == "2021-12-13"
    assert row["identity"]["source_ref"].startswith("https://www.swsresearch.com/")
    assert row["bar"]["trade_date"] == "2026-11-26"
    assert row["bar"]["source"] == "shenwan"
    assert row["bar"]["change_pct"] == pytest.approx(1.7452252506)
    assert row["relative_percentage_points"] == pytest.approx(1.6859677395)
    assert row["bar"]["volume"] == "40.25708616"
    assert row["bar"]["amount"] == "605.18668354"
    prior, latest = row["trend"][-2:]
    assert (prior["trade_date"], prior["industry"]["close"], prior["benchmark"]["close"]) == (
        "2026-11-25", "5544.27", "3898.24",
    )
    assert latest["relative_percentage_points"] == pytest.approx(1.6859677395)


def test_industry_workbench_leaves_only_affected_metrics_blank_when_dates_or_inputs_are_missing(tmp_path):
    identity = json.loads(CAPTURE.read_text(encoding="utf-8"))[0]
    industry, benchmark = "801050.SI", "000300.SH"
    rows = [identity]
    for symbol, day, close, payload in (
        (industry, "2026-11-20", 100, {}),
        (benchmark, "2026-11-20", 100, {}),
        (industry, "2026-11-23", 102, {"volume": 0, "amount": None}),
        (benchmark, "2026-11-23", 99, {}),
        (industry, "2026-11-24", 104, {"volume": None, "amount": 1234}),
        (industry, "2026-11-26", 105, {"volume": 50, "amount": 2500}),
        (benchmark, "2026-11-25", 97, {}),
        (benchmark, "2026-11-26", 98, {}),
    ):
        rows.append({
            "series": "daily_bar", "symbol": symbol, "trade_date": day,
            "source": "fixture", "received_at": f"{day}T15:05:00+08:00", "payload": {"close": close, **payload},
        })
    _import_rows(tmp_path, rows)

    with TestClient(create_app(tmp_path)) as browser:
        response = browser.get("/api/market/industry", params={"trade_date": "2026-11-26", "as_of": CLOCK})
    assert response.status_code == 200, response.text
    group, = response.json()["groups"]
    assert group["coverage"] == {"classified": 1, "expected": 31, "priced": 1, "comparable": 0}
    assert group["last_comparable_trade_date"] == "2026-11-23"
    row, = group["rows"]
    _, aligned, missing_benchmark, missing_industry, missing_prior = row["trend"]
    assert aligned["relative_percentage_points"] == 3
    assert aligned["industry"]["volume"] == "0"
    assert aligned["industry"]["amount"] is None
    assert missing_benchmark["relative_percentage_points"] is None
    assert missing_benchmark["benchmark"] is None
    assert missing_benchmark["industry"]["change_pct"] == pytest.approx(1.9607843)
    assert missing_benchmark["industry"]["volume"] is None
    assert missing_benchmark["industry"]["amount"] == "1234"
    assert missing_industry["industry"] is None
    assert missing_prior["industry"]["change_pct"] is None
    assert missing_prior["industry"]["amount"] == "2500"
    assert missing_prior["benchmark"]["change_pct"] == pytest.approx(1.0309278)
    assert missing_prior["relative_percentage_points"] is None


def test_industry_workbench_limits_the_list_to_effective_level_one_classifications(tmp_path):
    with TestClient(create_app(tmp_path)) as browser:
        empty = browser.get("/api/market/industry", params={"as_of": CLOCK}).json()
        assert empty["trade_date"] is None
        assert empty["groups"] == []

    rows = json.loads(CAPTURE.read_text(encoding="utf-8"))
    identity = rows[0]
    rows.extend((
        {**identity, "symbol": "801055.SI", "payload": {**identity["payload"], "level": 2, "name": "工业金属"}},
        {**identity, "symbol": "801010.SI", "payload": {**identity["payload"], "effective_end": "2026-11-25"}},
        {**identity, "symbol": "801030.SI", "trade_date": "2026-11-27",
         "payload": {**identity["payload"], "effective_start": "2026-11-27"}},
    ))
    _import_rows(tmp_path, rows)

    with TestClient(create_app(tmp_path)) as browser:
        response = browser.get("/api/market/industry", params={"trade_date": "2026-11-26", "as_of": CLOCK})
        before_version = browser.get("/api/market/industry", params={"trade_date": "2021-12-10", "as_of": CLOCK})
    assert response.status_code == 200, response.text
    assert [row["symbol"] for group in response.json()["groups"] for row in group["rows"]] == ["801050.SI"]
    assert before_version.json()["groups"] == []
