"""Import and publish research independently of any account."""
from contextlib import contextmanager
from datetime import UTC
from hashlib import sha256
import json
from pathlib import Path

import yaml

from roll.v3.storage import database, instant, json_text


def _timestamp(value=None):
    return instant(value).astimezone(UTC).isoformat(timespec="microseconds")

def _metadata(markdown):
    lines = markdown.removeprefix("\ufeff").splitlines()
    if not lines or lines[0] != "---":
        return {}
    if "---" not in lines[1:]:
        raise ValueError("研究档案的 YAML 元数据须以一对 --- 包围")
    end = lines.index("---", 1)
    try:
        metadata = yaml.safe_load("\n".join(lines[1:end])) or {}
    except yaml.YAMLError as error:
        raise ValueError(f"无法读取研究档案 YAML：{error}") from error
    if not isinstance(metadata, dict):
        raise ValueError("档案元数据须为 YAML 映射")
    return metadata


_PUBLIC_EVIDENCE_FIELDS = (
    "id", "title", "issuer", "source", "url", "document_id", "locator",
    "disclosed_at", "received_at", "classification", "snapshot_id",
)


_CONSTRAINTS = (
    "fundamental_gate",
    "thesis_status",
    "strategy_whitelist",
    "invalidation_triggers",
)


def _list(value, field):
    if not isinstance(value, list):
        raise ValueError(f"{field} 须为列表")
    return value


def _check_refs(refs, available, field):
    if any(not isinstance(ref, str) or ref not in available for ref in _list(refs, field)):
        raise ValueError(f"{field} 引用了未登记的证据")
    return refs


def _validated_draft(draft, *, reviewer=None):
    as_of = _timestamp(draft.get("as_of") or draft["imported_at"])
    if not draft.get("valid_until"):
        raise ValueError("档案须提供 valid_until")
    valid_until = _timestamp(draft["valid_until"])
    if valid_until <= as_of:
        raise ValueError("档案有效期截止须晚于结论时点")

    fundamental_gate = draft.get("fundamental_gate", "unknown")
    thesis_status = draft.get("thesis_status", "unknown")
    if fundamental_gate not in ("pass", "unknown", "fail"):
        raise ValueError("fundamental_gate 须为 pass、unknown 或 fail")
    if thesis_status not in ("intact", "watch", "broken", "unknown"):
        raise ValueError("thesis_status 须为 intact、watch、broken 或 unknown")

    evidence = {}
    for item in _list(draft.get("evidence", []), "evidence"):
        if not isinstance(item, dict) or not all(item.get(key) for key in ("id", "title", "source", "locator")):
            raise ValueError("证据须提供 id、title、source 和 locator")
        if not (item.get("url") or item.get("document_id")):
            raise ValueError("证据须提供 url 或 document_id")
        key = str(item["id"])
        if key in evidence:
            raise ValueError(f"证据 id 重复：{key}")
        received_at = _timestamp(item.get("received_at") or draft["imported_at"])
        if received_at > as_of:
            raise ValueError(f"证据 {key} 的取得时间晚于档案结论时点")
        evidence[key] = {**item, "id": key, "received_at": received_at}

    evidence_refs = _check_refs(draft.get("evidence_refs", list(evidence)), evidence, "evidence_refs")
    whitelist = _list(draft.get("strategy_whitelist", []), "strategy_whitelist")
    if any(not isinstance(strategy, str) for strategy in whitelist):
        raise ValueError("strategy_whitelist 须列出策略标识")
    triggers = _list(draft.get("invalidation_triggers", []), "invalidation_triggers")
    for trigger in triggers:
        if not isinstance(trigger, dict):
            raise ValueError("invalidation_triggers 须列出结构化触发条件")
        _check_refs(trigger.get("evidence_refs", []), evidence, "invalidation_triggers.evidence_refs")

    authored_basis = draft.get("constraint_basis", {})
    if not isinstance(authored_basis, dict):
        raise ValueError("constraint_basis 须按约束字段列出依据")
    basis = {}
    for constraint in _CONSTRAINTS:
        entry = authored_basis.get(constraint, {})
        if not isinstance(entry, dict):
            raise ValueError(f"constraint_basis.{constraint} 须列出依据")
        refs = _check_refs(entry.get("evidence_refs", []), evidence, f"constraint_basis.{constraint}")
        basis[constraint] = {"evidence_refs": refs} if refs or reviewer is None else {"confirmed_by": reviewer}
        if entry.get("rationale"):
            basis[constraint]["rationale"] = entry["rationale"]

    return {
        **draft,
        "as_of": as_of,
        "valid_until": valid_until,
        "fundamental_gate": fundamental_gate,
        "thesis_status": thesis_status,
        "strategy_whitelist": whitelist,
        "invalidation_triggers": triggers,
        "evidence_refs": evidence_refs,
        "evidence": list(evidence.values()),
        "constraint_basis": basis,
    }


def _publication(draft, reviewer, published_at, effective_at):
    draft = _validated_draft(draft, reviewer=reviewer)
    if draft["as_of"] > published_at:
        raise ValueError("档案结论时点不可晚于发布时间")
    if not published_at <= effective_at < draft["valid_until"]:
        raise ValueError("档案须在发布时或之后生效，且生效时点须早于有效期截止")
    return {
        **draft,
        "review_status": "published",
        "reviewer": reviewer,
        "published_at": published_at,
        "effective_at": effective_at,
    }


def prepare_task_draft(result, receipt, manifest, gaps):
    draft = {**result, "task_id": receipt["task_id"], "attempt_id": receipt["attempt_id"],
             "version": receipt["attempt_id"], "gaps": gaps, "imported_at": _timestamp(),
             "review_status": "draft", "reviewer": None, "published_at": None, "effective_at": None}
    if draft.get("symbol") != manifest["symbol"]:
        raise ValueError("草稿标的与任务标的不符")
    if not draft.get("as_of") or _timestamp(draft["as_of"]) != manifest["as_of"]:
        raise ValueError("草稿结论时点与任务截止时点不符")
    draft = _validated_draft(draft)
    if not draft["evidence_refs"]:
        raise ValueError("研究草稿须引用本次清单的证据")
    allowed = [{k: v for k, v in item.items() if k not in ("content", "encoding")}
               for item in manifest["materials"]]
    if manifest["dossier"]:
        allowed.extend(manifest["dossier"]["evidence"])
    if any(item not in allowed for item in draft["evidence"]):
        raise ValueError("草稿证据不属于本次清单或来源元数据不符")
    body = draft.pop("markdown")
    if not isinstance(body, str) or not body.strip():
        raise ValueError("研究草稿须提供正文")
    draft["markdown"] = "---\n" + yaml.safe_dump(draft, allow_unicode=True) + "---\n" + body
    return draft


class ResearchDossiers:
    def __init__(self, data_dir):
        self.data_dir = data_dir

    @contextmanager
    def _connect(self, *, write=False, db=None):
        with database(self.data_dir, write=write, db=db) as db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS research_draft (
                    symbol TEXT NOT NULL,
                    version TEXT NOT NULL,
                    imported_at TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    PRIMARY KEY (symbol, version)
                )
            """)
            db.execute("""
                CREATE TABLE IF NOT EXISTS research_version (
                    symbol TEXT NOT NULL,
                    version TEXT NOT NULL,
                    published_at TEXT NOT NULL,
                    effective_at TEXT NOT NULL,
                    valid_until TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    PRIMARY KEY (symbol, version)
                )
            """)
            yield db

    def import_draft(self, symbol, markdown, *, version=None):
        metadata = _metadata(markdown)
        symbol = symbol.upper()
        version = str(metadata.get("version") or version or "").strip()
        if not version:
            raise ValueError("研究草稿须提供版本")
        imported_at = _timestamp()
        draft = {
            **metadata,
            "symbol": symbol,
            "version": version,
            "markdown": markdown,
            "review_status": "draft",
            "reviewer": None,
            "published_at": None,
            "effective_at": None,
            "imported_at": imported_at,
        }
        payload = json_text(draft)
        with self._connect(write=True) as db:
            db.execute("""
                INSERT INTO research_draft (symbol, version, imported_at, payload)
                VALUES (?, ?, ?, ?)
                ON CONFLICT (symbol, version) DO UPDATE
                SET imported_at = excluded.imported_at, payload = excluded.payload
            """, (symbol, version, imported_at, payload))
        return json.loads(payload)

    def save_task_draft(self, draft, *, db):
        with self._connect(write=True, db=db) as db:
            db.execute("INSERT INTO research_draft (symbol, version, imported_at, payload) VALUES (?,?,?,?)",
                       (draft["symbol"], draft["version"], draft["imported_at"], json_text(draft)))
        return draft

    def draft(self, symbol, version=None):
        with self._connect() as db:
            row = db.execute("""
                SELECT payload FROM research_draft
                WHERE symbol = ? AND (? IS NULL OR version = ?)
                ORDER BY imported_at DESC, version DESC LIMIT 1
            """, (symbol.upper(), version, version)).fetchone()
        return json.loads(row["payload"]) if row else None

    def publish(self, symbol, version, reviewer, *, effective_at=None):
        symbol = symbol.upper()
        reviewer = reviewer.strip()
        if not reviewer:
            raise ValueError("发布档案须指定确认人")
        effective_at = _timestamp(effective_at) if effective_at is not None else None
        with self._connect(write=True) as db:
            row = db.execute("""
                SELECT payload FROM research_draft WHERE symbol = ? AND version = ?
            """, (symbol, version)).fetchone()
            if row is None:
                raise ValueError(f"无此研究草稿：{symbol} {version}")
            draft = json.loads(row["payload"])
            row = db.execute("""
                SELECT payload FROM research_version WHERE symbol = ? AND version = ?
            """, (symbol, version)).fetchone()
            if row:
                prior = json.loads(row["payload"])
                if (prior["markdown"] == draft["markdown"] and prior["reviewer"] == reviewer
                        and effective_at in (None, prior["effective_at"])):
                    return prior
                raise ValueError(f"已发布的档案不可覆盖，请指定新版本：{symbol} {version}")

            published_at = _timestamp()
            publication = _publication(draft, reviewer, published_at, effective_at or published_at)
            db.execute("""
                INSERT INTO research_version
                    (symbol, version, published_at, effective_at, valid_until, payload)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (symbol, version, published_at, publication["effective_at"],
                  publication["valid_until"], json_text(publication)))
        return publication

    def version(self, symbol, version, *, db=None):
        """Read an immutable publication by its reference, including expired versions."""
        with self._connect(db=db) as db:
            row = db.execute("""
                SELECT payload FROM research_version WHERE symbol = ? AND version = ?
            """, (symbol.upper(), version)).fetchone()
        return json.loads(row["payload"]) if row else None

    def active(self, symbol, as_of=None):
        """Read only the version in effect at the decision cutoff."""
        cutoff = _timestamp(as_of)
        result = self.effective_version(symbol, cutoff)
        return result if result and cutoff < result["valid_until"] else None

    def effective_version(self, symbol, as_of=None, *, db=None):
        """Read the last effective publication, retaining its expiration for arbitration."""
        cutoff = _timestamp(as_of)
        with self._connect(db=db) as db:
            row = db.execute("""
                SELECT payload, valid_until FROM research_version
                WHERE symbol = ? AND published_at <= ? AND effective_at <= ?
                ORDER BY effective_at DESC, published_at DESC, version DESC LIMIT 1
            """, (symbol.upper(), cutoff, cutoff)).fetchone()
        return json.loads(row["payload"]) if row else None

    def public_version(self, symbol, as_of):
        """Freeze only the active dossier reference and its public evidence metadata."""
        version = self.active(symbol, as_of)
        if version is None:
            return None
        public = {"symbol": version["symbol"], "version": version["version"],
                  "evidence": [{key: item[key] for key in _PUBLIC_EVIDENCE_FIELDS if key in item}
                               for item in version["evidence"]]}
        return {**public, "sha256": sha256(json_text(public).encode()).hexdigest()}

    def inputs(self, symbol, as_of=None):
        """Export the public source references available through the research entrance."""
        symbol = symbol.upper()
        cutoff = _timestamp(as_of)
        with self._connect() as db:
            rows = db.execute("""
                SELECT payload FROM research_version
                WHERE symbol = ? AND published_at <= ?
                ORDER BY published_at, version
            """, (symbol, cutoff)).fetchall()

        evidence = {}
        for row in rows:
            for item in json.loads(row["payload"])["evidence"]:
                evidence[item["id"]] = {key: item[key] for key in _PUBLIC_EVIDENCE_FIELDS if key in item}
        return {"symbol": symbol, "as_of": cutoff, "evidence": list(evidence.values())}


def _import_draft(args, data_dir):
    markdown = args.markdown.read_bytes().decode("utf-8")
    return ResearchDossiers(data_dir).import_draft(args.symbol, markdown, version=args.markdown.stem)


def _publish(args, data_dir):
    return ResearchDossiers(data_dir).publish(
        args.symbol, args.version, args.reviewer, effective_at=args.effective_at
    )


def _show(args, data_dir):
    dossiers = ResearchDossiers(data_dir)
    if args.draft:
        return dossiers.draft(args.symbol, args.version)
    if args.version:
        return dossiers.version(args.symbol, args.version)
    return dossiers.active(args.symbol, args.as_of)


def _inputs(args, data_dir):
    return ResearchDossiers(data_dir).inputs(args.symbol, args.as_of)


def _followups(args, data_dir):
    from roll.v3.review import DecisionLedger

    return DecisionLedger(data_dir).research_followups(args.symbol, mode=args.mode, as_of=args.as_of)


def register_research_commands(commands):
    research = commands.add_parser("research", help="导入、发布和读取个股研究档案")
    operations = research.add_subparsers(dest="research_operation", required=True)

    draft = operations.add_parser("draft", help="导入 Markdown 研究草稿")
    draft.add_argument("symbol")
    draft.add_argument("markdown", type=Path)
    draft.set_defaults(handler=_import_draft)

    publish = operations.add_parser("publish", help="由研究者确认并发布指定版本")
    publish.add_argument("symbol")
    publish.add_argument("version")
    publish.add_argument("--reviewer", required=True)
    publish.add_argument("--effective-at", help="带时区的 ISO 8601 时间，缺省为实际发布时间")
    publish.set_defaults(handler=_publish)

    show = operations.add_parser("show", help="读取档案版本或指定时点的有效档案")
    show.add_argument("symbol")
    show.add_argument("--draft", action="store_true")
    selection = show.add_mutually_exclusive_group()
    selection.add_argument("--version")
    selection.add_argument("--as-of")
    show.set_defaults(handler=_show)

    inputs = operations.add_parser("inputs", help="导出指定标的已发布的公开证据")
    inputs.add_argument("symbol")
    inputs.add_argument("--as-of")
    inputs.set_defaults(handler=_inputs)

    followups = operations.add_parser("followups", help="查看本标的由复盘证据触发的重新研究事项")
    followups.add_argument("symbol")
    followups.add_argument("--mode", choices=("live", "rehearsal", "reconstructed"), default="live")
    followups.add_argument("--as-of")
    followups.set_defaults(handler=_followups)
    return operations
