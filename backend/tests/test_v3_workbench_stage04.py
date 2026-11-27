"""Stage 04 acceptance tests: background runner, SQLite concurrency, privacy-safe followup and archive."""
import io
import json
import sys
import threading
import time

from fastapi.testclient import TestClient

from roll.v3.cli import run
from roll.v3.research import ResearchDossiers
from roll.v3.research_lifecycle import attempt_lock
from roll.v3.research_tasks import (
    enqueue_task,
    execute_attempt,
    freeze_manifest,
    get_attempt,
    get_task,
    offline_executor,
    task_database,
)
from roll.v3.storage import json_text
from roll.v3.web import create_app


DECISION = "2026-11-27T16:00:00+08:00"
SYMBOL = "600362.SH"


def _seed_review_with_private_finding(tmp_path, monkeypatch, private_marker):
    from test_v3_review import NEXT_CLOSE, NEXT_OPEN, seed_trend
    from roll.v3 import research
    from roll.v3.storage import instant

    publication_time = "2026-11-26T16:00:00+08:00"
    monkeypatch.setattr(research, "instant", lambda value=None: instant(value or publication_time))
    version = seed_trend(tmp_path, opening="10.90")
    draft = tmp_path / "copper-v1.md"
    draft.write_text("""---
valid_until: "2026-12-15T00:00:00+08:00"
fundamental_gate: pass
evidence:
  - id: quarterly-report
    title: 演练用季报
    source: 测试材料
    document_id: quarterly-report
    locator: 合并现金流量表
constraint_basis:
  fundamental_gate:
    evidence_refs: [quarterly-report]
  thesis_status:
    rationale: 演练假设由研究者定期复核
thesis_status: intact
hypothesis: 收盘维持在十元以上
invalidation_triggers:
  - id: close-below-ten
    feature: close
    operator: "<"
    threshold: 10
    effect: block_new_risk
---
# 收盘价格假设
""", encoding="utf-8")
    run(("research", "draft", SYMBOL, str(draft)), data_dir=tmp_path)
    run(("research", "publish", SYMBOL, "copper-v1", "--reviewer", "研究者"), data_dir=tmp_path)

    registration = run((
        "review", "register", "--mode", "rehearsal", "--now", DECISION,
        "--strategy-version", version, "--price-only",
    ), data_dir=tmp_path)
    key = registration["registration_id"]
    plan_id = registration["plans"][0]["real_plan"]["plan_id"]
    closing = tmp_path / "closing.json"
    closing.write_text(json.dumps([{
        "series": "daily_bar", "symbol": SYMBOL, "trade_date": "2026-11-30", "source": "fixture",
        "available_at": "2026-11-30T15:05:00+08:00", "received_at": "2026-11-30T15:05:00+08:00",
        "payload": {"close": "9", "prior_close": "11", "pre_close": "11", "trading_status": "trading"},
    }]), encoding="utf-8")
    run(("market", "import", str(closing)), data_dir=tmp_path)
    preview = run(("plan", "--as-of", NEXT_CLOSE, "--preview"), data_dir=tmp_path)
    ref = "market:" + preview["snapshot_id"]
    from roll.v3.review import DecisionLedger

    DecisionLedger(tmp_path).record_finding(
        key, SYMBOL, category="research_hypothesis", trigger_id="close-below-ten", now=NEXT_CLOSE,
        reason=f"私有演练备注 {private_marker}：持仓成本偏高", evidence_refs=[ref],
    )
    followup, = run(("research", "followups", SYMBOL, "--mode", "rehearsal", "--as-of", NEXT_CLOSE), data_dir=tmp_path)
    return {"registration_id": key, "plan_id": plan_id, "followup": followup, "as_of": NEXT_CLOSE, "version": version}


def test_followup_task_strips_private_fields_and_traces_origin(tmp_path, monkeypatch):
    marker = "PRIVATE_REHEARSAL_NOTE_X7731"
    seeded = _seed_review_with_private_finding(tmp_path, monkeypatch, marker)
    followup = seeded["followup"]
    captured_public = []

    def offline_capture(manifest):
        captured_public.append(json.dumps(manifest, ensure_ascii=False))
        return offline_executor(manifest)

    app = create_app(tmp_path, research_executor=offline_capture)
    with TestClient(app) as browser:
        created = browser.post("/api/research/tasks/from-followup", json={
            "followup_id": followup["followup_id"],
            "as_of": seeded["as_of"],
        })
        assert created.status_code == 200, created.text
        receipt = created.json()
        app.state.research_runner.wait(receipt["attempt_id"], timeout=10)
        task = browser.get(f"/api/research/tasks/{receipt['task_id']}").json()
        attempt = task["attempts"][-1]
        assert attempt["status"] == "draft_ready"

        # Public manifest and executor payload MUST NOT leak private note or internal ledger IDs.
        serialized = captured_public[0]
        assert marker not in serialized
        assert seeded["plan_id"] not in serialized
        assert seeded["registration_id"] not in serialized
        assert followup["followup_id"] not in serialized
        assert "risk_budget" not in serialized
        assert "close-below-ten" in serialized

        # Publish the draft from workbench API, then trace back from CLI.
        from roll.v3 import research
        from roll.v3.storage import instant
        monkeypatch.setattr(research, "instant", lambda value=None: instant(value or seeded["as_of"]))
        published = browser.post(f"/api/research/{SYMBOL}/dossiers", json={
            "version": attempt["draft_version"], "reviewer": "审阅人",
        })
        assert published.status_code == 200, published.text

    traced = run(("research", "trace", SYMBOL, attempt["draft_version"]), data_dir=tmp_path)
    assert traced["task_id"] == receipt["task_id"]
    assert traced["attempt_id"] == receipt["attempt_id"]
    assert traced["followup_link"]["followup_id"] == followup["followup_id"]
    assert traced["followup_link"]["registration_id"] == seeded["registration_id"]
    assert traced["followup_link"]["plan_id"] == seeded["plan_id"]
    assert traced["followup_link"]["trigger_id"] == "close-below-ten"


def test_concurrent_rehearsal_review_during_background_research(tmp_path, monkeypatch):
    from test_v3_review import seed_trend

    version = seed_trend(tmp_path, opening="10.90")
    started = threading.Event()
    release = threading.Event()

    def slow_executor(manifest):
        started.set()
        release.wait(timeout=10)
        return offline_executor(manifest)

    app = create_app(tmp_path, research_executor=slow_executor)
    with TestClient(app) as browser:
        created = browser.post("/api/research/tasks", json={
            "symbol": SYMBOL,
            "question": "核对最新收盘价",
            "as_of": DECISION,
            "basis": "stock-close",
        })
        assert created.status_code == 200, created.text
        attempt_id = created.json()["attempt_id"]
        assert started.wait(timeout=5), "background research should be actively running"

        # Register a rehearsal review via CLI on the EXACT same SQLite DB while research runs.
        reg = run((
            "review", "register", "--mode", "rehearsal", "--now", DECISION,
            "--strategy-version", version, "--price-only",
        ), data_dir=tmp_path)
        assert reg["mode"] == "rehearsal"
        audit = run(("forward-window", "audit", "--book-id", "real", "--start", "2026-11-27", "--end", "2026-11-27"),
                    data_dir=tmp_path)
        assert audit["consecutive_live_sessions"] == 0

        release.set()
        app.state.research_runner.wait(attempt_id, timeout=10)
        done = browser.get(f"/api/research/attempts/{attempt_id}").json()
        assert done["status"] == "draft_ready"


def test_single_owner_restart_recovery_and_cancel_race(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({
        "cash": "2200", "available_cash": "2200", "effective_at": DECISION, "known_at": DECISION,
    })))
    run(("account", "init"), data_dir=tmp_path)
    closing = tmp_path / "bar.json"
    closing.write_text(json.dumps([{
        "series": "daily_bar", "symbol": SYMBOL, "trade_date": "2026-11-27", "source": "fixture",
        "available_at": "2026-11-27T15:05:00+08:00", "received_at": "2026-11-27T15:05:00+08:00",
        "payload": {"close": "11", "prior_close": "10.8", "pre_close": "10.8", "trading_status": "trading"},
    }]), encoding="utf-8")
    run(("market", "import", str(closing)), data_dir=tmp_path)
    snap = run(("market", "freeze", SYMBOL, "--start", "2026-11-27", "--end", "2026-11-27", "--as-of", DECISION),
               data_dir=tmp_path)["snapshot_id"]

    # 1. Single owner on concurrent claim of the same pending attempt
    manifest = freeze_manifest(tmp_path, SYMBOL, question="并发领取核对", snapshot_id=snap, as_of=DECISION, basis="stock-close")
    pending = enqueue_task(tmp_path, manifest)
    calls = []

    def counted_executor(m):
        calls.append(1)
        time.sleep(0.15)
        return offline_executor(m)

    t1 = threading.Thread(target=execute_attempt, args=(tmp_path, pending["attempt_id"]), kwargs={"executor": counted_executor})
    t2 = threading.Thread(target=execute_attempt, args=(tmp_path, pending["attempt_id"]), kwargs={"executor": counted_executor})
    t1.start()
    t2.start()
    t1.join()
    t2.join()
    assert len(calls) == 1
    assert get_attempt(tmp_path, pending["attempt_id"])["status"] == "draft_ready"

    # 2. CLI-held lock survives workbench restart; once dead, recovers to interrupted and retries
    cli_attempt_id = "attempt-0123456789abcdef0123456789abcdef"
    cli_task_id = "task-0123456789abcdef0123456789abcdef"
    with task_database(tmp_path, write=True) as db:
        db.execute("INSERT INTO research_task VALUES (?,?)", (cli_task_id, json_text(manifest)))
        db.execute("INSERT INTO research_attempt VALUES (?,?,?)", (
            cli_attempt_id, cli_task_id, json_text({
                "task_id": cli_task_id, "attempt_id": cli_attempt_id,
                "status": "running", "receipt_version": 2, "gaps": [], "draft_version": None,
            }),
        ))
    with attempt_lock(tmp_path, cli_attempt_id) as lock:
        assert lock is not None
        with TestClient(create_app(tmp_path, research_executor=offline_executor)):
            assert get_attempt(tmp_path, cli_attempt_id)["status"] == "running"
    # Now lock is released (owner exited): restart marks it interrupted, retry succeeds
    app2 = create_app(tmp_path, research_executor=offline_executor)
    with TestClient(app2) as browser:
        assert get_attempt(tmp_path, cli_attempt_id)["status"] == "interrupted"
        retried = browser.post(f"/api/research/tasks/{cli_task_id}/retry", json={})
        assert retried.status_code == 200
        app2.state.research_runner.wait(retried.json()["attempt_id"], timeout=10)
        assert get_attempt(tmp_path, retried.json()["attempt_id"])["status"] == "draft_ready"

    # 3. Cancel before commit leaves no draft
    started = threading.Event()
    release = threading.Event()

    def cancellable_executor(m):
        started.set()
        release.wait(timeout=10)
        return offline_executor(m)

    app3 = create_app(tmp_path, research_executor=cancellable_executor)
    with TestClient(app3) as browser:
        created = browser.post("/api/research/tasks", json={
            "symbol": SYMBOL, "question": "取消竞争测试", "as_of": DECISION,
            "snapshot_id": snap, "basis": "stock-close",
        })
        attempt_id = created.json()["attempt_id"]
        assert started.wait(timeout=5)
        # Mark cancelling before commit
        with task_database(tmp_path, write=True) as db:
            row = db.execute("SELECT receipt FROM research_attempt WHERE attempt_id=?", (attempt_id,)).fetchone()
            rec = json.loads(row["receipt"])
            rec["status"] = "cancelling"
            db.execute("UPDATE research_attempt SET receipt=? WHERE attempt_id=?", (json_text(rec), attempt_id))
        release.set()
        app3.state.research_runner.wait(attempt_id, timeout=10)
        final = get_attempt(tmp_path, attempt_id)
        assert final["status"] == "cancelled"
        assert ResearchDossiers(tmp_path).draft(SYMBOL, attempt_id) is None


def test_development_task_archive_via_web_leaves_dossier_and_plan_unchanged(tmp_path, monkeypatch):
    from roll.v3.development_interpretation import offline_interpretation
    from roll.v3.storage import sessions

    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({
        "cash": "100000", "available_cash": "100000", "effective_at": DECISION, "known_at": DECISION,
    })))
    run(("account", "init"), data_dir=tmp_path)
    bars = []
    days = list(sessions("2020-01-02", "2020-06-30"))
    for idx, day in enumerate(days):
        close = round(14.0 + (idx % 15) * 0.25 + idx * 0.02, 2)
        prior = round(14.0 + (max(0, idx - 1) % 15) * 0.25 + max(0, idx - 1) * 0.02, 2)
        bars.append({
            "series": "daily_bar", "symbol": SYMBOL, "trade_date": day, "source": "fixture",
            "available_at": f"{day}T15:05:00+08:00", "received_at": f"{day}T15:05:00+08:00",
            "payload": {"open": str(prior), "close": str(close), "high": str(close), "low": str(prior),
                        "prior_close": str(prior), "pre_close": str(prior), "trading_status": "trading"},
        })
        bars.append({
            "series": "daily_open", "symbol": SYMBOL, "trade_date": day, "source": "fixture",
            "available_at": f"{day}T09:30:00+08:00", "received_at": f"{day}T09:30:00+08:00",
            "payload": {"open": str(prior), "prior_close": str(prior), "pre_close": str(prior), "trading_status": "trading"},
        })
        bench = round(4000.0 + idx * 3.0, 2)
        b_prior = round(4000.0 + max(0, idx - 1) * 3.0, 2)
        bars.append({
            "series": "daily_bar", "symbol": "000300.SH", "trade_date": day, "source": "fixture",
            "available_at": f"{day}T15:05:00+08:00", "received_at": f"{day}T15:05:00+08:00",
            "payload": {"open": str(b_prior), "close": str(bench), "high": str(bench), "low": str(b_prior),
                        "prior_close": str(b_prior), "pre_close": str(b_prior), "trading_status": "trading"},
        })
    bars_file = tmp_path / "dev-bars.json"
    bars_file.write_text(json.dumps(bars), encoding="utf-8")
    run(("market", "import", str(bars_file)), data_dir=tmp_path)
    snap = run((
        "market", "freeze", SYMBOL, "000300.SH",
        "--start", "2020-01-02", "--end", "2023-12-29",
        "--as-of", "2026-11-26T16:00:00+08:00", "--use-mode", "RECONSTRUCTED_RESEARCH",
    ), data_dir=tmp_path)["snapshot_id"]

    before_plan = run(("plan", "--as-of", DECISION, "--symbol", SYMBOL, "--preview"), data_dir=tmp_path)
    app = create_app(tmp_path, research_executor=offline_interpretation)
    with TestClient(app) as browser:
        presets = browser.get("/api/development/presets").json()
        assert presets[0]["id"] == "jxcc-e0-e1-v1"
        created = browser.post("/api/development/tasks", json={"preset_id": "jxcc-e0-e1-v1", "snapshot_id": snap})
        assert created.status_code == 200, created.text
        receipt = created.json()
        app.state.research_runner.wait(receipt["attempt_id"], timeout=15)
        detail = browser.get(f"/api/development/tasks/{receipt['task_id']}").json()
        attempt = detail["attempts"][-1]
        assert attempt["status"] == "report_ready"
        assert detail["development_receipt"]["metrics"]["e0"]["fills"] >= 0

        archived = browser.post(f"/api/development/tasks/{receipt['task_id']}/archive", json={
            "attempt_id": attempt["attempt_id"],
            "report_version": attempt["report_version"],
            "conclusion": "evidence_insufficient",
            "decision": "stop",
            "reviewer": "审阅人",
            "reason": "样本覆盖不足，停止扩展",
        })
        assert archived.status_code == 200, archived.text
        assert archived.json()["decision"] == "stop"

        # Verify task appears under development_experiment list and NOT under dossier list
        dev_list = browser.get("/api/research/tasks", params={"kind": "development_experiment"}).json()
        dossier_list = browser.get("/api/research/tasks", params={"kind": "dossier"}).json()
        assert any(item["task_id"] == receipt["task_id"] for item in dev_list)
        assert not any(item["task_id"] == receipt["task_id"] for item in dossier_list)

    after_plan = run(("plan", "--as-of", DECISION, "--symbol", SYMBOL, "--preview"), data_dir=tmp_path)
    assert after_plan["plans"] == before_plan["plans"]

