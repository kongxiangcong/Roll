"""Freeze the public inputs to one offline research question and record each attempt."""
import base64
import json
import time
import sys
import re
import shutil
import sqlite3
from contextlib import ExitStack, contextmanager
from copy import deepcopy
from datetime import timedelta
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

from roll.v3.development_interpretation import (
    is_development, offline_interpretation, prepare_development_report, public_development_input,
)
from roll.v3.research_harness import ResearchHarness, HarnessFailure
from roll.v3.research_lifecycle import AttemptStopped, ProcessConfigurationError, attempt_lock, run_process
from roll.v3.market import utc_timestamp
from roll.v3.market_research import export_market_research
from roll.v3.research import ResearchDossiers, material_evidence, prepare_task_draft
from roll.v3.storage import database, ensure_schema, instant, json_text


_SCHEMA = """
CREATE TABLE IF NOT EXISTS research_task (
    task_id TEXT PRIMARY KEY,
    manifest TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS research_task_parent (
    task_id TEXT PRIMARY KEY REFERENCES research_task(task_id),
    parent_task_id TEXT NOT NULL REFERENCES research_task(task_id)
);
CREATE TABLE IF NOT EXISTS research_attempt (
    attempt_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL REFERENCES research_task(task_id),
    receipt TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS research_attempt_task ON research_attempt(task_id);
CREATE TABLE IF NOT EXISTS research_development_public_input (
    task_id TEXT PRIMARY KEY REFERENCES research_task(task_id),
    public_input TEXT NOT NULL
)
"""


@contextmanager
def task_database(data_dir, *, write=False):
    with database(data_dir, write=write) as db:
        ensure_schema(db, _SCHEMA)
        yield db


def get_task(data_dir, task_id):
    from roll.v3.development_archive import read_development_archives

    with task_database(data_dir) as db:
        row = db.execute(
            "SELECT manifest, parent_task_id FROM research_task "
            "LEFT JOIN research_task_parent USING(task_id) WHERE task_id=?", (task_id,)
        ).fetchone()
        if not row:
            raise ValueError(f"无此研究任务：{task_id}")
        task = {"task_id": task_id, "parent_task_id": row["parent_task_id"], "manifest": json.loads(row["manifest"])}
        if is_development(task["manifest"]):
            # Read archives first so every archived attempt appears in the subsequent attempt list.
            task["archives"] = read_development_archives(db, task_id)
        attempts = db.execute(
            "SELECT receipt FROM research_attempt WHERE task_id=? ORDER BY rowid", (task_id,)
        ).fetchall()
    task["attempts"] = [read_receipt(data_dir, json.loads(item["receipt"])) for item in attempts]
    return task


def get_attempt(data_dir, attempt_id):
    with task_database(data_dir) as db:
        row = db.execute("SELECT receipt FROM research_attempt WHERE attempt_id=?", (attempt_id,)).fetchone()
    if not row:
        raise ValueError(f"无此研究尝试：{attempt_id}")
    return read_receipt(data_dir, json.loads(row["receipt"]))


_DEFAULT_HARNESS = object()
ACTIVE = ("running", "cancelling", "pending")
ACTIVE_PARAMS = ", ".join("?" for _ in ACTIVE)


def abandon(db, receipt):
    if receipt["status"] == "cancelling":
        return store_receipt(db, cancelled(receipt))
    return store_receipt(db, {**receipt, "status": "interrupted", "termination_reason": "interrupted",
                              "error": "执行者已退出，研究尝试中断"})


def read_receipt(data_dir, receipt):
    # Stage 01 had neither an owner lock nor a process identity to check.
    if receipt["status"] in ACTIVE and receipt.get("receipt_version") == 2:
        with attempt_lock(data_dir, receipt["attempt_id"], observe=True) as lock:
            if lock is not None:
                if receipt.get("supervised") or receipt.get("executor") == "codex":
                    # Only a dead Roll owner's read waits. Its orphaned subreaper holds
                    # the child lock until every descendant has actually been reaped.
                    with attempt_lock(data_dir, receipt["attempt_id"], children=True, wait=True):
                        if re.fullmatch(r"attempt-[0-9a-f]{32}", receipt["attempt_id"]):
                            runtime = Path(data_dir) / "research-attempts" / receipt["attempt_id"] / "runtime"
                            if runtime.exists():
                                shutil.rmtree(runtime)
                with task_database(data_dir, write=True) as db:
                    row = db.execute("SELECT receipt FROM research_attempt WHERE attempt_id=?",
                                     (receipt["attempt_id"],)).fetchone()
                    current = json.loads(row["receipt"])
                    return abandon(db, current) if current["status"] in ACTIVE else current
    return receipt


def store_receipt(db, receipt):
    db.execute("UPDATE research_attempt SET receipt=? WHERE attempt_id=?",
               (json_text(receipt), receipt["attempt_id"]))
    return receipt


def cancelled(receipt):
    return {**receipt, "status": "cancelled", "termination_reason": "cancelled", "error": "用户取消了研究尝试"}


def cancel_attempt(data_dir, attempt_id):
    with task_database(data_dir, write=True) as db:
        row = db.execute("SELECT receipt FROM research_attempt WHERE attempt_id=?", (attempt_id,)).fetchone()
        if not row:
            raise ValueError(f"无此研究尝试：{attempt_id}")
        receipt = json.loads(row["receipt"])
        if receipt["status"] == "running" and receipt.get("receipt_version") != 2:
            # A stage 01 offline executor uses the same commit-time status check.
            return store_receipt(db, cancelled(receipt))
        if receipt["status"] == "running":
            with attempt_lock(data_dir, attempt_id, observe=True) as vacant:
                if vacant is None:
                    receipt["status"] = "cancelling"
                    store_receipt(db, receipt)
        elif receipt["status"] == "pending":
            return store_receipt(db, cancelled(receipt))
    if receipt["status"] == "running":
        return read_receipt(data_dir, receipt)
    while receipt["status"] == "cancelling":
        time.sleep(0.05)
        receipt = get_attempt(data_dir, attempt_id)
    return receipt


def freeze_material(path, cutoff):
    path = Path(path)
    item = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(item, dict):
        raise ValueError("公告材料须为 JSON 对象")
    fields = ("title", "source", "locator", "url", "document_id", "received_at")
    metadata = {key: item[key].strip() for key in fields
                if isinstance(item.get(key), str) and item[key].strip()}
    for key in ("title", "source", "locator", "received_at"):
        if key not in metadata:
            raise ValueError(f"公告材料缺少 {key}")
    if not (metadata.get("url") or metadata.get("document_id")):
        raise ValueError("公告材料须提供 url 或 document_id")
    metadata["received_at"] = utc_timestamp(metadata["received_at"])
    if metadata["received_at"] > cutoff:
        raise ValueError(f'公告「{metadata["title"]}」取得时间晚于任务截止时点')
    if ("file" in item) == ("excerpt" in item):
        raise ValueError("每份公告须提供 file 或 excerpt 其中之一")
    if "file" in item:
        if not isinstance(item["file"], str) or not item["file"].strip():
            raise ValueError("file 须指定本地文件")
        raw = (path.parent / item["file"]).read_bytes()
        try:
            content, encoding = raw.decode("utf-8"), "utf-8"
        except UnicodeDecodeError:
            content, encoding = base64.b64encode(raw).decode("ascii"), "base64"
    else:
        content = item["excerpt"]
        if not isinstance(content, str) or not content.strip():
            raise ValueError("excerpt 须提供原文")
        raw, encoding = content.encode("utf-8"), "utf-8"
    if not raw:
        raise ValueError("公告文件为空")
    metadata["sha256"] = sha256(raw).hexdigest()
    reference = sha256(json_text(metadata).encode()).hexdigest()
    return {**metadata, "id": "material-" + reference, "content": content, "encoding": encoding}


def collect_materials(paths, cutoff, inherited=()):
    by_id = {item["id"]: item for item in inherited}
    for item in inherited:
        if item["received_at"] > cutoff:
            raise ValueError(f'公告「{item["title"]}」取得时间晚于任务截止时点')
    for path in paths:
        item = freeze_material(path, cutoff)
        by_id[item["id"]] = item
    return list(by_id.values())


BASIS = {
    "announcement": "公开公告",
    "stock-close": "最近交易日的有效个股收盘价",
    "industry-comparison": "最近五个交易日同区间的个股、行业指数行情和成分归属",
}


def freeze_manifest(data_dir, symbol, *, question, snapshot_id, as_of, materials=(), required_titles=(), basis=None):
    if not question.strip() or not symbol.strip() or not as_of:
        raise ValueError("研究任务须提供标的、问题和截止时点")
    symbol = symbol.strip().upper()
    cutoff = utc_timestamp(as_of)
    if basis is None:
        market_terms = ("行业", "收盘", "行情", "股价", "涨跌", "大盘", "基准", "跑赢", "跑输",
                        "industry", "sector", "close", "stock price", "market", "benchmark")
        if any(term in question.lower() for term in market_terms):
            raise ValueError("请用 --basis 指明依据：stock-close 核对最近收盘价，industry-comparison 核对五日行业"
                             "相对收益，announcement 核对公告。")
        basis = "announcement"
    if basis not in BASIS:
        raise ValueError("未知研究依据：" + basis)
    titles = [title.strip() for title in required_titles]
    if any(not title for title in titles):
        raise ValueError("必要公告标题为空")
    market = export_market_research(data_dir, symbol, snapshot_id=snapshot_id, as_of=cutoff)
    return {
        "symbol": symbol, "question": question.strip(), "as_of": cutoff, "snapshot_id": snapshot_id,
        "basis": basis, "purpose": market["snapshot"]["use_mode"], "market": market,
        "dossier": ResearchDossiers(data_dir).public_version(symbol, cutoff),
        "required_titles": list(dict.fromkeys(titles)),
        "materials": collect_materials(materials, cutoff),
    }


def market_finding(manifest):
    finding = market_observations(manifest)
    return finding[:2] if finding else None


def market_observations(manifest):
    if manifest.get("basis", "announcement") == "announcement":
        return None
    market = manifest["market"]
    periods = market["industry_comparisons"]
    if not periods:
        return None
    period = periods[-1]
    day = period["end"]
    basis = manifest["basis"]
    if basis == "industry-comparison":
        if period["kind"] != "industry_index":
            return None
        window = period["stock_relative_windows"]["5"]
        if window["status"] != "usable":
            return None
        index = period["symbol"]
        start = window["start"]
        observations = [row for code in (manifest["symbol"], index)
                        for series in ("observations", "adjustment_factors")
                        for row in market["securities"][code][series] if start <= row["trade_date"] <= day]
        membership = next(row for row in market["industry_memberships"] if row["seq"] == period["membership_seq"])
        observations.append(membership)
        locator = f'industry_comparisons: {index}, {start} 至 {day}, stock_relative_windows/5'
        summary = f'{start} 至 {day} 相对 {index} 的五日收益率差为 {window["relative_return"] * 100:.2f} 个百分点。'
        return market_citation(manifest, locator, observations, summary)

    security = market["securities"][manifest["symbol"]]
    coverage = security["coverage"]
    if day in coverage["unusable_dates"] or day in coverage["suspended_dates"]:
        return None
    quote = next((row for row in security["observations"] if row["trade_date"] == day), None)
    if not quote:
        return None
    locator = f'{manifest["symbol"]} 日线 {day} seq={quote["seq"]}'
    summary = f'{day} 收盘价：{quote["payload"]["close"]} {quote["unit"].get("price", "")}'.rstrip()
    return market_citation(manifest, locator, [quote], summary)


def market_citation(manifest, locator, rows, summary):
    received_at = max(row["received_at"] for row in rows)
    if received_at > manifest["as_of"]:
        return None
    basis = manifest["basis"]
    reference = manifest["market"]["reference"]
    evidence = {"id": reference + "#" + basis, "title": BASIS[basis], "locator": locator,
                "source": "、".join(sorted({row["source"] for row in rows})), "document_id": reference,
                "received_at": received_at}
    return evidence, summary, rows


def preflight_gaps(manifest):
    titles = {item["title"] for item in manifest["materials"]}
    needed = manifest["required_titles"]
    if manifest.get("basis", "announcement") == "announcement" and not titles and not needed:
        needed = [f'可核对「{manifest["question"]}」的公开公告']
    gaps = [{"reason": "缺少回答本问题所需的公告原文或可定位摘录",
             "required_evidence": title, "blocking": True} for title in needed if title not in titles]
    if manifest.get("basis", "announcement") != "announcement" and not market_finding(manifest):
        gaps.append({"reason": "截止时点的冻结行情缺少本问题所需数据",
                     "required_evidence": BASIS[manifest["basis"]], "blocking": True})
    return gaps


def offline_executor(manifest):
    if preflight_gaps(manifest):
        return {"gaps": []}
    gaps = []
    periods = manifest["market"]["industry_comparisons"]
    if manifest.get("basis", "announcement") == "announcement" and (
        not periods or any(item["kind"] != "industry_index" for item in periods)
    ):
        gaps.append({"required_evidence": "完整的行业指数行情与成分归属",
                     "reason": "部分日期缺少行业对照，草稿仅核对公告，无法据此判断相对行业表现",
                     "blocking": False})
    evidence = [material_evidence(item) for item in manifest["materials"]]
    lines = [f'# {manifest["question"]}', "", "离线执行桩汇集的公开材料，供人工核对。"]
    finding = market_finding(manifest)
    if finding:
        evidence.append(finding[0])
        lines.extend(["", finding[1]])
    for item in manifest["materials"]:
        lines.extend(["", f'## {item["title"]}（{item["locator"]}）',
                      item["content"] if item["encoding"] == "utf-8" else "原文件见冻结清单。"])
    return {"gaps": gaps, "draft": {
        "symbol": manifest["symbol"], "as_of": manifest["as_of"],
        "valid_until": (instant(manifest["as_of"]) + timedelta(days=30)).isoformat(),
        "evidence": evidence, "evidence_refs": [item["id"] for item in evidence],
        "markdown": "\n".join(lines),
    }}


def execute_attempt(data_dir, attempt_id, *, executor=None):
    # Stage 01 registered a pending row in a transaction prior to claiming it.
    # Modern registrations are already running by the time another caller can read them.
    if get_attempt(data_dir, attempt_id)["status"] == "pending":
        with attempt_lock(data_dir, attempt_id) as lock:
            if lock is not None:
                with task_database(data_dir, write=True) as db:
                    row = db.execute(
                        "SELECT receipt, manifest FROM research_attempt JOIN research_task USING(task_id) "
                        "WHERE attempt_id=?", (attempt_id,),
                    ).fetchone()
                    receipt = json.loads(row["receipt"])
                    if receipt["status"] != "pending":
                        return receipt
                    ensure_no_other_owner(db, receipt["task_id"], attempt_id)
                    prepare_claim(data_dir, receipt, row["manifest"], executor)
                    store_receipt(db, receipt)
                if receipt["status"] == "running":
                    return run_claimed(data_dir, receipt, row["manifest"], executor)
                return receipt
    return get_attempt(data_dir, attempt_id)


def ensure_no_other_owner(db, task_id, attempt_id):
    active = db.execute(
        "SELECT attempt_id FROM research_attempt WHERE task_id=? AND attempt_id!=? "
        f"AND json_extract(receipt, '$.status') IN ({ACTIVE_PARAMS})", (task_id, attempt_id, *ACTIVE),
    ).fetchone()
    if active:
        raise ValueError(f"研究任务已有进行中的尝试：{active['attempt_id']}")


def prepare_claim(data_dir, receipt, frozen, executor):
    receipt.update(status="running", receipt_version=2, manifest_sha256=sha256(frozen.encode()).hexdigest())
    if isinstance(executor, ResearchHarness):
        if not re.fullmatch(r"attempt-[0-9a-f]{32}", receipt["attempt_id"]):
            raise ValueError("尝试 ID 无法用于受限研究执行")
        try:
            receipt.update(executor.initial_receipt(data_dir, receipt["attempt_id"]))
        except OSError as error:
            receipt.update(executor=executor.name, supervised=True, status="failed", failure_kind="configuration",
                           log_ref=None, exit_code=None, error=f"无法创建尝试日志（errno={error.errno}）")


def run_claimed(data_dir, receipt, frozen, executor, *, development_public=None):
    attempt_id = receipt["attempt_id"]
    external = isinstance(executor, ResearchHarness)
    deadline = time.monotonic() + executor.timeout if external else None

    def check_state():
        with task_database(data_dir) as db:
            row = db.execute("SELECT json_extract(receipt, '$.status') FROM research_attempt WHERE attempt_id=?",
                             (attempt_id,)).fetchone()
        if row[0] == "cancelling":
            raise AttemptStopped("cancelled", "用户取消了研究尝试")
        if time.monotonic() >= deadline:
            raise AttemptStopped("timed_out", "研究尝试超过配置的时限")

    def supervised(argv, **kwargs):
        # Publish new metadata (e.g. verified CLI version) before the next command waits.
        with task_database(data_dir, write=True) as db:
            db.execute("UPDATE research_attempt SET receipt=? WHERE attempt_id=? "
                       "AND json_extract(receipt, '$.status')='running'", (json_text(receipt), attempt_id))
        with attempt_lock(data_dir, attempt_id, children=True) as children:
            if children is None:
                raise AttemptStopped("interrupted", "前一个研究命令尚未退出")
            process = run_process(argv, lock=children, check_state=check_state, **kwargs)
        if process.returncode < 0:
            receipt["exit_code"] = process.returncode
            raise AttemptStopped("interrupted", f"研究命令被信号 {-process.returncode} 终止")
        return process

    def commit(completed, draft=None):
        with task_database(data_dir, write=True) as db:
            current = db.execute("SELECT receipt FROM research_attempt WHERE attempt_id=?",
                                 (attempt_id,)).fetchone()
            stored = json.loads(current["receipt"])
            if stored["status"] == "cancelling":
                return store_receipt(db, cancelled(receipt))
            if stored["status"] != "running":
                return stored
            if external and completed["status"] in ("blocked", "draft_ready", "report_ready") and time.monotonic() >= deadline:
                return store_receipt(db, {**receipt, "status": "timed_out", "termination_reason": "timed_out",
                                          "error": "研究尝试超过配置的时限"})
            if draft is not None:
                ResearchDossiers(data_dir).save_task_draft(draft, db=db)
            db.execute("UPDATE research_attempt SET receipt=? WHERE attempt_id=?",
                       (json_text(completed), attempt_id))
        return completed

    try:
        manifest = json.loads(frozen)
        public = deepcopy(development_public) if development_public is not None else json.loads(frozen)
        if external:
            print(f'研究任务 {receipt["task_id"]}  尝试 {attempt_id}', file=sys.stderr, flush=True)
            result = executor.run(public, receipt, data_dir, supervised)
        elif development_public is not None:
            result = (executor or offline_interpretation)(public)
        else:
            result = (executor or offline_executor)(public)
        if development_public is not None:
            report = prepare_development_report(result, receipt, development_public)
            return commit({**receipt, "status": "report_ready", "report_version": report["version"],
                           "report": report, "gaps": report["gaps"]})
        gaps = preflight_gaps(manifest)
        for gap in result["gaps"]:
            if (not isinstance(gap.get("blocking"), bool) or not gap.get("reason")
                    or not gap.get("required_evidence")):
                raise ValueError("证据缺口须说明所需材料、原因和阻塞性")
            if gap not in gaps:
                gaps.append(gap)
        if any(gap["blocking"] for gap in gaps):
            return commit({**receipt, "status": "blocked", "gaps": gaps})
        draft = prepare_task_draft(result["draft"], receipt, manifest, gaps, market_finding(manifest))
        return commit({**receipt, "status": "draft_ready", "draft_version": draft["version"],
                       "gaps": gaps}, draft)
    except AttemptStopped as error:
        return commit({**receipt, "status": error.status, "termination_reason": error.status, "error": str(error)})
    except (HarnessFailure, ProcessConfigurationError) as error:
        kind = error.kind if isinstance(error, HarnessFailure) else "configuration"
        return commit({**receipt, "status": "failed", "failure_kind": kind, "error": str(error)})
    except KeyboardInterrupt:
        if external:
            return commit(cancelled(receipt))
        commit({**receipt, "status": "interrupted", "termination_reason": "interrupted", "error": "用户中断研究执行"})
        raise
    except OSError as error:
        if external:
            return commit({**receipt, "status": "failed", "failure_kind": "configuration",
                           "error": f"无法使用本地研究运行环境（errno={error.errno}）"})
        return commit({**receipt, "status": "failed", "error": str(error)})
    except sqlite3.Error as error:
        return commit({**receipt, "status": "failed", "failure_kind": "storage", "error": str(error)})
    except Exception as error:
        if external:
            receipt["failure_kind"] = "invalid_response"
        return commit({**receipt, "status": "failed", "error": str(error)})


def register_and_execute(data_dir, task_id, *, manifest=None, parent_task_id=None,
                         executor=_DEFAULT_HARNESS, executor_name=None, timeout=180, development_receipt=None):
    from roll.v3.development_replay import development_attempt_fields, store_development_receipt
    from roll.v3.harness_settings import select_harness

    configuration_error = None
    if executor is _DEFAULT_HARNESS and (development_receipt is None or development_receipt["status"] == "computed"):
        try:
            executor = select_harness(data_dir, executor_name, timeout)
        except (OSError, ValueError) as error:
            if development_receipt is None:
                raise
            configuration_error = (str(error) if isinstance(error, ValueError)
                                   else f"无法读取研究助手设置（errno={error.errno}）")

    attempt_id = "attempt-" + uuid4().hex
    lock_error = None
    with ExitStack() as stack:
        try:
            lock = stack.enter_context(attempt_lock(data_dir, attempt_id))
        except OSError as error:
            lock_error = f"无法创建研究运行锁（errno={error.errno}）"
        else:
            if lock is None:
                raise ValueError(f"研究尝试 ID 已被占用：{attempt_id}")
        with task_database(data_dir, write=True) as db:
            if manifest is None:
                row = db.execute(
                    "SELECT manifest, parent_task_id FROM research_task LEFT JOIN research_task_parent USING(task_id) "
                    "WHERE task_id=?", (task_id,),
                ).fetchone()
                if row is None:
                    raise ValueError(f"无此研究任务：{task_id}")
                parent_task_id = row["parent_task_id"]
                frozen = row["manifest"]
                ensure_no_other_owner(db, task_id, attempt_id)
            else:
                frozen = json_text(manifest)
                db.execute("INSERT INTO research_task VALUES (?,?)", (task_id, frozen))
                if parent_task_id is not None:
                    db.execute("INSERT INTO research_task_parent VALUES (?,?)", (task_id, parent_task_id))
            receipt = {"task_id": task_id, "attempt_id": attempt_id, "gaps": [], "draft_version": None}
            development_public = None
            if development_receipt is not None:
                receipt.update(development_attempt_fields(development_receipt))
                if manifest is not None:
                    store_development_receipt(db, task_id, development_receipt)
                if development_receipt["status"] == "computed":
                    receipt["development_input_ref"] = development_receipt["input_ref"]
                    try:
                        development_public = frozen_development_public(db, task_id, frozen, development_receipt)
                    except HarnessFailure as error:
                        configuration_error = str(error)
            if development_receipt is None or development_receipt["status"] == "computed":
                prepare_claim(data_dir, receipt, frozen, executor)
                error = lock_error or configuration_error
                if error:
                    receipt.update(status="failed", failure_kind="configuration", error=error)
            if parent_task_id is not None:
                receipt["parent_task_id"] = parent_task_id
            db.execute("INSERT INTO research_attempt VALUES (?,?,?)", (attempt_id, task_id, json_text(receipt)))
        if receipt["status"] != "running":
            return receipt
        return run_claimed(data_dir, receipt, frozen, executor, development_public=development_public)


def frozen_development_public(db, task_id, frozen, development_receipt):
    row = db.execute("SELECT public_input FROM research_development_public_input WHERE task_id=?", (task_id,)).fetchone()
    if row:
        return json.loads(row["public_input"])
    try:
        public = json_text(public_development_input(json.loads(frozen), development_receipt))
    except Exception:
        raise HarnessFailure("configuration", "无法从冻结开发回执构造公开研究输入") from None
    db.execute("INSERT INTO research_development_public_input VALUES (?,?)", (task_id, public))
    return json.loads(public)


def start_task(data_dir, manifest, *, executor=_DEFAULT_HARNESS, parent_task_id=None,
               executor_name=None, timeout=180, development_receipt=None):
    return register_and_execute(data_dir, "task-" + uuid4().hex, manifest=manifest, parent_task_id=parent_task_id,
                                executor=executor, executor_name=executor_name, timeout=timeout,
                                development_receipt=development_receipt)


def retry_task(data_dir, task_id, *, executor=_DEFAULT_HARNESS, executor_name=None, timeout=180):
    from roll.v3.development_replay import read_development_receipt

    with task_database(data_dir) as db:
        task = db.execute("SELECT json_extract(manifest, '$.kind') AS kind FROM research_task WHERE task_id=?",
                          (task_id,)).fetchone()
        active = db.execute(
            "SELECT receipt FROM research_attempt WHERE task_id=? "
            f"AND json_extract(receipt, '$.status') IN ({ACTIVE_PARAMS})", (task_id, *ACTIVE),
        ).fetchall()
    for row in active:
        read_receipt(data_dir, json.loads(row["receipt"]))
    development_receipt = read_development_receipt(data_dir, task_id) if task and is_development(dict(task)) else None
    return register_and_execute(data_dir, task_id, executor=executor, executor_name=executor_name,
                                timeout=timeout, development_receipt=development_receipt)


def run_task(data_dir, symbol, *, question, snapshot_id, as_of, materials=(), required_titles=(), basis=None, executor=_DEFAULT_HARNESS):
    manifest = freeze_manifest(data_dir, symbol, question=question, snapshot_id=snapshot_id,
                               as_of=as_of, materials=materials, required_titles=required_titles, basis=basis)
    return start_task(data_dir, manifest, executor=executor)


def supplement_task(data_dir, parent_task_id, *, materials=(), snapshot_id=None, as_of=None, executor=_DEFAULT_HARNESS):
    manifest = get_task(data_dir, parent_task_id)["manifest"]
    if is_development(manifest):
        raise ValueError("开发任务使用冻结预设与快照；更换快照请发起新的开发实验")
    cutoff = utc_timestamp(as_of) if as_of is not None else manifest["as_of"]
    combined = collect_materials(materials, cutoff, manifest["materials"])
    snapshot = snapshot_id if snapshot_id is not None else manifest["snapshot_id"]
    new_basis = snapshot != manifest["snapshot_id"] or cutoff != manifest["as_of"]
    if new_basis:
        market = export_market_research(data_dir, manifest["symbol"], snapshot_id=snapshot, as_of=cutoff)
        manifest.update(snapshot_id=snapshot, market=market, purpose=market["snapshot"]["use_mode"])
    if cutoff != manifest["as_of"]:
        manifest["as_of"] = cutoff
        manifest["dossier"] = ResearchDossiers(data_dir).public_version(manifest["symbol"], cutoff)
    if not new_basis and combined == manifest["materials"]:
        raise ValueError("补证须提供新材料、行情快照或截止时点；相同清单请重试原任务")
    manifest["materials"] = combined
    return start_task(data_dir, manifest, parent_task_id=parent_task_id, executor=executor)


def add_executor_options(command):
    command.add_argument("--executor", metavar="HARNESS", help="覆盖研究助手设置，如 offline、codex 或已配置的 ACP 名称")
    command.add_argument("--timeout", type=float, default=180, metavar="SECONDS", help="外部助手尝试的总时限")


def register_task_commands(research):
    from roll.v3.development_cli import register_development_commands
    from roll.v3.harness_settings import select_harness

    commands = research.add_parser("task", help="研究任务").add_subparsers(required=True)
    register_development_commands(commands)
    run = commands.add_parser("run", help="冻结公开输入并执行首次研究")
    run.add_argument("symbol")
    run.add_argument("--question", required=True)
    run.add_argument("--snapshot", required=True)
    run.add_argument("--as-of", required=True)
    run.add_argument("--material", action="append", default=[], metavar="JSON",
                     help="公告元数据 JSON，含 title/source/locator、url 或 document_id、received_at、file 或 excerpt")
    run.add_argument("--basis", choices=BASIS, help="问题依赖的公开证据类型")
    run.add_argument("--require", action="append", default=[], help="回答问题所需的公告标题，可重复")
    run.set_defaults(handler=lambda a, d: run_task(d, a.symbol, question=a.question,
                     snapshot_id=a.snapshot, as_of=a.as_of, materials=a.material, required_titles=a.require,
                     basis=a.basis, executor=select_harness(d, a.executor, a.timeout)))
    retry = commands.add_parser("retry", help="用原任务冻结的公开输入执行新尝试")
    retry.add_argument("task_id")
    retry.set_defaults(handler=lambda a, d: retry_task(d, a.task_id, executor_name=a.executor, timeout=a.timeout))
    supplement = commands.add_parser("supplement", help="沿用原问题及标的，补证并创建关联任务")
    supplement.add_argument("task_id", help="父任务 ID")
    supplement.add_argument("--material", action="append", default=[], metavar="JSON", help="新增公告元数据 JSON")
    supplement.add_argument("--snapshot", help="新行情快照 ID，默认沿用父任务")
    supplement.add_argument("--as-of", help="新研究截止时点，默认沿用父任务")
    supplement.set_defaults(handler=lambda a, d: supplement_task(d, a.task_id, materials=a.material,
                            snapshot_id=a.snapshot, as_of=a.as_of, executor=select_harness(d, a.executor, a.timeout)))
    for command in (run, retry, supplement):
        add_executor_options(command)
    show = commands.add_parser("show", help="读取任务的公开清单与历次尝试")
    show.add_argument("task_id")
    show.set_defaults(handler=lambda a, d: get_task(d, a.task_id))
    cancel = commands.add_parser("cancel", help="取消正在运行的研究尝试并等候清理")
    cancel.add_argument("attempt_id")
    cancel.set_defaults(handler=lambda a, d: cancel_attempt(d, a.attempt_id))
    attempt = commands.add_parser("attempt", help="按 ID 读取单次尝试结果")
    attempt.add_argument("attempt_id")
    attempt.set_defaults(handler=lambda a, d: get_attempt(d, a.attempt_id))
