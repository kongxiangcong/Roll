"""Record a researcher's review of a specific frozen development report."""
from decimal import Decimal
import json

from roll.v3.development_interpretation import is_development
from roll.v3.development_replay import read_development_receipt
from roll.v3.market import utc_timestamp
from roll.v3.storage import ensure_schema, json_text


CONCLUSIONS = ("actions_identical", "single_segment", "evidence_insufficient", "multiple_segments")
DECISIONS = ("stop", "continue")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS research_development_archive (
    task_id TEXT NOT NULL REFERENCES research_task(task_id),
    attempt_id TEXT NOT NULL REFERENCES research_attempt(attempt_id),
    report_version TEXT NOT NULL,
    archive TEXT NOT NULL,
    PRIMARY KEY (task_id, attempt_id, report_version)
)
"""


def read_development_archives(db, task_id):
    ensure_schema(db, _SCHEMA)
    return [
        json.loads(row["archive"]) for row in db.execute(
            "SELECT archive FROM research_development_archive WHERE task_id=? ORDER BY rowid", (task_id,),
        )
    ]


def _target(db, task_id, attempt_id, report_version):
    row = db.execute(
        "SELECT manifest, receipt FROM research_attempt JOIN research_task USING(task_id) "
        "WHERE task_id=? AND attempt_id=?", (task_id, attempt_id),
    ).fetchone()
    if row is None:
        raise ValueError("所选研究尝试不属于此任务")
    if not is_development(json.loads(row["manifest"])):
        raise ValueError("此命令仅归档开发实验报告")
    attempt = json.loads(row["receipt"])
    if attempt["status"] != "report_ready":
        raise ValueError("所选尝试还没有可归档的开发报告")
    report = attempt["report"]
    if (attempt["report_version"] != report_version or report["version"] != report_version
            or report["attempt_id"] != attempt_id):
        raise ValueError("报告版本与所选研究尝试不符")
    return attempt


def _differentiating_segment(segment):
    net = segment["net_difference"]
    if net is None or Decimal(net) == 0:
        return False
    return Decimal(net) + Decimal(segment["cost_difference"]) + Decimal(segment["slippage_difference"]) != 0


def _review_details(receipt, conclusion, decision, segment_refs, sizing_rule, measurement):
    multiple_segments = conclusion == "multiple_segments"
    if decision == "continue":
        if not multiple_segments:
            raise ValueError("只有多个不重叠持仓段仍有待解释差异时才能继续")
        if not sizing_rule or not measurement:
            raise ValueError("继续须提供预定仓位规则和计量口径")
    elif sizing_rule is not None or measurement is not None:
        raise ValueError("停止时不登记下一项仓位对照")

    if not multiple_segments:
        if segment_refs:
            raise ValueError("仅多段结论需要指定待解释的持仓段")
        return {}

    if len(segment_refs) < 2 or len(set(segment_refs)) != len(segment_refs):
        raise ValueError("多段结论须引用至少两个不同的冻结对照区段")
    candidates = {segment["ref"]: segment for segment in receipt.get("attribution", {}).get("segments", [])}
    segments = []
    for ref in segment_refs:
        segment = candidates.get(ref)
        if segment is None or not _differentiating_segment(segment):
            raise ValueError(f"对照区段缺少可复核且超出交易费用及滑点的差异：{ref}")
        segments.append(segment)
    segments.sort(key=lambda segment: segment["start"])
    if any(left["end"] >= right["start"] for left, right in zip(segments, segments[1:])):
        raise ValueError("待解释的对照区段不得重叠")

    details = {"segment_refs": [segment["ref"] for segment in segments]}
    if decision == "continue":
        details["next_comparison"] = {"sizing_rule": sizing_rule, "measurement": measurement}
    return details


def archive_development(data_dir, task_id, attempt_id, report_version, *, conclusion, reviewer, decision, reason,
                        segment_refs=(), sizing_rule=None, measurement=None):
    from roll.v3.research_tasks import task_database

    reviewer, reason = reviewer.strip(), reason.strip()
    if not reviewer or not reason:
        raise ValueError("归档须提供审阅人和停止或继续的理由")
    if conclusion not in CONCLUSIONS or decision not in DECISIONS:
        raise ValueError("未知结论或停止与继续决定")

    with task_database(data_dir, write=True) as db:
        attempt = _target(db, task_id, attempt_id, report_version)
        receipt = read_development_receipt(data_dir, task_id, db=db)
        if (attempt["report"]["receipt_id"] != receipt["receipt_id"]
                or attempt["development_receipt_id"] != receipt["receipt_id"]
                or attempt["development_input_ref"] != receipt["input_ref"]):
            raise ValueError("所选报告与此任务的冻结开发回执或输入不符")
        details = _review_details(receipt, conclusion, decision, segment_refs,
                                  sizing_rule.strip() if sizing_rule is not None else None,
                                  measurement.strip() if measurement is not None else None)
        archive = {
            "task_id": task_id, "attempt_id": attempt_id, "report_version": report_version,
            "development_receipt_id": receipt["receipt_id"], "development_input_ref": receipt["input_ref"],
            "conclusion": conclusion, "reviewer": reviewer, "decision": decision, "reason": reason,
            **details,
        }
        ensure_schema(db, _SCHEMA)
        key = (task_id, attempt_id, report_version)
        previous = db.execute(
            "SELECT archive FROM research_development_archive WHERE task_id=? AND attempt_id=? AND report_version=?", key,
        ).fetchone()
        if previous is not None:
            stored = json.loads(previous["archive"])
            if stored == {**archive, "archived_at": stored["archived_at"]}:
                return stored
            raise ValueError("所选报告已归档，审阅记录不可更改")
        archive["archived_at"] = utc_timestamp(None)
        db.execute("INSERT INTO research_development_archive VALUES (?, ?, ?, ?)", (*key, json_text(archive)))
    return archive
