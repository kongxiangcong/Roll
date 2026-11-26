import json

import pytest

from test_v3_research_tasks import material_file, snapshot, start, task_cli


def test_missing_codex_records_replayable_configuration_error(tmp_path, snapshot, monkeypatch):
    monkeypatch.setenv("PATH", str(tmp_path / "no-binaries"))
    path = material_file(tmp_path, "季报", excerpt="经营现金流增加")
    receipt = start(tmp_path, snapshot, "--executor", "codex", "--material", path)
    assert receipt["status"] == "failed"
    assert receipt["failure_kind"] == "configuration"
    assert receipt["executor"] == "codex"
    assert receipt["draft_version"] is None and receipt["exit_code"] is None
    assert "codex" in receipt["error"].lower()
    assert receipt["attempt_id"] in receipt["log_ref"]
    assert (tmp_path / receipt["log_ref"]).is_file()
    assert task_cli(tmp_path, "attempt", receipt["attempt_id"]) == receipt


def install_cli(tmp_path, monkeypatch, body):
    executable = tmp_path / "bin" / "codex"
    executable.parent.mkdir(exist_ok=True)
    executable.write_text("""#!/usr/bin/python3
import json, sys
from pathlib import Path
if "--version" in sys.argv:
    print("codex-cli 0.172.0")
elif "debug" in sys.argv:
    print(json.dumps({"models": [{"slug":"gpt-6.2-sol"}]}))
else:
""" + "\n".join("    " + line for line in body.splitlines()) + "\n")
    executable.chmod(0o700)
    monkeypatch.setenv("PATH", str(executable.parent))
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "empty-home"))
    monkeypatch.setenv("CODEX_API_KEY", "synthetic-probe-key")


def test_codex_gap_retains_diagnostics_without_raw_streams(tmp_path, snapshot, monkeypatch):
    install_cli(tmp_path, monkeypatch, """
answer = {"gaps": [{"reason": "缺少同期对照", "required_evidence": "上期现金流", "blocking": True}], "draft": None}
Path(sys.argv[sys.argv.index("--output-last-message")+1]).write_text(json.dumps(answer))
print("synthetic-probe-key", file=sys.stderr)
""")
    report = material_file(tmp_path, "季报", excerpt="本期回款增加。")
    receipt = start(tmp_path, snapshot, "--material", report, "--executor", "codex")
    assert receipt["status"] == "blocked", receipt
    assert receipt["gaps"] == [{"reason": "缺少同期对照", "required_evidence": "上期现金流", "blocking": True}]
    assert receipt["exit_code"] == 0
    assert receipt["cli_version"] == "codex-cli 0.172.0"
    assert receipt["draft_version"] is None
    log = (tmp_path / receipt["log_ref"]).read_text()
    assert "synthetic-probe-key" not in log and "synthetic-probe-key" not in str(receipt)


def test_required_binary_announcement_records_readable_excerpt_gap(tmp_path, snapshot, monkeypatch):
    install_cli(tmp_path, monkeypatch, 'raise SystemExit(44)')
    pdf = tmp_path / "original.pdf"
    pdf.write_bytes(b"%PDF-1.7\n\xff\xfa")
    material = material_file(tmp_path, "年度报告", file=pdf.name)
    receipt = start(tmp_path, snapshot, "--executor", "codex", "--require", "年度报告", "--material", material)
    assert receipt["status"] == "blocked", receipt
    gap, = receipt["gaps"]
    assert gap["blocking"] and "年度报告" in gap["required_evidence"] and "文本" in gap["reason"]
    assert receipt["exit_code"] is None


def test_cli_rejects_risk_permission_based_only_on_model_rationale(tmp_path, snapshot, monkeypatch):
    install_cli(tmp_path, monkeypatch, FAKE_DRAFT + """
draft["thesis_status"] = "intact"
draft["constraint_basis"]["thesis_status"]["rationale"] = "模型自行推断，并未获审阅人确认"
Path(sys.argv[sys.argv.index("--output-last-message")+1]).write_text(json.dumps({"draft":draft, "gaps":[]}))
""")
    path = material_file(tmp_path, "季报", excerpt="仅披露当期数据。")
    receipt = start(tmp_path, snapshot, "--executor", "codex", "--material", path)
    assert receipt["status"] == "failed", receipt
    assert receipt["failure_kind"] == "invalid_response"
    assert receipt["draft_version"] is None


FAKE_DRAFT = """
public = json.load(sys.stdin)
ref = public["evidence"][0]["id"]
draft = {"symbol":public["symbol"], "as_of":public["as_of"], "valid_until":public["suggested_valid_until"],
         "markdown":"据季报第三节，销售回款增加。其持续性仍未知。", "evidence_refs":[ref],
         "fundamental_gate":"unknown", "thesis_status":"unknown", "strategy_whitelist":[],
         "invalidation_triggers":[], "constraint_basis":{field: {"evidence_refs":[], "rationale":""}
         for field in ("fundamental_gate","thesis_status","strategy_whitelist","invalidation_triggers")}}
"""


def test_draft_replays_exact_public_prompt_and_attempt_version(tmp_path, snapshot, monkeypatch):
    from hashlib import sha256
    from roll.v3.cli import run

    install_cli(tmp_path, monkeypatch, FAKE_DRAFT + """
Path(sys.argv[sys.argv.index("--output-last-message")+1]).write_text(json.dumps({"draft":draft, "gaps":[]}))
""")
    path = material_file(tmp_path, "季报", excerpt="销售回款增加。", internal_note="private-broker-fact")
    receipt = start(tmp_path, snapshot, "--executor", "codex", "--material", path)
    assert receipt["status"] == "draft_ready", receipt
    prompt = (tmp_path / receipt["input_ref"]).read_bytes()
    assert sha256(prompt).hexdigest() == receipt["input_sha256"]
    public = json.loads(prompt)
    assert public["materials"][0]["content"] == "销售回款增加。"
    assert "private-broker-fact" not in prompt.decode()
    assert public["market_reference"].startswith("market-research:")
    assert "securities" not in public
    draft = run(["research", "show", public["symbol"], "--draft", "--version", receipt["draft_version"]],
                data_dir=tmp_path)
    assert draft["attempt_id"] == receipt["attempt_id"]
    assert draft["evidence_refs"] == [public["materials"][0]["id"]]


@pytest.mark.parametrize(("body", "kind", "exit_code"), [
    ('print("503 Service Unavailable; synthetic-probe-key", file=sys.stderr); sys.exit(9)', "cli_exit", 9),
    ('print("401 Unauthorized", file=sys.stderr); sys.exit(1)', "configuration", 1),
    ('pass', "invalid_response", 0),
    ('Path(sys.argv[sys.argv.index("--output-last-message")+1]).write_text("not json")', "invalid_response", 0),
    (FAKE_DRAFT + """
gap = {"blocking": True, "reason": "缺少对照", "required_evidence": "上期财报"}
Path(sys.argv[sys.argv.index("--output-last-message")+1]).write_text(json.dumps({"gaps": [gap], "draft": draft}))
""", "invalid_response", 0),
    (FAKE_DRAFT + """
draft["evidence_refs"] = ["other-task-only"]
Path(sys.argv[sys.argv.index("--output-last-message")+1]).write_text(json.dumps({"gaps": [], "draft": draft}))
""", "invalid_response", 0),
])
def test_unsuccessful_attempt_has_classified_log_and_no_draft(tmp_path, snapshot, monkeypatch, body, kind, exit_code):
    install_cli(tmp_path, monkeypatch, body)
    report = material_file(tmp_path, "季报", excerpt="销售回款增加。")
    receipt = start(tmp_path, snapshot, "--executor", "codex", "--material", report)
    assert receipt["status"] == "failed" and receipt["draft_version"] is None
    assert (receipt["failure_kind"], receipt["exit_code"]) == (kind, exit_code)
    assert task_cli(tmp_path, "attempt", receipt["attempt_id"]) == receipt
    log = (tmp_path / receipt["log_ref"]).read_text()
    assert kind in log and "synthetic-probe-key" not in log


def test_market_prompt_contains_the_cited_original_price_observation(tmp_path, snapshot, monkeypatch):
    install_cli(tmp_path, monkeypatch, FAKE_DRAFT + """
Path(sys.argv[sys.argv.index("--output-last-message")+1]).write_text(json.dumps({"draft":draft, "gaps":[]}))
""")
    receipt = start(tmp_path, snapshot, "--executor", "codex", "--basis", "stock-close", "--question", "核对收盘价")
    assert receipt["status"] == "draft_ready", receipt
    public = json.loads((tmp_path / receipt["input_ref"]).read_text())
    row, = public["market_observations"]
    assert row["trade_date"] == "2025-07-21" and row["payload"]["close"] == "21.5"
    assert f"seq={row['seq']}" in public["evidence"][0]["locator"]


def test_risk_field_requires_evidence_content_in_this_prompt(tmp_path, snapshot, monkeypatch):
    from datetime import UTC, datetime, timedelta
    from test_v3_research import _write_draft, research_cli

    now = datetime.now(UTC)
    path = _write_draft(tmp_path, "old", (now - timedelta(days=1)).isoformat(),
                        (now + timedelta(days=30)).isoformat())
    research_cli(tmp_path, "draft", "600362.SH", str(path))
    published = research_cli(tmp_path, "publish", "600362.SH", "old", "--reviewer", "研究者")
    report = material_file(tmp_path, "新季报", excerpt="经营活动现金流量净额为正。")
    reply = """
draft["fundamental_gate"] = "pass"
draft["evidence_refs"].append("quarterly-report")
draft["constraint_basis"]["fundamental_gate"] = {"evidence_refs": [basis_ref], "rationale": "经营现金流量净额为正"}
Path(sys.argv[sys.argv.index("--output-last-message")+1]).write_text(json.dumps({"draft":draft, "gaps":[]}))
"""
    install_cli(tmp_path, monkeypatch, FAKE_DRAFT + 'basis_ref = "quarterly-report"\n' + reply)
    failed = start(tmp_path, snapshot, "--executor", "codex", "--as-of", published["published_at"],
                   "--material", report)
    assert failed["status"] == "failed" and failed["failure_kind"] == "invalid_response", failed
    assert "fundamental_gate" in failed["error"]
    assert failed["draft_version"] is None
    install_cli(tmp_path, monkeypatch, FAKE_DRAFT + 'basis_ref = ref\n' + reply)
    retried = task_cli(tmp_path, "retry", failed["task_id"], "--executor", "codex")
    assert retried["status"] == "draft_ready", retried
    public = json.loads((tmp_path / retried["input_ref"]).read_bytes())
    assert public["metadata_only_refs"] == ["quarterly-report"]


def test_delayed_cli_reader_receives_entire_large_announcement(tmp_path, snapshot, monkeypatch):
    excerpt = "现金流数据。" * 16000 + "尾注"
    install_cli(tmp_path, monkeypatch, "import time\ntime.sleep(.25)\n" + FAKE_DRAFT + """
assert public["materials"][0]["content"].endswith("尾注")
Path(sys.argv[sys.argv.index("--output-last-message")+1]).write_text(json.dumps({"draft":draft,"gaps":[]}))
""")
    report = material_file(tmp_path, "季报", excerpt=excerpt)
    receipt = start(tmp_path, snapshot, "--executor", "codex", "--timeout", "4", "--material", report)
    assert receipt["status"] == "draft_ready", receipt


def test_published_codex_triggers_are_evaluated_against_plan_observations(tmp_path, snapshot, monkeypatch):
    from datetime import datetime
    from roll.v3.cli import run
    from test_v3_account import BASELINE, account

    cutoff = "2026-11-27T16:00:00+08:00"

    class FixedClock(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime.fromisoformat(cutoff).astimezone(tz)

    monkeypatch.setattr("roll.v3.storage.datetime", FixedClock)
    account(tmp_path, monkeypatch, "init", payload=BASELINE)
    market = tmp_path / "cash-flow.json"
    market.write_text(json.dumps([{
        "series": "research_feature", "symbol": "600362.SH", "trade_date": "2026-09-30",
        "source": "季报", "source_ref": "quarterly#cash-flow", "available_at": cutoff,
        "received_at": cutoff, "payload": {"feature": "operating_cash_flow_ytd_cny", "value": "-100"},
    }]))
    run(["market", "import", str(market)], data_dir=tmp_path)
    install_cli(tmp_path, monkeypatch, FAKE_DRAFT + """
common = {"evidence_refs":[ref], "source":"季报", "data_required":"累计经营现金流",
          "feature":None, "operator":None, "threshold":None}
numeric = dict(common, feature="operating_cash_flow_ytd_cny", operator="<=", effect="block_new_risk")
draft["invalidation_triggers"] = [
    dict(numeric, id="nonpositive", threshold=0, condition="累计经营现金流不高于零"),
    dict(numeric, id="below-floor", threshold=-200, condition="累计经营现金流不高于负二百"),
    dict(common, id="revised", effect="pause", condition="是否已披露财报更正"),
    dict(common, id="annual-review", effect="require_research", condition="复核年度合并口径"),
]
Path(sys.argv[sys.argv.index("--output-last-message")+1]).write_text(json.dumps({"draft":draft,"gaps":[]}))
""")
    report = material_file(tmp_path, "季报", excerpt="本期累计经营现金流为负一百元。")
    receipt = start(tmp_path, snapshot, "--as-of", cutoff, "--executor", "codex", "--material", report)
    assert receipt["status"] == "draft_ready", receipt
    run(["research", "publish", "600362.SH", receipt["draft_version"], "--reviewer", "研究者"], data_dir=tmp_path)
    plan, = run(["plan", "--as-of", cutoff, "--preview", "--symbol", "600362.SH"], data_dir=tmp_path)["plans"]
    triggers = plan["research"]["triggers"]
    assert [item["status"] for item in triggers] == [True, False, None, None]
    assert triggers[0]["observation"]["source_ref"] == "quarterly#cash-flow"
    assert [item for item in plan["reasons"]["P2"] if item.startswith("TRIGGER_")] == [
        "TRIGGER_FIRED:nonpositive", "TRIGGER_UNKNOWN:revised",
    ]


@pytest.mark.parametrize("operator, threshold, effect", [
    ("<=", None, "block_new_risk"), (None, 0, "block_new_risk"),
    ("<=", "亏损", "block_new_risk"), ("<=", 0, "unknown-effect"),
])
def test_codex_rejects_incomplete_or_contradictory_triggers(tmp_path, snapshot, monkeypatch, operator, threshold, effect):
    trigger = {"id": "cash-flow", "feature": "ocf", "operator": operator, "threshold": threshold,
               "condition": "累计经营现金流小于等于零", "effect": effect,
               "source": "季报", "data_required": "合并现金流量表", "evidence_refs": []}
    install_cli(tmp_path, monkeypatch, FAKE_DRAFT + f'draft["invalidation_triggers"] = [{trigger!r}]\n' + """
Path(sys.argv[sys.argv.index("--output-last-message")+1]).write_text(json.dumps({"draft":draft,"gaps":[]}))
""")
    report = material_file(tmp_path, "季报", excerpt="累计经营现金流量净额为正。")
    receipt = start(tmp_path, snapshot, "--executor", "codex", "--material", report)
    assert receipt["failure_kind"] == "invalid_response" and receipt["draft_version"] is None
