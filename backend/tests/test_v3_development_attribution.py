from roll.v3.storage import sessions
from test_v3_development_inputs import PRESET, command, load_snapshot
from test_v3_development_replay import _quotes


def _receipt(data_dir, rows):
    snapshot = load_snapshot(data_dir, rows)
    attempt = command(data_dir, "research", "task", "development", "--preset", PRESET, "--snapshot", snapshot)
    return command(data_dir, "research", "task", "development-receipt", attempt["task_id"])


def test_receipt_links_a_filtered_signal_to_the_fill_and_later_candidate_difference(tmp_path):
    start = list(sessions("2023-01-03", "2023-12-29"))[-75]
    days, rows = _quotes(start)

    attribution = _receipt(tmp_path, rows)["attribution"]

    direct, diverged = attribution["signals"][:2]
    assert direct["ref"] == f"signal:{days[59]}"
    assert direct["stock"]["signal"] == "long"
    assert direct["market"]["close"] == direct["market"]["average"] == "100"
    assert direct["direct_market_block"] and not direct["candidate_difference"]
    assert direct["paths"]["e1"]["action"] == "HOLD"
    assert direct["paths"]["e1"]["gate_reason"] == "MARKET_AT_OR_BELOW_AVERAGE"
    assert direct["paths"]["e1"]["next_open"]["status"] == "NO_INTENT"
    trade_ref = direct["paths"]["e0"]["next_open"]["trade_ref"]
    fill, = [item for item in attribution["trades"] if item["ref"] == trade_ref]
    assert fill["signal_ref"] == direct["ref"]
    assert (fill["date"], fill["side"], fill["quantity"], fill["price"], fill["fee"]) == (
        days[60], "BUY", 9800, "10.01", "30.41",
    )
    assert diverged["date"] == days[60]
    assert diverged["candidate_difference"]
    assert diverged["prior_filter_signal_ref"] == direct["ref"]
    rejected = diverged["paths"]["e0"]["next_open"]
    assert (rejected["date"], rejected["status"], rejected["reason"]) == (days[61], "UNFILLED", "INSUFFICIENT_CASH")
    assert rejected["trade_ref"] == f"trade:e0:{days[61]}" and rejected["fill"] is None


def _overlapping_holds():
    start = list(sessions("2023-01-03", "2023-12-29"))[-75]
    days, rows = _quotes(start)
    rows[3 * 60]["payload"]["close"] = "11"
    rows[3 * 65]["payload"]["close"] = "9"
    rows[3 * 60 + 2]["payload"]["open"] = "10.10"
    rows[3 * 62 + 2]["payload"]["open"] = "10.12"
    return days, rows


def test_receipt_attributes_overlapping_holdings_once_and_marks_open_positions(tmp_path):
    days, rows = _overlapping_holds()
    attribution = _receipt(tmp_path, rows)["attribution"]

    first, = attribution["holding_periods"]["e0"]
    second, = attribution["holding_periods"]["e1"]
    assert (first["start"], second["start"]) == (days[60], days[62])
    assert all(period["end"] == days[-1] and period["open_at_end"] for period in (first, second))
    # E0 holds 9700 at 10.11 plus 100 at 10.01, while E1 holds 9700 at 10.13.
    assert (first["nav_change"], second["nav_change"]) == ("8696.59", "8408.54")
    assert [point["closing"]["total_shares"] for point in first["positions"]] == [9700] + [9800] * 14

    segment, = attribution["segments"]
    assert segment["start"] == days[60] and segment["end"] == days[-1]
    assert segment["holding_refs"] == [first["ref"], second["ref"]]
    assert segment["paths"]["e0"]["costs"] == "35.41"
    assert segment["paths"]["e1"]["costs"] == "30.46"
    assert segment["net_difference"] == "-288.05"
    assert segment["return_contribution"] == "-0.0028805"
    assert segment["slippage_difference"] == "-1"


def test_receipt_locates_each_paths_max_drawdown_and_the_shares_actually_held(tmp_path):
    days, rows = _overlapping_holds()
    attribution = _receipt(tmp_path, rows)["attribution"]

    e0, e1 = (attribution["drawdowns"][path] for path in ("e0", "e1"))
    assert (e0["peak_date"], e0["trough_date"]) == (days[60], days[65])
    assert (e0["peak_nav"], e0["trough_nav"]) == ("108602.6", "89096.59")
    assert (e1["peak_date"], e1["trough_date"]) == (days[59], days[65])
    assert (e1["peak_nav"], e1["trough_nav"]) == ("100000", "89008.54")
    assert [point["closing"]["total_shares"] for point in e0["positions"]] == [9700] + [9800] * 5
    assert [point["closing"]["total_shares"] for point in e1["positions"]] == [0] * 3 + [9700] * 4
    for drawdown, path in ((e0, "e0"), (e1, "e1")):
        assert drawdown["magnitude"] == attribution["metrics"][f"metric:{path}:max_drawdown"]["value"]


def test_receipt_reconciles_a_difference_concentrated_in_one_segment(tmp_path):
    _, rows = _overlapping_holds()
    attribution = _receipt(tmp_path, rows)["attribution"]

    comparison = attribution["comparison"]
    assert comparison["classification"] == "single_segment"
    assert comparison["segment_refs"] == [attribution["segments"][0]["ref"]]
    assert comparison["dominant_segment_ref"] == comparison["segment_refs"][0]
    assert comparison["dominant_absolute_share"] == "1"
    assert comparison["total_net_difference"] == comparison["attributed_net_difference"] == "-288.05"
    assert comparison["residual_net_difference"] == "0"
    assert attribution["basis"]["costs_only"].startswith("仅当")


def test_receipt_can_explain_a_flat_price_difference_entirely_by_execution_costs(tmp_path):
    start = list(sessions("2021-01-01", "2022-04-28"))[-61]
    days, rows = _quotes(start)
    rows[3 * 60 + 1]["payload"]["close"] = "101"
    rows[3 * 61 + 1]["payload"]["close"] = "100"
    rows[-3]["payload"]["close"] = "10"
    attribution = _receipt(tmp_path, rows)["attribution"]

    assert days[60:62] == ["2022-04-28", "2022-04-29"]
    comparison = attribution["comparison"]
    assert comparison["classification"] == "costs_only"
    # Equal fills straddle the transfer fee change from 0.002% to 0.001%.
    assert comparison["total_cost_difference"] == "-0.98"
    assert comparison["total_slippage_difference"] == "0"
    assert comparison["total_net_difference"] == "0.98"


def test_receipt_locates_an_unusable_mark_without_claiming_a_complete_segment(tmp_path):
    days, rows = _overlapping_holds()
    rows[3 * 65]["quality"] = "unusable"
    attribution = _receipt(tmp_path, rows)["attribution"]

    gap_ref = f"gap:{days[65]}:valuation:MISSING_VALUATION_MARK"
    assert attribution["gaps"][gap_ref]["observation_quality"] == "unusable"
    assert attribution["drawdowns"]["e0"]["status"] == "unavailable"
    assert attribution["drawdowns"]["e0"]["gap_refs"] == [gap_ref]
    segment, = attribution["segments"]
    assert segment["net_difference"] is None
    assert segment["paths"]["e0"]["observed_nav_change"] == "8696.59"
    assert segment["paths"]["e0"]["costs"] == "35.41"
    assert segment["paths"]["e0"]["gap_refs"] == [gap_ref]
    assert attribution["comparison"]["classification"] == "evidence_insufficient"
    assert attribution["comparison"]["total_net_difference"] is None


def test_receipt_explains_why_a_common_entry_gap_leaves_no_fills_to_compare(tmp_path):
    start = list(sessions("2023-01-03", "2023-12-29"))[-65]
    days, rows = _quotes(start)
    rows[3 * 59]["payload"]["close"] = "9"
    rows = [row for row in rows if row["symbol"] != "000300.SH" or row["trade_date"] < days[60]]
    attribution = _receipt(tmp_path, rows)["attribution"]

    comparison = attribution["comparison"]
    assert comparison["classification"] == "evidence_insufficient"
    assert comparison["total_net_difference"] == "0"
    no_fills = "gap:comparison:no_fills"
    assert no_fills in comparison["gap_refs"]
    assert attribution["gaps"][no_fills]["reason"] == "NO_SIMULATED_FILLS"
    coverage = f"coverage:{days[60]}:market:missing"
    assert coverage in attribution["gaps"][no_fills]["related_gap_refs"]
    first_missing = attribution["signals"][1]
    assert first_missing["gap_refs"] == [coverage]
    assert {path["gate_reason"] for path in first_missing["paths"].values()} == {"COMMON_ENTRY_INPUT_UNAVAILABLE"}


def test_receipt_recognizes_matching_actions_and_fills_on_complete_paths(tmp_path):
    start = list(sessions("2023-01-03", "2023-12-29"))[-75]
    days, rows = _quotes(start)
    for index in range(len(days)):
        rows[3 * index + 1]["payload"]["close"] = str(100 + index)
    attribution = _receipt(tmp_path, rows)["attribution"]

    assert attribution["metrics"]["metric:e0:fills"]["value"] > 0
    comparison = attribution["comparison"]
    assert comparison["classification"] == "actions_identical"
    assert comparison["action_difference_signal_refs"] == comparison["fill_difference_signal_refs"] == []
    assert comparison["total_net_difference"] == "0"
