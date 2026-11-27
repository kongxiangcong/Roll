"""Exercise the packaged workbench against plans from the normal Roll CLI."""
import io
import json
import sys

from fastapi.testclient import TestClient

from roll.v3.cli import run
from roll.v3.web import create_app


DECISION = "2026-11-27T16:00:00+08:00"
SYMBOL = "600362.SH"


def test_workbench_reads_the_same_immutable_plan_as_the_cli(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({
        "cash": "2200", "available_cash": "2200", "effective_at": DECISION, "known_at": DECISION,
    })))
    run(("account", "init"), data_dir=tmp_path)
    plan, = run(("plan", "--as-of", DECISION, "--symbol", SYMBOL), data_dir=tmp_path)["plans"]
    replay = run(("plan", "--plan-id", plan["plan_id"]), data_dir=tmp_path)

    with TestClient(create_app(tmp_path)) as browser:
        page = browser.get("/")
        assert page.status_code == 200
        assert "盘后工作台" in page.text
        assert browser.get("/assets/workbench.js").status_code == 200
        assert browser.get("/assets/workbench.css").status_code == 200
        response = browser.get(f"/api/plans/{plan['plan_id']}")
        assert response.status_code == 200
        assert response.json() == replay
        assert response.json()["action"] == "WATCH"
        assert list(response.json()["reasons"]) == ["P0", "P1", "P2", "P3", "P4"]
        assert browser.get("/api/plans", params={"session": "2026-11-30"}).json() == [replay]


def test_workbench_review_carries_evidence_into_a_new_dossier_version(tmp_path, monkeypatch):
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
    dossier = run(("research", "publish", SYMBOL, "copper-v1", "--reviewer", "研究者"), data_dir=tmp_path)

    with TestClient(create_app(tmp_path)) as browser:
        assert browser.get(f"/api/research/{SYMBOL}/dossiers", params={"as_of": DECISION}).json() == dossier
        registration = browser.post("/api/reviews", json={
            "mode": "rehearsal", "now": DECISION, "strategy_versions": [version], "price_only": True,
        })
        assert registration.status_code == 200, registration.text
        result = registration.json()
        key = result["registration_id"]
        before, = result["plans"]
        plan_id = before["real_plan"]["plan_id"]
        assert before["real_plan"]["action"] == "WATCH"
        assert before["shadow_plan"]["action"] == "BUY"
        assert before["real_plan"]["dossier_version"] == "copper-v1"

        settled = browser.post(f"/api/reviews/{key}/settle", json={"now": NEXT_OPEN})
        assert settled.status_code == 200, settled.text
        after, = settled.json()["plans"]
        assert after["shadow"]["status"] == "FILLED"
        assert after["shadow"]["fill"]["quantity"] == 100
        assert after["real_plan"] == before["real_plan"]
        assert browser.post(f"/api/reviews/{key}/settle", json={"now": NEXT_OPEN}).json() == settled.json()
        assert run(("review", "show", key, "--as-of", NEXT_OPEN), data_dir=tmp_path) == settled.json()
        closing = tmp_path / "closing.json"
        closing.write_text(json.dumps([{
            "series": "daily_bar", "symbol": SYMBOL, "trade_date": "2026-11-30", "source": "fixture",
            "available_at": "2026-11-30T15:05:00+08:00", "received_at": "2026-11-30T15:05:00+08:00",
            "payload": {"close": "9", "prior_close": "11", "pre_close": "11", "trading_status": "trading"},
        }]))
        run(("market", "import", str(closing)), data_dir=tmp_path)
        preview = run(("plan", "--as-of", NEXT_CLOSE, "--preview"), data_dir=tmp_path)
        reference = "market:" + preview["snapshot_id"]
        assert "TRIGGER_FIRED:close-below-ten" in preview["plans"][0]["reasons"]["P2"]
        finding = browser.post(f"/api/reviews/{key}/findings", json={
            "symbol": SYMBOL, "category": "research_hypothesis", "trigger_id": "close-below-ten",
            "now": NEXT_CLOSE, "reason": "下一交易日收盘 9 元", "evidence_refs": [reference],
        })
        assert finding.status_code == 200, finding.text
        evidence, = browser.get(
            f"/api/research/{SYMBOL}/followups", params={"mode": "rehearsal", "as_of": NEXT_CLOSE},
        ).json()
        assert evidence["trigger_id"] == "close-below-ten"
        assert evidence["plan_id"] == plan_id
        assert evidence["evidence_refs"] == [reference]

        publication_time = NEXT_CLOSE
        draft_v2 = """---
valid_until: "2026-12-15T00:00:00+08:00"
fundamental_gate: fail
thesis_status: broken
---
# 收盘跌破十元
复盘证据：{reference}
""".format(reference=evidence["evidence_refs"][0])
        imported = browser.post(f"/api/research/{SYMBOL}/drafts", json={
            "version": "copper-v2", "markdown": draft_v2,
        })
        assert imported.status_code == 200, imported.text
        revised = browser.post(f"/api/research/{SYMBOL}/dossiers", json={
            "version": "copper-v2", "reviewer": "研究者",
        })
        assert revised.status_code == 200, revised.text
        assert revised.json() == run(("research", "show", SYMBOL, "--as-of", NEXT_CLOSE), data_dir=tmp_path)
        new_plan, = run(("plan", "--as-of", NEXT_CLOSE), data_dir=tmp_path)["plans"]
        assert new_plan["dossier_version"] == "copper-v2"
        assert new_plan["reasons"]["P2"] != before["real_plan"]["reasons"]["P2"]
        assert "THESIS_BROKEN" in new_plan["reasons"]["P2"]
        assert browser.get(f"/api/plans/{plan_id}").json() == before["real_plan"]
        assert run(("plan", "--plan-id", plan_id), data_dir=tmp_path) == before["real_plan"]
