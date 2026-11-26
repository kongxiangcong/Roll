"""Freeze the public inputs to one offline research question and record each attempt."""
import base64
import json
from contextlib import contextmanager
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

from roll.v3.market import utc_timestamp
from roll.v3.market_research import export_market_research
from roll.v3.research import ResearchDossiers
from roll.v3.storage import database, ensure_schema, json_text


_SCHEMA = """
CREATE TABLE IF NOT EXISTS research_task (
    task_id TEXT PRIMARY KEY,
    manifest TEXT NOT NULL
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
        row = db.execute("SELECT manifest FROM research_task WHERE task_id=?", (task_id,)).fetchone()
        if not row:
            raise ValueError(f"无此研究任务：{task_id}")
        attempts = db.execute(
            "SELECT receipt FROM research_attempt WHERE task_id=? ORDER BY rowid", (task_id,)
        ).fetchall()
    return {"task_id": task_id, "manifest": json.loads(row["manifest"]),
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


def freeze_manifest(data_dir, symbol, *, question, snapshot_id, as_of, materials=(), required_titles=()):
    if not question.strip() or not symbol.strip() or not as_of:
        raise ValueError("研究任务须提供标的、问题和截止时点")
    symbol = symbol.strip().upper()
    cutoff = utc_timestamp(as_of)
    market = export_market_research(data_dir, symbol, snapshot_id=snapshot_id, as_of=cutoff)
    titles = [title.strip() for title in required_titles]
    if any(not title for title in titles):
        raise ValueError("必要公告标题为空")
    return {
        "symbol": symbol, "question": question.strip(), "as_of": cutoff, "snapshot_id": snapshot_id,
        "purpose": market["snapshot"]["use_mode"], "market": market,
        "dossier": ResearchDossiers(data_dir).public_version(symbol, cutoff),
        "required_titles": list(dict.fromkeys(titles)),
        "materials": [freeze_material(path, cutoff) for path in materials],
    }


def offline_executor(manifest):
    titles = {item["title"] for item in manifest["materials"]}
    needed = manifest["required_titles"] or [f'可核对「{manifest["question"]}」的公开公告']
    return {"gaps": [{"reason": "缺少回答本问题所需的公告原文或可定位摘录",
                      "required_evidence": title, "blocking": True} for title in needed if title not in titles]}


def execute_attempt(data_dir, manifest, receipt, *, executor=None):
    try:
        result = (executor or offline_executor)(manifest)
        receipt = {**receipt, "status": "blocked", "gaps": result["gaps"]}
    except Exception as error:
        receipt = {**receipt, "status": "failed", "error": str(error)}
    with task_database(data_dir, write=True) as db:
        db.execute("UPDATE research_attempt SET receipt=? WHERE attempt_id=?",
                   (json_text(receipt), receipt["attempt_id"]))
    return receipt


def start_task(data_dir, manifest, *, executor=None):
    task_id = "task-" + uuid4().hex
    attempt_id = "attempt-" + uuid4().hex
    receipt = {"task_id": task_id, "attempt_id": attempt_id, "status": "running",
               "gaps": [], "draft_version": None}
    with task_database(data_dir, write=True) as db:
        db.execute("INSERT INTO research_task VALUES (?,?)", (task_id, json_text(manifest)))
        db.execute("INSERT INTO research_attempt VALUES (?,?,?)", (attempt_id, task_id, json_text(receipt)))
    return execute_attempt(data_dir, manifest, receipt, executor=executor)


def run_task(data_dir, symbol, *, question, snapshot_id, as_of, materials=(), required_titles=(), executor=None):
    manifest = freeze_manifest(data_dir, symbol, question=question, snapshot_id=snapshot_id,
                               as_of=as_of, materials=materials, required_titles=required_titles)
    return start_task(data_dir, manifest, executor=executor)


def register_task_commands(research):
    commands = research.add_parser("task", help="离线研究任务").add_subparsers(required=True)
    run = commands.add_parser("run", help="冻结公开输入并执行首次研究")
    run.add_argument("symbol")
    run.add_argument("--question", required=True)
    run.add_argument("--snapshot", required=True)
    run.add_argument("--as-of", required=True)
    run.add_argument("--material", action="append", default=[], metavar="JSON",
                     help="公告元数据 JSON，含 title/source/locator、url 或 document_id、received_at、file 或 excerpt")
    run.add_argument("--require", action="append", default=[], help="回答问题所需的公告标题，可重复")
    run.set_defaults(handler=lambda a, d: run_task(d, a.symbol, question=a.question,
                     snapshot_id=a.snapshot, as_of=a.as_of, materials=a.material, required_titles=a.require))
    show = commands.add_parser("show", help="读取任务的公开清单与历次尝试")
    show.add_argument("task_id")
    show.set_defaults(handler=lambda a, d: get_task(d, a.task_id))
    attempt = commands.add_parser("attempt", help="按 ID 读取单次尝试结果")
    attempt.add_argument("attempt_id")
    attempt.set_defaults(handler=lambda a, d: get_attempt(d, a.attempt_id))
