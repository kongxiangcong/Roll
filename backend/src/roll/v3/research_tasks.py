"""Freeze the public inputs to one offline research question and record each attempt."""
import base64
import json
from contextlib import contextmanager
from datetime import timedelta
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

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
CREATE INDEX IF NOT EXISTS research_attempt_task ON research_attempt(task_id)
"""


@contextmanager
def task_database(data_dir, *, write=False):
    with database(data_dir, write=write) as db:
        ensure_schema(db, _SCHEMA)
        yield db


def get_task(data_dir, task_id):
    with task_database(data_dir) as db:
        row = db.execute(
            "SELECT manifest, parent_task_id FROM research_task "
            "LEFT JOIN research_task_parent USING(task_id) WHERE task_id=?", (task_id,)
        ).fetchone()
        if not row:
            raise ValueError(f"无此研究任务：{task_id}")
        attempts = db.execute(
            "SELECT receipt FROM research_attempt WHERE task_id=? ORDER BY rowid", (task_id,)
        ).fetchall()
    return {"task_id": task_id, "parent_task_id": row["parent_task_id"], "manifest": json.loads(row["manifest"]),
            "attempts": [json.loads(item["receipt"]) for item in attempts]}


def get_attempt(data_dir, attempt_id):
    with task_database(data_dir) as db:
        row = db.execute("SELECT receipt FROM research_attempt WHERE attempt_id=?", (attempt_id,)).fetchone()
    if not row:
        raise ValueError(f"无此研究尝试：{attempt_id}")
    return json.loads(row["receipt"])


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
    return evidence, summary


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
    with task_database(data_dir, write=True) as db:
        row = db.execute(
            "SELECT receipt FROM research_attempt WHERE attempt_id=?",
            (attempt_id,),
        ).fetchone()
        if not row:
            raise ValueError(f"无此研究尝试：{attempt_id}")
        receipt = json.loads(row["receipt"])
        if receipt["status"] != "pending":
            return receipt
        receipt["status"] = "running"
        db.execute("UPDATE research_attempt SET receipt=? WHERE attempt_id=?", (json_text(receipt), attempt_id))

    def commit(completed, draft=None):
        with task_database(data_dir, write=True) as db:
            current = db.execute("SELECT receipt FROM research_attempt WHERE attempt_id=?",
                                 (attempt_id,)).fetchone()
            stored = json.loads(current["receipt"])
            if stored["status"] != "running":
                return stored
            if draft is not None:
                ResearchDossiers(data_dir).save_task_draft(draft, db=db)
            db.execute("UPDATE research_attempt SET receipt=? WHERE attempt_id=?",
                       (json_text(completed), attempt_id))
        return completed

    try:
        with task_database(data_dir) as db:
            frozen = db.execute("SELECT manifest FROM research_task WHERE task_id=?", (receipt["task_id"],)).fetchone()
        manifest = json.loads(frozen["manifest"])
        from roll.v3.codex_research import CodexExecutor, CodexFailure
        if isinstance(executor, CodexExecutor):
            import subprocess
            receipt.update(executor.initial_receipt(data_dir, attempt_id))
            try:
                result = executor.run(manifest, receipt, data_dir,
                                      lambda argv, **kwargs: subprocess.run(argv, capture_output=True, timeout=executor.timeout, **kwargs))
            except CodexFailure as error:
                return commit({**receipt, "status": "failed", "failure_kind": error.kind, "error": str(error)})
        else:
            result = (executor or offline_executor)(json.loads(frozen["manifest"]))
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
    except KeyboardInterrupt:
        commit({**receipt, "status": "interrupted", "error": "用户中断研究执行"})
        raise
    except Exception as error:
        if receipt.get("executor") == "codex":
            receipt["failure_kind"] = "invalid_response"
        return commit({**receipt, "status": "failed", "error": str(error)})


def register_attempt(db, task_id, parent_task_id):
    attempt_id = "attempt-" + uuid4().hex
    receipt = {"task_id": task_id, "attempt_id": attempt_id, "status": "pending",
               "gaps": [], "draft_version": None}
    if parent_task_id is not None:
        receipt["parent_task_id"] = parent_task_id
    db.execute("INSERT INTO research_attempt VALUES (?,?,?)", (attempt_id, task_id, json_text(receipt)))
    return attempt_id


def start_task(data_dir, manifest, *, executor=None, parent_task_id=None):
    task_id = "task-" + uuid4().hex
    with task_database(data_dir, write=True) as db:
        db.execute("INSERT INTO research_task VALUES (?,?)", (task_id, json_text(manifest)))
        if parent_task_id is not None:
            db.execute("INSERT INTO research_task_parent VALUES (?,?)", (task_id, parent_task_id))
        attempt_id = register_attempt(db, task_id, parent_task_id)
    return execute_attempt(data_dir, attempt_id, executor=executor)


def retry_task(data_dir, task_id, *, executor=None):
    with task_database(data_dir, write=True) as db:
        row = db.execute(
            "SELECT parent_task_id FROM research_task LEFT JOIN research_task_parent USING(task_id) "
            "WHERE task_id=?", (task_id,)
        ).fetchone()
        if row is None:
            raise ValueError(f"无此研究任务：{task_id}")
        attempt_id = register_attempt(db, task_id, row["parent_task_id"])
    return execute_attempt(data_dir, attempt_id, executor=executor)


def run_task(data_dir, symbol, *, question, snapshot_id, as_of, materials=(), required_titles=(), basis=None, executor=None):
    manifest = freeze_manifest(data_dir, symbol, question=question, snapshot_id=snapshot_id,
                               as_of=as_of, materials=materials, required_titles=required_titles, basis=basis)
    return start_task(data_dir, manifest, executor=executor)


def supplement_task(data_dir, parent_task_id, *, materials=(), snapshot_id=None, as_of=None, executor=None):
    manifest = get_task(data_dir, parent_task_id)["manifest"]
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


def register_task_commands(research):
    from roll.v3.codex_research import CodexExecutor

    def selected(args):
        return CodexExecutor(args.timeout) if args.executor == "codex" else None

    commands = research.add_parser("task", help="研究任务").add_subparsers(required=True)
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
                     snapshot_id=a.snapshot, as_of=a.as_of, materials=a.material, required_titles=a.require, basis=a.basis, executor=selected(a)))
    retry = commands.add_parser("retry", help="用原任务冻结的公开输入执行新尝试")
    retry.add_argument("task_id")
    retry.set_defaults(handler=lambda a, d: retry_task(d, a.task_id, executor=selected(a)))
    supplement = commands.add_parser("supplement", help="沿用原问题及标的，补证并创建关联任务")
    supplement.add_argument("task_id", help="父任务 ID")
    supplement.add_argument("--material", action="append", default=[], metavar="JSON", help="新增公告元数据 JSON")
    supplement.add_argument("--snapshot", help="新行情快照 ID，默认沿用父任务")
    supplement.add_argument("--as-of", help="新研究截止时点，默认沿用父任务")
    supplement.set_defaults(handler=lambda a, d: supplement_task(d, a.task_id, materials=a.material,
                            snapshot_id=a.snapshot, as_of=a.as_of, executor=selected(a)))
    for command in (run, retry, supplement):
        command.add_argument("--executor", choices=("offline", "codex"), default="offline", help="默认离线执行")
        command.add_argument("--timeout", type=float, default=180, metavar="SECONDS", help="Codex 尝试的总时限")
    show = commands.add_parser("show", help="读取任务的公开清单与历次尝试")
    show.add_argument("task_id")
    show.set_defaults(handler=lambda a, d: get_task(d, a.task_id))
    attempt = commands.add_parser("attempt", help="按 ID 读取单次尝试结果")
    attempt.add_argument("attempt_id")
    attempt.set_defaults(handler=lambda a, d: get_attempt(d, a.attempt_id))
