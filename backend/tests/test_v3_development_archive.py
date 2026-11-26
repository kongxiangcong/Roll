from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import subprocess

import pytest

from roll.v3.storage import sessions
from test_v3_development_attribution import _overlapping_holds
from test_v3_development_inputs import PRESET, command, load_snapshot
from test_v3_development_interpretation import cli, cli_environment, invocation
from test_v3_development_replay import _quotes


def _start(data_dir, rows):
    snapshot = load_snapshot(data_dir, rows)
    return cli(data_dir, "research", "task", "development", "--preset", PRESET, "--snapshot", snapshot,
               "--executor", "offline")


def _archive_arguments(attempt, *, task_id=None, attempt_id=None, report_version=None,
                       conclusion="single_segment", decision="stop", reviewer="审阅工程师",
                       reason="冻结回执中的差异集中在一个对照区段。", extra=()):
    return ("research", "task", "development-archive", task_id or attempt["task_id"],
            "--attempt", attempt_id or attempt["attempt_id"],
            "--report-version", report_version or attempt["report_version"],
            "--conclusion", conclusion, "--reviewer", reviewer, "--decision", decision, "--reason", reason, *extra)


def _reject(data_dir, *arguments):
    result = subprocess.run(invocation(data_dir, *arguments), capture_output=True, text=True,
                            env=cli_environment(), timeout=45)
    assert result.returncode == 2, result
    return result.stderr


def test_archive_binds_an_explicit_report_and_preserves_the_frozen_task(tmp_path):
    _, rows = _overlapping_holds()
    first = _start(tmp_path, rows)
    task_id = first["task_id"]
    frozen = cli(tmp_path, "research", "task", "development-receipt", task_id)
    assert frozen["attribution"]["comparison"]["classification"] == "single_segment"
    second = cli(tmp_path, "research", "task", "retry", task_id, "--executor", "offline")
    before = cli(tmp_path, "research", "task", "show", task_id)
    assert before["archives"] == []
    wrong_report = _reject(tmp_path, *_archive_arguments(first, report_version=second["report_version"]))
    assert "报告版本与所选研究尝试不符" in wrong_report
    wrong_task = _reject(tmp_path, *_archive_arguments(first, task_id="another-task"))
    assert "所选研究尝试不属于此任务" in wrong_task

    archive = cli(tmp_path, *_archive_arguments(first))

    assert {key: archive[key] for key in (
        "task_id", "attempt_id", "report_version", "development_receipt_id", "development_input_ref",
        "reviewer", "conclusion", "decision", "reason",
    )} == {
        "task_id": task_id, "attempt_id": first["attempt_id"], "report_version": first["report_version"],
        "development_receipt_id": frozen["receipt_id"], "development_input_ref": frozen["input_ref"],
        "reviewer": "审阅工程师", "conclusion": "single_segment", "decision": "stop",
        "reason": "冻结回执中的差异集中在一个对照区段。",
    }
    assert datetime.fromisoformat(archive["archived_at"]).tzinfo is not None
    assert cli(tmp_path, "research", "task", "show", task_id) == {**before, "archives": [archive]}
    assert cli(tmp_path, "research", "task", "attempt", first["attempt_id"]) == first
    assert cli(tmp_path, "research", "task", "attempt", second["attempt_id"]) == second
    assert cli(tmp_path, "research", "task", "development-receipt", task_id) == frozen
    error = _reject(tmp_path, "research", "publish", "600362.SH", first["report_version"],
                    "--reviewer", "审阅工程师")
    assert "无此研究草稿" in error


def _separate_holds():
    start = list(sessions("2023-01-03", "2023-12-29"))[-150]
    days, rows = _quotes(start)
    prices = [9] * 59 + [12] * 20 + [8] * 23 + [12] * 22 + [8] * 18 + [12] * 8
    for index in range(len(days)):
        rows[3 * index]["payload"]["close"] = str(prices[index])
        rows[3 * index + 1]["payload"]["close"] = "100"
        opening = str(prices[max(0, index - 1)])
        rows[3 * index + 2]["payload"].update(open=opening, pre_close=opening)
    return rows


def test_continuing_requires_distinct_differentiating_segments_and_a_predeclared_comparison(tmp_path):
    attempt = _start(tmp_path, _separate_holds())
    receipt = command(tmp_path, "research", "task", "development-receipt", attempt["task_id"])
    first, second = (segment["ref"] for segment in receipt["attribution"]["segments"])
    assert (first, second) == ("segment:2023-08-18:2023-10-09", "segment:2023-11-09:2023-12-12")
    sizing = "两组都用期初现金的 50% 作为固定买入目标。"
    measurement = "在独立窗口比较同费率的净收益、最大回撤及入场覆盖率。"
    planned = ("--sizing-rule", sizing, "--measurement", measurement)
    options = {"conclusion": "multiple_segments", "decision": "continue",
               "reason": "两个不重叠区段加回交易成本后仍有差异。"}

    one_segment = _reject(tmp_path, *_archive_arguments(attempt, **options, extra=(
        "--segment-ref", first, "--segment-ref", first, *planned,
    )))
    assert "至少两个" in one_segment
    segment_options = ("--segment-ref", second, "--segment-ref", first)
    missing_basis = _reject(tmp_path, *_archive_arguments(attempt, **options, extra=segment_options))
    assert "预定仓位规则和计量口径" in missing_basis

    archive = cli(tmp_path, *_archive_arguments(attempt, **options, extra=(*segment_options, *planned)))

    assert archive["conclusion"] == "multiple_segments" and archive["decision"] == "continue"
    assert archive["segment_refs"] == [first, second]
    assert archive["next_comparison"] == {"sizing_rule": sizing, "measurement": measurement}
    assert cli(tmp_path, "research", "task", "show", attempt["task_id"])["archives"] == [archive]


def test_concurrent_archive_retries_return_the_original_review_and_reject_revisions(tmp_path):
    _, rows = _overlapping_holds()
    snapshot = load_snapshot(tmp_path, rows)
    attempt = command(tmp_path, "research", "task", "development", "--preset", PRESET, "--snapshot", snapshot,
                      "--executor", "offline")
    arguments = _archive_arguments(attempt)
    with ThreadPoolExecutor(max_workers=2) as processes:
        first = processes.submit(cli, tmp_path, *arguments)
        second = processes.submit(cli, tmp_path, *arguments)
        archive = first.result()
        assert second.result() == archive

    conflict = _reject(tmp_path, *_archive_arguments(attempt, reason="拟覆盖现有审阅理由。"))
    assert "已归档" in conflict
    assert cli(tmp_path, "research", "task", "show", attempt["task_id"])["archives"] == [archive]


@pytest.mark.parametrize(("kind", "conclusion", "reason"), [
    ("matching", "actions_identical", "两组在可评价机会的动作和成交一致。"),
    ("costs", "evidence_insufficient", "逐日加回交易费用及滑点后净值相同，证据不足以扩展。"),
    ("coverage", "evidence_insufficient", "区段估值依据不可用，保留估值缺口。"),
])
def test_descriptive_conclusions_preserve_the_reviewers_reason_and_stop(tmp_path, kind, conclusion, reason):
    days, rows = _overlapping_holds()
    if kind == "matching":
        for index in range(len(days)):
            rows[3 * index + 1]["payload"]["close"] = str(100 + index)
    elif kind == "coverage":
        rows[3 * 65]["quality"] = "unusable"
    else:
        days, rows = _quotes(days[0])
    snapshot = load_snapshot(tmp_path, rows)
    attempt = command(tmp_path, "research", "task", "development", "--preset", PRESET, "--snapshot", snapshot,
                      "--executor", "offline")
    receipt = command(tmp_path, "research", "task", "development-receipt", attempt["task_id"])
    comparison = receipt["attribution"]["comparison"]
    assert comparison["classification"] == {
        "matching": "actions_identical", "costs": "costs_only", "coverage": "evidence_insufficient",
    }[kind]

    denied = _reject(tmp_path, *_archive_arguments(attempt, conclusion=conclusion, decision="continue", reason=reason))
    assert "只有多个不重叠持仓段" in denied
    archive = cli(tmp_path, *_archive_arguments(attempt, conclusion=conclusion, reason=reason))
    assert archive["conclusion"] == conclusion and archive["decision"] == "stop" and archive["reason"] == reason
    assert "next_comparison" not in archive
