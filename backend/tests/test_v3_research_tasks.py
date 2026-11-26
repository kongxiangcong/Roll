import base64
import json
from hashlib import sha256

import pytest

from roll.v3.cli import run
from test_v3_market_research import import_and_freeze, observation


SYMBOL = "600362.SH"
AS_OF = "2025-07-24T16:00:00+08:00"
QUESTION = "核对经营现金流变化原因"


@pytest.fixture
def snapshot(tmp_path):
    return import_and_freeze(tmp_path, [observation(SYMBOL, "2025-07-21", 21.5)],
                             start="2025-07-21", end="2025-07-21")


def task_cli(data_dir, *args):
    return run(["research", "task", *args], data_dir=data_dir)


def start(data_dir, snapshot, *args):
    return task_cli(data_dir, "run", SYMBOL, "--snapshot", snapshot, "--as-of", AS_OF,
                    "--question", QUESTION, *args)


def test_blocked_task_replays_public_inputs_and_gap(tmp_path, snapshot):
    receipt = start(tmp_path, snapshot, "--require", "经营现金流说明公告")
    assert receipt["status"] == "blocked"
    assert receipt["draft_version"] is None
    assert receipt["gaps"][0]["required_evidence"] == "经营现金流说明公告"
    assert receipt["gaps"][0]["reason"]
    assert task_cli(tmp_path, "attempt", receipt["attempt_id"]) == receipt
    task = task_cli(tmp_path, "show", receipt["task_id"])
    assert task_cli(tmp_path, "show", receipt["task_id"]) == task
    assert task["attempts"] == [receipt]
    manifest = task["manifest"]
    assert manifest["question"] == QUESTION
    assert manifest["symbol"] == SYMBOL
    assert manifest["as_of"].startswith("2025-07-24T08:00")
    assert manifest["snapshot_id"] == snapshot
    market = manifest["market"]
    assert manifest["purpose"] == market["snapshot"]["use_mode"]
    assert market["securities"][SYMBOL]["observations"][0]["payload"]["close"] == "21.5"
    assert market["reference"].startswith("market-research:")


def material_file(directory, name, **fields):
    path = directory / f"{name}.json"
    path.write_text(json.dumps({"title": name, "source": "交易所", "locator": "第三节",
                               "document_id": "公告-" + name, "received_at": AS_OF, **fields}))
    return str(path)


def test_frozen_file_and_excerpt_survive_source_edits(tmp_path, snapshot):
    binary = b"%PDF-1.5\n\xff"
    path = tmp_path / "cashflow.pdf"
    path.write_bytes(binary)
    report = material_file(tmp_path, "季报", file=path.name)
    note = material_file(tmp_path, "补充说明", excerpt="经营活动现金流量净额")
    receipt = start(tmp_path, snapshot, "--material", report, "--material", note,
                    "--require", "季报", "--require", "年度审计报告")
    assert [g["required_evidence"] for g in receipt["gaps"]] == ["年度审计报告"]
    path.write_text("已更新")
    task = task_cli(tmp_path, "show", receipt["task_id"])
    original, excerpt = task["manifest"]["materials"]
    assert base64.b64decode(original["content"]) == binary
    assert original["sha256"] == sha256(binary).hexdigest()
    assert excerpt["content"] == "经营活动现金流量净额"
    assert excerpt["locator"] == "第三节"
    assert excerpt["sha256"] == sha256("经营活动现金流量净额".encode()).hexdigest()


@pytest.mark.parametrize("updates, message", [
    ({"title": ""}, "title"), ({"source": ""}, "source"), ({"locator": ""}, "locator"),
    ({"document_id": ""}, "url"), ({"received_at": ""}, "received_at"),
    ({"received_at": "2025-07-24T09:00:00Z"}, "截止时点"),
])
def test_rejects_unverifiable_or_late_material(tmp_path, snapshot, updates, message):
    path = material_file(tmp_path, "公告", excerpt="经营现金流", **updates)
    with pytest.raises(ValueError, match=message):
        start(tmp_path, snapshot, "--material", path)


def test_executor_sees_only_frozen_public_inputs(tmp_path, monkeypatch, snapshot):
    from test_v3_account import account, BASELINE
    from roll.v3.research_tasks import run_task

    marker = "private-broker-lot"
    account(tmp_path, monkeypatch, "init", payload={**BASELINE, "lots": [{**BASELINE["lots"][0], "lot_id": marker}]})
    assert marker in json.dumps(account(tmp_path, monkeypatch, "show", "--as-of", AS_OF))
    material = material_file(tmp_path, "季报", excerpt="经营现金流为正", internal_note=marker)
    seen = []

    def executor(manifest):
        seen.append(manifest)
        return {"gaps": [{"reason": "缺少对照期", "required_evidence": "上期季报", "blocking": True}]}

    receipt = run_task(tmp_path, SYMBOL, question=QUESTION, as_of=AS_OF, snapshot_id=snapshot,
                       materials=[material], executor=executor)
    assert receipt["status"] == "blocked"
    assert seen == [task_cli(tmp_path, "show", receipt["task_id"])["manifest"]]
    assert marker not in json.dumps(seen)
    assert seen[0]["dossier"] is None
    assert seen[0]["materials"][0]["content"] == "经营现金流为正"


def test_material_alone_delivers_versioned_draft_without_a_prior_publication(tmp_path, snapshot):
    path = material_file(tmp_path, "季报", excerpt="销售回款增加")
    receipt = start(tmp_path, snapshot, "--material", path)
    assert receipt["status"] == "draft_ready"
    task = task_cli(tmp_path, "show", receipt["task_id"])
    assert task["attempts"] == [task_cli(tmp_path, "attempt", receipt["attempt_id"])]
    material, = task["manifest"]["materials"]
    draft = run(["research", "show", SYMBOL, "--draft", "--version", receipt["draft_version"]],
                data_dir=tmp_path)
    evidence, = draft["evidence"]
    assert draft["evidence_refs"] == [material["id"]]
    assert evidence["locator"] == "第三节"
    assert evidence["sha256"] == sha256("销售回款增加".encode()).hexdigest()
    assert draft["task_id"] == receipt["task_id"]
    assert draft["attempt_id"] == receipt["attempt_id"]
    assert "销售回款增加" in draft["markdown"]


def test_preflight_gap_survives_executor_that_reports_only_other_gaps(tmp_path, snapshot):
    from roll.v3.research_tasks import run_task

    def executor(manifest):
        return {"gaps": [{"reason": "缺少对照期", "required_evidence": "上期季报", "blocking": False}]}

    receipt = run_task(tmp_path, SYMBOL, question=QUESTION, as_of=AS_OF, snapshot_id=snapshot,
                       required_titles=["本期季报"], executor=executor)
    assert receipt["status"] == "blocked"
    assert {gap["required_evidence"]: gap["blocking"] for gap in receipt["gaps"]} == {
        "本期季报": True, "上期季报": False}


def test_draft_explains_nonblocking_limitation_on_industry_comparison(tmp_path, snapshot):
    path = material_file(tmp_path, "季报", excerpt="销售回款增加")
    receipt = start(tmp_path, snapshot, "--material", path)
    draft = run(["research", "show", SYMBOL, "--draft", "--version", receipt["draft_version"]],
                data_dir=tmp_path)
    gap, = receipt["gaps"]
    assert gap["blocking"] is False
    assert "行业" in gap["reason"]
    assert draft["gaps"] == [gap]


@pytest.mark.parametrize("invalid, reason", [
    ("symbol", "标的"), ("as_of", "截止时点"), ("received_at", "取得时间"),
    ("foreign_material", "清单"), ("mutated_locator", "清单"), ("missing_ref", "未登记"),
    ("trigger_ref", "未登记"), ("empty_evidence", "证据"),
])
def test_invalid_executor_draft_leaves_readable_failure(tmp_path, snapshot, invalid, reason):
    from roll.v3.research_tasks import offline_executor, run_task

    def executor(manifest):
        if invalid == "mutated_locator":
            manifest["materials"][0]["locator"] = "伪造章节"
        result = offline_executor(manifest)
        draft = result["draft"]
        if invalid == "symbol":
            draft["symbol"] = "000001.SZ"
        if invalid == "as_of":
            draft["as_of"] = "2025-07-25T00:00:00Z"
        if invalid == "received_at":
            draft["evidence"][0]["received_at"] = "2025-07-25T00:00:00Z"
        if invalid == "foreign_material":
            draft["evidence"][0]["id"] = "material-from-another-manifest"
            draft["evidence_refs"] = [draft["evidence"][0]["id"]]
        if invalid == "missing_ref":
            draft["evidence_refs"] = ["missing"]
        if invalid == "trigger_ref":
            draft["invalidation_triggers"] = [{"evidence_refs": ["missing"]}]
        if invalid == "empty_evidence":
            draft.update(evidence=[], evidence_refs=[])
        return result

    path = material_file(tmp_path, "季报", excerpt="销售回款增加")
    receipt = run_task(tmp_path, SYMBOL, question=QUESTION, as_of=AS_OF, snapshot_id=snapshot,
                       materials=[path], executor=executor)
    assert receipt["status"] == "failed"
    assert reason in receipt["error"]
    assert task_cli(tmp_path, "attempt", receipt["attempt_id"]) == receipt
    assert receipt["draft_version"] is None
    assert run(["research", "show", SYMBOL, "--draft"], data_dir=tmp_path) is None


def test_failed_receipt_write_rolls_back_draft(tmp_path, snapshot):
    import sqlite3
    from roll.v3.research_tasks import offline_executor, run_task

    def executor(manifest):
        with sqlite3.connect(tmp_path / "roll-v3.sqlite3") as db:
            db.execute("""
                CREATE TRIGGER simulate_full_disk BEFORE UPDATE ON research_attempt
                WHEN json_extract(NEW.receipt, '$.status') = 'draft_ready'
                BEGIN SELECT RAISE(ABORT, 'simulated full disk'); END
            """)
        return offline_executor(manifest)

    path = material_file(tmp_path, "季报", excerpt="销售回款增加")
    receipt = run_task(tmp_path, SYMBOL, question=QUESTION, as_of=AS_OF, snapshot_id=snapshot,
                       materials=[path], executor=executor)
    assert receipt["status"] == "failed"
    assert "simulated full disk" in receipt["error"]
    assert task_cli(tmp_path, "attempt", receipt["attempt_id"]) == receipt
    assert run(["research", "show", SYMBOL, "--draft"], data_dir=tmp_path) is None


@pytest.mark.parametrize("late_result", ["failure", "blocked", "draft"])
def test_late_callback_preserves_first_committed_result(tmp_path, snapshot, monkeypatch, late_result):
    from uuid import UUID
    from roll.v3 import research_tasks

    ids = iter([UUID(int=1), UUID(int=2)])
    monkeypatch.setattr(research_tasks, "uuid4", lambda: next(ids))
    attempt_id = "attempt-" + UUID(int=2).hex
    first = []

    def slower_executor(manifest):
        first.append(research_tasks.execute_attempt(tmp_path, attempt_id))
        if late_result == "draft":
            result = research_tasks.offline_executor(manifest)
            result["draft"]["markdown"] = "第二次回包"
            return result
        if late_result == "failure":
            raise ValueError("过期执行失败")
        return {"gaps": [{"blocking": True, "required_evidence": "旧材料", "reason": "迟到回包"}]}

    path = material_file(tmp_path, "季报", excerpt="销售回款增加")
    receipt = research_tasks.run_task(tmp_path, SYMBOL, question=QUESTION, as_of=AS_OF,
                                      snapshot_id=snapshot, materials=[path], executor=slower_executor)
    assert receipt == first[0] == task_cli(tmp_path, "attempt", attempt_id)
    assert receipt["status"] == "draft_ready"
    draft = run(["research", "show", SYMBOL, "--draft", "--version", receipt["draft_version"]],
                data_dir=tmp_path)
    assert "销售回款增加" in draft["markdown"]
    assert "第二次回包" not in draft["markdown"]


def test_retry_keeps_frozen_inputs_and_can_publish_earlier_attempt(tmp_path, snapshot):
    from datetime import UTC, datetime
    from pathlib import Path

    path = material_file(tmp_path, "季报", excerpt="销售回款增加")
    cutoff = datetime.now(UTC).isoformat()
    first = task_cli(tmp_path, "run", SYMBOL, "--snapshot", snapshot, "--as-of", cutoff,
                     "--question", QUESTION, "--material", path)
    task_id = first["task_id"]
    manifest = task_cli(tmp_path, "show", task_id)["manifest"]

    def dossier(*args):
        return run(["research", "show", SYMBOL, *args], data_dir=tmp_path)

    first_draft = dossier("--draft", "--version", first["draft_version"])
    Path(path).unlink()
    second = task_cli(tmp_path, "retry", task_id)
    assert first["draft_version"] != second["draft_version"]
    assert first["attempt_id"] != second["attempt_id"]
    assert task_cli(tmp_path, "show", task_id) == {
        "task_id": task_id, "parent_task_id": None, "manifest": manifest, "attempts": [first, second]}
    second_draft = dossier("--draft", "--version", second["draft_version"])
    assert second_draft["evidence"] == first_draft["evidence"]
    assert dossier("--draft", "--version", first["draft_version"]) == first_draft

    published = run(["research", "publish", SYMBOL, first["draft_version"], "--reviewer", "研究者"],
                    data_dir=tmp_path)
    assert published["reviewer"] == "研究者"
    assert published["published_at"] == published["effective_at"] < published["valid_until"]
    assert published["task_id"] == task_id
    assert published["attempt_id"] == first["attempt_id"]
    assert dossier("--version", first["draft_version"]) == dossier() == published
    assert dossier("--draft", "--version", second["draft_version"]) == second_draft
    assert dossier("--version", second["draft_version"]) is None


def test_manual_import_cannot_replace_a_task_owned_draft(tmp_path, snapshot):
    path = material_file(tmp_path, "季报", excerpt="销售回款增加")
    receipt = start(tmp_path, snapshot, "--material", path)
    version = receipt["draft_version"]
    show = ["research", "show", SYMBOL, "--draft", "--version", version]
    reviewed = run(show, data_dir=tmp_path)
    replacement = tmp_path / "manual.md"
    replacement.write_text(f"---\nversion: {version}\n---\n替换原文")
    with pytest.raises(ValueError, match="不可覆盖"):
        run(["research", "draft", SYMBOL, str(replacement)], data_dir=tmp_path)
    assert run(show, data_dir=tmp_path) == reviewed
    assert task_cli(tmp_path, "attempt", receipt["attempt_id"]) == receipt


def test_manual_import_cannot_claim_task_provenance(tmp_path):
    path = tmp_path / "manual.md"
    path.write_text("---\nversion: manual\ntask_id: old-task\nattempt_id: old-attempt\n---\n正文")
    with pytest.raises(ValueError, match="来源"):
        run(["research", "draft", SYMBOL, str(path)], data_dir=tmp_path)
    assert run(["research", "show", SYMBOL, "--draft"], data_dir=tmp_path) is None


def test_attempts_assign_independent_versions_to_same_named_executor_results(tmp_path, snapshot):
    from roll.v3.research_tasks import offline_executor, retry_task, run_task

    def named_executor(manifest):
        result = offline_executor(manifest)
        result["draft"]["version"] = "研究桩草稿"
        return result

    path = material_file(tmp_path, "季报", excerpt="销售回款增加")
    first = run_task(tmp_path, SYMBOL, question=QUESTION, as_of=AS_OF, snapshot_id=snapshot,
                     materials=[path], executor=named_executor)
    second = retry_task(tmp_path, first["task_id"], executor=named_executor)
    versions = {first["draft_version"], second["draft_version"]}
    assert len(versions) == 2 and "研究桩草稿" not in versions
    for receipt in (first, second):
        draft = run(["research", "show", SYMBOL, "--draft", "--version", receipt["draft_version"]],
                    data_dir=tmp_path)
        assert draft["attempt_id"] == receipt["attempt_id"]
