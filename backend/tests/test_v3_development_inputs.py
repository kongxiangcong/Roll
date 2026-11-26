import json
import socket

from roll.v3.cli import run
from roll.v3.storage import sessions


PRESET = "jxcc-e0-e1-v1"


def command(data_dir, *arguments):
    return run(["--data-dir", str(data_dir), *arguments])


def test_preview_lists_the_complete_versioned_development_preset(tmp_path):
    preset = command(tmp_path, "research", "task", "development-preset")

    assert preset["id"] == PRESET
    assert preset["symbol"] == "600362.SH"
    assert preset["e0"]["feature"] == "total_return_index"
    assert preset["e0"]["parameters"] == {"fast": 20, "slow": 60}
    assert preset["e0"]["entry_operator"] == ">"
    assert preset["e1"] == {
        "symbol": "000300.SH", "feature": "raw_close", "lookback_sessions": 20,
        "includes_signal_day": True, "entry_operator": ">", "applies_to": "buy_only",
    }
    assert preset["signal_time"] == "15:05 Asia/Shanghai"
    assert preset["execution_time"] == "next_session_open 09:30 Asia/Shanghai"
    assert preset["protocol"]["windows"] == {
        "development": {"start": "2020-01-02", "end": "2023-12-29"},
    }


def load_snapshot(data_dir, observations, *, mode="RECONSTRUCTED_RESEARCH"):
    incoming = data_dir / "incoming.json"
    incoming.write_text(json.dumps(observations), encoding="utf-8")
    command(data_dir, "market", "import", str(incoming))
    return command(
        data_dir, "market", "freeze", "600362.SH", "000300.SH",
        "--start", "2019-01-02", "--end", "2026-11-25", "--as-of", "2026-11-26T15:05:00+08:00",
        "--use-mode", mode, "--series", "daily_bar", "--series", "daily_open", "--series", "corporate_action",
        "--series", "adjustment_factor", "--series", "announcement", "--series", "review_note",
        "--series", "window_summary",
    )["snapshot_id"]


def test_blocked_sample_still_has_a_retrievable_attempt_without_formal_exposure(tmp_path):
    strategy = command(tmp_path, "strategy", "freeze")["strategy"]["version"]
    before = command(tmp_path, "strategy", "show", strategy)
    snapshot_id = load_snapshot(tmp_path, [])
    attempt = command(tmp_path, "research", "task", "development", "--preset", PRESET, "--snapshot", snapshot_id)

    read = command(tmp_path, "research", "task", "show", attempt["task_id"])
    assert read["manifest"]["preset"] == command(tmp_path, "research", "task", "development-preset")
    assert read["manifest"]["snapshot_id"] == snapshot_id
    assert read["manifest"]["sample"]["effective_window"] is None
    assert read["manifest"]["sample"]["losses"]["2020-01-02"] == [
        {"feature": "e0", "reason": "missing"}, {"feature": "market", "reason": "missing"},
    ]
    assert read["attempts"][0] == command(tmp_path, "research", "task", "attempt", attempt["attempt_id"])
    assert attempt["status"] == "blocked"
    assert attempt["snapshot_id"] == snapshot_id
    assert attempt["input_ref"] == read["manifest"]["input_ref"]
    assert attempt["gaps"][0]["blocking"] is True
    assert command(tmp_path, "strategy", "show", strategy) == before


def observation(day, *, series="daily_bar", symbol="600362.SH", close="100", source="archive-a", **changes):
    return {
        "series": series, "symbol": symbol, "trade_date": day, "source": source, "revision": "2026-edition-1",
        "received_at": "2026-11-25T15:05:00+08:00", "assumed_available_at": f"{day}T15:05:00+08:00",
        "availability_assumption": "archived close at 15:05 Asia/Shanghai",
        "payload": {"close": close, "pre_close_basis": "prior_close_no_adjustment_factor", "trading_status": "trading"},
        **changes,
    }


def create_manifest(data_dir, snapshot_id):
    attempt = command(data_dir, "research", "task", "development", "--preset", PRESET, "--snapshot", snapshot_id)
    return command(data_dir, "research", "task", "show", attempt["task_id"])["manifest"]


def test_development_freezes_the_common_opportunity_set_at_each_daily_cutoff(tmp_path, monkeypatch):
    def unexpected_network(*args, **kwargs):
        raise AssertionError("the development experiment must run offline")

    monkeypatch.setattr(socket.socket, "connect", unexpected_network)
    monkeypatch.setattr(socket, "getaddrinfo", unexpected_network)
    all_days = list(sessions("2020-01-02", "2023-12-29"))
    days = all_days[:150]
    rows = [observation(day, close=str(100 + i)) for i, day in enumerate(days)]
    rows[70].update(quality="unusable")
    rows += [
        observation(day, symbol="000300.SH", close={130: "99", 131: "101"}.get(i, "100"))
        for i, day in enumerate(days[43:], start=43) if i not in (49, 132)
    ]
    rows += [
        observation(days[49], symbol="000300.SH", assumed_available_at=f"{days[49]}T15:06:00+08:00"),
        observation(days[70], symbol="000300.SH", close="200", source="archive-b"),
        observation(days[70], series="adjustment_factor", item_id="dividend", quality="unusable"),
    ]
    rows += [observation(day) for day in sessions("2019-07-01", "2019-12-31")]
    manifest = create_manifest(tmp_path, load_snapshot(tmp_path, rows))
    sample = manifest["sample"]

    assert sample["nominal_window"] == {"start": "2020-01-02", "end": "2023-12-29"}
    assert sample["effective_window"] == {"start": days[69], "end": "2023-12-29"}
    assert sample["candidate_day_count"] == 970
    assert sample["common_evaluable_dates"] == [days[69], days[130], days[131]]
    assert sample["common_evaluable_day_count"] == 3
    assert sample["loss_day_count"] == 967
    assert sample["losses"][days[49]] == [
        {"feature": "e0", "reason": "warmup"}, {"feature": "market", "reason": "not_visible"},
    ]
    assert sample["losses"][days[70]] == [
        {"feature": "e0", "reason": "unusable"}, {"feature": "adjustment_factor", "reason": "unusable"},
        {"feature": "market", "reason": "conflict"},
    ]
    assert sample["losses"][days[132]] == [{"feature": "market", "reason": "missing"}]
    signals = sample["by_date"]
    assert signals[days[58]]["e0"]["status"] == "warmup"
    assert signals[days[59]]["e0"]["signal"] == "long"
    assert signals[days[69]]["market"]["average"] == "100"
    assert [signals[days[i]]["market"]["above_average"] for i in (69, 130, 131)] == [False, False, True]
    assert manifest["snapshot"]["use_mode"] == "RECONSTRUCTED_RESEARCH"
    assert manifest["snapshot"]["external_data_requests"] == 0
    assert manifest["snapshot"]["paid_data_cost_cny"] == "0"
    source = manifest["snapshot"]["sources"][0]
    assert source["last_received_at"] == "2026-11-25T07:05:00.000000+00:00"
    assert source["revisions"] == ["2026-edition-1"]
    assert source["availability_assumptions"] == ["archived close at 15:05 Asia/Shanghai"]


def test_outside_material_leaves_frozen_development_inputs_unchanged(tmp_path):
    days = list(sessions("2020-01-02", "2020-07-01"))
    rows = [observation(day, close=str(100 + i), source_ref=str(tmp_path / "private-source"))
            for i, day in enumerate(days)]
    rows += [observation(day, symbol="000300.SH") for day in days]
    rows += [observation("2024-01-02", close="8888800"), observation("2026-11-25", series="announcement",
             payload={"text": "announce-sentinel-a"}), observation("2026-11-25", series="review_note",
             payload={"text": "review-sentinel-a"}), observation(days[-1], series="window_summary",
             payload={"text": "full-window-sentinel-a"})]
    first_snapshot = load_snapshot(tmp_path, rows)
    first = create_manifest(tmp_path, first_snapshot)
    changed_snapshot = load_snapshot(tmp_path, [
        observation("2024-01-02", close="9999900"), observation("2026-11-25", series="announcement",
        payload={"text": "announce-sentinel-b"}), observation("2026-11-25", series="review_note",
        payload={"text": "review-sentinel-b"}), observation(days[-1], series="window_summary",
        payload={"text": "full-window-sentinel-b"}),
    ])
    changed = create_manifest(tmp_path, changed_snapshot)

    assert first_snapshot != changed_snapshot
    for manifest in (first, changed):
        public_text = json.dumps(manifest)
        for token in ("8888800", "9999900", "announce-sentinel", "review-sentinel", "full-window-sentinel",
                      "private-source", "2024-01-02"):
            assert token not in public_text
        assert "scope" not in manifest["snapshot"]
        del manifest["snapshot_id"], manifest["snapshot"]["snapshot_id"]
    assert first == changed

    later_snapshot = load_snapshot(tmp_path, [observation(days[-1], close="60")])
    later = create_manifest(tmp_path, later_snapshot)
    before, after = first["sample"]["by_date"], later["sample"]["by_date"]
    assert before[days[-1]]["e0"] != after[days[-1]]["e0"]
    assert all(before[day] == after[day] for day in days[:-1])
