from datetime import date, datetime, timezone, timedelta
import httpx

from roll.market.daily import read_bars, market_status, sync_market


def test_sync_history_reanchors_and_survives_partial_failure(tmp_path, monkeypatch):
    monkeypatch.setenv("FUYAO_API_KEY", "test")
    calls = []
    failed = False

    def millis(day):
        return int(datetime.fromisoformat(day).replace(
            tzinfo=timezone(timedelta(hours=8))).timestamp() * 1000)

    def provider(request):
        symbol = request.url.params["thscode"]
        args = request.url.params
        calls.append((request.url.path, dict(args)))
        if failed and symbol == "600362.SH":
            return httpx.Response(503)
        if "corporate-actions" in request.url.path:
            items = [{"ex_date_ms": millis("2025-07-22"), "ticker": "600362",
                      "dividend_per_share": 0.7, "per_share_bonus": 0}]
            data = {"thscode": symbol, "item": items}
        else:
            data = {"thscode": symbol, "item": []}
            if "adjust" in args:
                data["adjust"] = args["adjust"]
            for day, raw in [("2025-07-21", 21.70), ("2025-07-22", 22.00)]:
                if not int(args["start"]) <= millis(day) <= int(args["end"]):
                    continue
                value = 21 if args.get("adjust") == "forward" and day.endswith("21") else raw
                data["item"].append({"date_ms": millis(day), **{
                    k + "_price": str(value) for k in ("open", "close", "high", "low")}})
        return httpx.Response(200, json={"code": 0, "data": data})

    transport = httpx.MockTransport(provider)
    with httpx.Client(transport=transport) as client:
        sync_market(tmp_path, "2025-07-21", "2025-07-21", client=client)
        sync_market(tmp_path, None, "2025-07-22", client=client)
        assert all("adjust" not in args for path, args in calls if "index" in path)
        assert [float(r["open"]) for r in read_bars(tmp_path, "600362.SH")] == [21.7, 22]
        assert [float(r["open"]) for r in read_bars(
            tmp_path, "600362.SH", adjustment="forward")] == [21, 22]
        assert [float(r["close"]) for r in read_bars(
            tmp_path, "600362.SH", adjustment="backward")] == [21.7, 22.7]
        failed = True
        status = sync_market(tmp_path, None, "2025-07-22", client=client)
    stock = next(row for row in status if row["symbol"] == "600362.SH")
    assert stock["error"] and stock["last_success_at"] and stock["count"] == 2
    assert stock["last_date"] == "2025-07-22"
    assert next(row for row in market_status(tmp_path) if row["symbol"] == "000300.SH")["error"] is None
