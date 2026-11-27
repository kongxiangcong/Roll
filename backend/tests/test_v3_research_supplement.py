from hashlib import sha256
from pathlib import Path

import pytest

from test_v3_market_research import import_and_freeze, observation
from test_v3_research_tasks import AS_OF, QUESTION, SYMBOL, material_file, snapshot, start, task_cli


def test_supplement_partial_evidence_preserves_parent_and_materials(tmp_path, snapshot):
    report = material_file(tmp_path, "季报", excerpt="本期报告")
    parent = start(tmp_path, snapshot, "--material", report, "--require", "现金流说明",
                   "--require", "对照期报告")
    before = task_cli(tmp_path, "show", parent["task_id"])
    Path(report).unlink()
    note = material_file(tmp_path, "现金流说明", excerpt="销售回款增加")
    child = task_cli(tmp_path, "supplement", parent["task_id"], "--material", note)
    assert child["task_id"] != parent["task_id"]
    assert child["attempt_id"] != parent["attempt_id"]
    assert child["parent_task_id"] == parent["task_id"]
    assert child["status"] == "blocked"
    assert [g["required_evidence"] for g in child["gaps"] if g["blocking"]] == ["对照期报告"]
    assert task_cli(tmp_path, "attempt", child["attempt_id"]) == child
    task = task_cli(tmp_path, "show", child["task_id"])
    assert task["parent_task_id"] == parent["task_id"]
    assert task["attempts"] == [child]
    inherited, extra = task["manifest"]["materials"]
    assert inherited == before["manifest"]["materials"][0]
    assert extra["source"] == "交易所"
    assert extra["document_id"] == "公告-现金流说明"
    assert extra["locator"] == "第三节"
    assert extra["received_at"] == before["manifest"]["as_of"]
    assert extra["sha256"] == sha256("销售回款增加".encode()).hexdigest()
    assert {**task["manifest"], "materials": [inherited]} == before["manifest"]
    assert task_cli(tmp_path, "show", parent["task_id"]) == before


def test_supplement_uses_new_snapshot_and_cutoff(tmp_path, snapshot):
    parent = start(tmp_path, snapshot, "--require", "补充公告", "--require", "审计报告")
    replacement = import_and_freeze(tmp_path, [observation(SYMBOL, "2025-07-22", 23)],
                                    start="2025-07-22", end="2025-07-22")
    later = "2025-07-25T08:00:00.000000+00:00"
    note = material_file(tmp_path, "补充公告", excerpt="次日公告", received_at=later)
    child = task_cli(tmp_path, "supplement", parent["task_id"], "--snapshot", replacement,
                     "--as-of", later, "--material", note)
    actual = task_cli(tmp_path, "show", child["task_id"])["manifest"]
    assert actual["symbol"] == SYMBOL
    assert actual["question"] == QUESTION
    assert actual["snapshot_id"] == actual["market"]["snapshot_id"] == replacement
    assert actual["as_of"] == actual["materials"][0]["received_at"] == later
    original = task_cli(tmp_path, "show", parent["task_id"])["manifest"]
    assert original["snapshot_id"] == original["market"]["snapshot_id"] == snapshot
    assert original["market"]["reference"] != actual["market"]["reference"]


def test_earlier_cutoff_rejects_later_inherited_material(tmp_path, snapshot):
    note = material_file(tmp_path, "补充公告", excerpt="次日公告", received_at="2025-07-26T08:00:00Z")
    parent = task_cli(tmp_path, "run", SYMBOL, "--snapshot", snapshot, "--as-of", "2025-07-26T08:00:00Z",
                      "--question", QUESTION, "--material", note, "--require", "审计报告")
    with pytest.raises(ValueError, match="补充公告.*取得时间晚于"):
        task_cli(tmp_path, "supplement", parent["task_id"], "--as-of", AS_OF)


def test_identical_supplement_requires_a_retry(tmp_path, snapshot):
    note = material_file(tmp_path, "季报", excerpt="现金流增加")
    parent = start(tmp_path, snapshot, "--material", note, "--require", "审计报告")
    with pytest.raises(ValueError, match="重试"):
        task_cli(tmp_path, "supplement", parent["task_id"], "--material", note)
