"""Single account write boundary; commands publish facts only on confirmation.

New event kinds extend prepare() while confirm() remains the sole atomic writer.
JSON stores decimal strings, never floating point amounts.
"""
import hashlib
import json
import os
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal, localcontext
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field
from roll.accounts.fills import actual_fill, fee_adjustment
from roll.accounts.cash_events import CASH_KINDS, EVENT_FIELDS, actual_cash, stamp_cash
from roll.accounts.corrections import active_events, correction_event, fact_command
from roll.accounts.reconcile import declare,reconcile_snapshot,RECONCILIATION_FIELDS


class DraftCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: str
    expected_account_version: int = Field(ge=0)
    payload: dict


class ConfirmCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")
    draft_id: str
    idempotency_key: str = Field(min_length=1, max_length=128)


class EquityHint(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: str = Field(min_length=1,max_length=4096)
    declared_at: str | None
    instrument: str | None
    content: str = Field(min_length=1,max_length=65536)


def now():
    return datetime.now(timezone.utc).isoformat()


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def number(value, field, scale=2, nullable=False):
    if value is None and nullable:
        return None
    if not isinstance(value, str) or not re.fullmatch(r"\d{1,18}(?:\.\d{1," + str(scale) + r"})?", value):
        raise HTTPException(422, f"{field}: 必须为非负十进制字符串，最多 {scale} 位小数")
    decimal = Decimal(value)
    return format(decimal, ".2f") if scale == 2 else format(decimal, "f")


def timestamp(value, field="effective_at"):
    try:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            raise ValueError()
    except (TypeError, ValueError):
        raise HTTPException(422, f"{field}: 需要带时区的 ISO 8601 时间")
    if parsed > datetime.now(timezone.utc):
        raise HTTPException(422, f"{field}: 不能确认未来事实")
    return parsed.isoformat()


def text_value(value, field):
    if not isinstance(value, str) or not value.strip():
        raise HTTPException(422, f"{field}: 不能为空")
    return value.strip()


def permissions(values, effective_at):
    if not isinstance(values, list):
        raise HTTPException(422, "permission_profile: 需要列表，未记录的范围一律未知")
    result, seen = [], set()
    for value in values:
        if not isinstance(value, dict) or set(value) != {"market", "board", "status", "basis"}:
            raise HTTPException(422, "权限需要 market、board、status、basis")
        market, board = text_value(value["market"], "market"), text_value(value["board"], "board")
        if (market, board) in seen or not isinstance(value["status"], str) or value["status"] not in {"OPEN", "NOT_OPEN", "UNKNOWN"}:
            raise HTTPException(422, "权限范围重复或状态无效")
        seen.add((market, board))
        result.append({**value, "market": market, "board": board, "basis": text_value(value["basis"], "basis"),
                       "effective_at": effective_at})
    return result


def empty_account():
    return {"version": 0, "currency": "CNY", "account_scope": "普通现金账户", "cash_balance": None,
            "broker_available": None, "broker_frozen": None, "withdrawable": None,
            "positions": [], "permission_profile": [], "confirmed_at": None, "effective_at": None,
            "historical_return": None, "state": "NOT_ESTABLISHED"}


class Ledger:
    def __init__(self, directory: Path):
        directory.mkdir(parents=True, exist_ok=True)
        self.path = directory / "roll.sqlite3"
        with self.connection() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS account_versions(version INTEGER PRIMARY KEY, snapshot TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS account_drafts(id TEXT PRIMARY KEY, command TEXT NOT NULL, preview TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS account_events(id TEXT PRIMARY KEY, version INTEGER NOT NULL, event TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS account_receipts(id TEXT PRIMARY KEY, idempotency_key TEXT UNIQUE NOT NULL, content_hash TEXT NOT NULL, receipt TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS account_audit(id TEXT PRIMARY KEY, version INTEGER NOT NULL, entry TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS account_equity_hints(id TEXT PRIMARY KEY, material TEXT NOT NULL);
            """)
            if db.execute("PRAGMA user_version").fetchone()[0] == 0:
                db.execute("PRAGMA user_version=1")
            if db.execute("PRAGMA user_version").fetchone()[0] == 1:
                db.execute("BEGIN IMMEDIATE")
                if db.execute("PRAGMA user_version").fetchone()[0] == 1:
                    db.execute("ALTER TABLE account_drafts ADD COLUMN status TEXT NOT NULL DEFAULT 'READY'")
                    db.execute("ALTER TABLE account_drafts ADD COLUMN issues TEXT NOT NULL DEFAULT '[]'")
                    db.execute("PRAGMA user_version=2")
                db.commit()

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA synchronous=FULL")
        try:
            yield db
        finally:
            db.close()

    def account(self, version=None, db=None):
        if db is None:
            with self.connection() as connection:
                return self.account(version, connection)
        row = db.execute("SELECT snapshot FROM account_versions ORDER BY version DESC LIMIT 1" if version is None
                         else "SELECT snapshot FROM account_versions WHERE version=?", () if version is None else (version,)).fetchone()
        if row:
            return json.loads(row["snapshot"])
        if version in {None, 0}:
            return empty_account()
        raise HTTPException(404, "账户版本不存在")

    def prepare(self, command, account, history=None):
        history=self.events() if history is None else history
        payload=command["payload"]
        if command["kind"]=="CSV_BATCH":
            if payload.get("errors"):
                raise HTTPException(422,payload["errors"])
            if set(payload)!={"source","effective_at","commands","errors","file_sha256"} or not payload["commands"]:
                raise HTTPException(422,"CSV 批次需要至少一条有效命令")
            projection,events,errors=account,[],[]
            for item in payload["commands"]:
                for check in item.get("csv_checks",[]):
                    try:
                        self._prepare_fact(check,empty_account() if check["kind"]=="BASELINE" else projection)
                    except HTTPException as error:
                        errors.append({"row":check["csv_row"],"reason":error.detail})
                try:
                    if item["kind"]=="CSV_BATCH":
                        raise HTTPException(422,"不能嵌套CSV批次")
                    projection,new_events=self.prepare(item,projection,history+events)
                    for event in new_events:
                        event.update(source_file_sha256=payload["file_sha256"],source_rows=[check["csv_row"] for check in item.get("csv_checks",[])] or [item["csv_row"]])
                    events.extend(new_events)
                except HTTPException as error:
                    errors.append({"row":item.get("csv_row"),"reason":error.detail})
            if errors:
                raise HTTPException(422,errors)
            return projection,events
        if command["kind"]=="CORRECTION":
            event=correction_event(payload,history,text_value,timestamp)
            event.update(account_version=account["version"]+1,recorded_at=now())
            return self.replay(history+[event]),[event]
        at=timestamp(payload.get("effective_at"))
        if history and datetime.fromisoformat(at)<min(datetime.fromisoformat(e["effective_at"]) for e in history if e["event_type"]=="INITIAL_CASH"):
            raise HTTPException(422,"事实早于初始账户基线，无法重建基线前历史；请核对对账依据")
        before=self.replay(history,effective_at=at) if history else account
        projection,events=self._prepare_fact(command,before)
        for event in events:
            event.update(account_version=account["version"]+1,recorded_at=now())
        return self.replay(history+events),events

    def _prepare_fact(self, command, account):
        payload = command["payload"]
        effective_at = timestamp(payload.get("effective_at"))
        source = text_value(payload.get("source"), "source")
        if command["kind"] == "BASELINE":
            if account["version"] != 0:
                raise HTTPException(409, "已建立基线，不能覆盖已有账户；请使用成交或对账")
            fields = {"effective_at", "source", "cash_balance", "broker_available", "broker_frozen", "withdrawable", "positions", "permission_profile"}
            if set(payload) != fields:
                raise HTTPException(422, "基线字段缺失或存在未知字段")
            cash = {key: number(payload[key], key, nullable=key != "cash_balance")
                    for key in ["cash_balance", "broker_available", "broker_frozen", "withdrawable"]}
            positions, seen = [], set()
            if not isinstance(payload["positions"], list):
                raise HTTPException(422, "positions: 需要列表")
            for value in payload["positions"]:
                if not isinstance(value, dict) or set(value) != {"instrument", "quantity", "sellable_quantity", "reference_cost"}:
                    raise HTTPException(422, "持仓字段缺失或存在未知字段")
                instrument = text_value(value["instrument"], "instrument")
                if not re.fullmatch(r"(?:SSE|SZSE|BSE):\d{6}", instrument) or instrument in seen:
                    raise HTTPException(422, "证券必须为交易所:六位代码且不重复")
                seen.add(instrument)
                quantity = number(value["quantity"], "quantity", scale=8)
                sellable = number(value["sellable_quantity"], "sellable_quantity", scale=8, nullable=True)
                if Decimal(quantity) <= 0 or (sellable is not None and Decimal(sellable) > Decimal(quantity)):
                    raise HTTPException(422, "持仓必须大于零，可卖数量不能超过持仓")
                positions.append({"instrument": instrument, "quantity": quantity, "sellable_quantity": sellable,
                                  "reference_cost": number(value["reference_cost"], "reference_cost", scale=8, nullable=True),
                                  "buy_time": None, "historical_fees": None, "baseline_source": source})
            projection = {**account, **cash, "positions": positions, "permission_profile": permissions(payload["permission_profile"], effective_at)}
            events = [{"event_type": "INITIAL_CASH", "payload": cash}]
            events += [{"event_type": "INITIAL_POSITION", "payload": value} for value in positions]
        elif command["kind"] == "PERMISSIONS":
            if account["version"] == 0:
                raise HTTPException(409, "请先建立账户基线")
            if set(payload) != {"effective_at", "source", "permission_profile"}:
                raise HTTPException(422, "权限草稿字段缺失或存在未知字段")
            projection = {**account, "permission_profile": permissions(payload["permission_profile"], effective_at)}
            events = []
        elif command["kind"]=="RECONCILIATION":
            if account["version"]==0:raise HTTPException(409,"请先建立账户基线")
            with localcontext() as context:
                context.prec=80
                projection,events=reconcile_snapshot(payload,account,number,text_value)
        elif command["kind"] == "ACCOUNT_DECLARATION":
            if account["version"]==0:
                raise HTTPException(409,"请先建立账户基线")
            projection,events=declare(payload,account,text_value)
        elif command["kind"] == "FILL":
            with localcontext() as context:
                context.prec=80
                projection,events=actual_fill(payload,account,number,text_value)
        elif command["kind"] == "FEE_ADJUSTMENT":
            with localcontext() as context:
                context.prec=80
                projection,events=fee_adjustment(payload,account,number,text_value)
        elif command["kind"] in EVENT_FIELDS:
            with localcontext() as context:
                context.prec=80
                projection,events=actual_cash(command["kind"],payload,account,number,text_value)
        else:
            raise HTTPException(422, "尚不支持的草稿类型")
        if command["kind"] in {"BASELINE","PERMISSIONS"}:
            events.append({"event_type": "PERMISSION_CONFIRMATION", "payload": projection["permission_profile"]})
        projection.update(effective_at=effective_at, state="CONFIRMED_AS_OF")
        for event in events:
            event.update(effective_at=effective_at, source=source)
        return projection, events

    @staticmethod
    def diff(before, after):
        return {key: {"before": before.get(key), "after": value}
                for key, value in after.items() if before.get(key) != value}

    def draft(self, command: DraftCommand, db=None):
        if db is None:
            with self.connection() as connection:
                return self.draft(command, connection)
        command = command.model_dump()
        account = self.account(db=db)
        if command["expected_account_version"] != account["version"]:
            self.version_conflict(command["expected_account_version"], account)
        status,issues="READY",[]
        try:
            projection,_=self.prepare(command,account)
        except HTTPException as error:
            if command["kind"] not in {"FILL","FEE_ADJUSTMENT","CSV_BATCH","CORRECTION","ACCOUNT_DECLARATION","RECONCILIATION"}|EVENT_FIELDS.keys() or error.status_code!=422:
                raise
            projection,status,issues=account,"QUARANTINED",[error.detail]
        draft_id, created_at = str(uuid4()), now()
        preview = self.diff(account, projection)
        if status=="READY" and command["kind"]=="FILL":
            candidate=next(f for f in projection["fills"] if f["record_id"]==text_value(command["payload"]["record_id"],"record_id"))
            if candidate.get("identity_warning"):issues=[candidate["identity_warning"]]
        db.execute("INSERT INTO account_drafts(id,command,preview,created_at,status,issues) VALUES(?,?,?,?,?,?)", (draft_id, encode(command), encode(preview), created_at,status,encode(issues)))
        result={"draft_id": draft_id, "command": command, "preview": preview, "created_at": created_at,"status":status,"issues":issues}
        if command["kind"]=="RECONCILIATION" and status=="READY":result["reconciliation_differences"]=projection["reconciliation"]["differences_before"]
        return result

    def get_draft(self, draft_id, db=None):
        if db is None:
            with self.connection() as connection:
                return self.get_draft(draft_id, connection)
        row = db.execute("SELECT * FROM account_drafts WHERE id=?", (draft_id,)).fetchone()
        if row is None:
            raise HTTPException(404, "草稿不存在")
        result={"draft_id": row["id"], "command": json.loads(row["command"]), "preview": json.loads(row["preview"]), "created_at": row["created_at"],"status":row["status"],"issues":json.loads(row["issues"])}
        if result["command"]["kind"]=="RECONCILIATION" and "reconciliation" in result["preview"]:
            result["reconciliation_differences"]=result["preview"]["reconciliation"]["after"]["differences_before"]
        return result

    def version_conflict(self, expected, account):
        before = self.account(expected)
        raise HTTPException(409, {"code": "ACCOUNT_VERSION_CONFLICT", "expected_account_version": expected,
                                  "current_account_version": account["version"], "diff": self.diff(before, account)})

    def confirm(self, command: ConfirmCommand):
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                draft = self.get_draft(command.draft_id, db)
                fingerprint = hashlib.sha256(encode(draft["command"]).encode()).hexdigest()
                prior = db.execute("SELECT * FROM account_receipts WHERE idempotency_key=?", (command.idempotency_key,)).fetchone()
                if prior:
                    if prior["content_hash"] != fingerprint:
                        raise HTTPException(409, {"code": "IDEMPOTENCY_CONTENT_CONFLICT", "receipt_id": prior["id"]})
                    db.rollback()
                    return json.loads(prior["receipt"])
                if draft["status"] != "READY":
                    raise HTTPException(422,{"code":draft["status"]+"_DRAFT","issues":draft["issues"],"draft_id":command.draft_id})
                account = self.account(db=db)
                if draft["command"]["expected_account_version"] != account["version"]:
                    self.version_conflict(draft["command"]["expected_account_version"], account)
                if draft["command"]["kind"] == "CSV_BATCH":
                    original_hash = draft["command"]["payload"]["file_sha256"]
                    try:
                        original = (self.path.parent / "raw" / "account-csv" / original_hash).read_bytes()
                    except OSError:
                        original = b""
                    if hashlib.sha256(original).hexdigest() != original_hash:
                        raise HTTPException(409, {"code": "CSV_ORIGINAL_UNAVAILABLE", "reason": "原文件缺失或指纹不符，未提交任何账户事实"})
                history=self.events(db)
                projection, events = self.prepare(draft["command"], account,history)
                version, confirmed_at, receipt_id = account["version"] + 1, now(), str(uuid4())
                projection.update(version=version, confirmed_at=confirmed_at)
                if any(event["event_type"] == "PERMISSION_CONFIRMATION" for event in events):
                    for value in projection["permission_profile"]:
                        value.update(confirmed_at=confirmed_at, account_version=version)
                event_ids = []
                for event in events:
                    event_id = str(uuid4())
                    event.update(event_id=event_id, account_version=version, recorded_at=confirmed_at, namespace="ACTUAL",receipt_id=receipt_id)
                    if event["event_type"]=="PERMISSION_CONFIRMATION":
                        for value in event["payload"]:value.update(confirmed_at=confirmed_at,account_version=version)
                    if event["event_type"] in {"BUY_FILL","SELL_FILL"}|EVENT_FIELDS.keys():
                        event["payload"].update(event_id=event_id,receipt_id=receipt_id)
                        for fill in projection.get("fills", []):
                            if fill["record_id"] == event["payload"]["record_id"]:
                                fill.update(event_id=event_id, receipt_id=receipt_id)
                    if event["event_type"] in EVENT_FIELDS:
                        stamp_cash(projection,event["payload"],event_id=event_id,receipt_id=receipt_id,confirmed_at=confirmed_at)
                    event_ids.append(event_id)
                    db.execute("INSERT INTO account_events VALUES(?,?,?)", (event_id, version, encode(event)))
                for event in events:
                    if event["event_type"]=="RECONCILIATION":
                        for resolved in event["payload"]["resolved_draft_ids"]:
                            material=self.get_draft(resolved,db)
                            if material["status"] not in {"READY","QUARANTINED"} or db.execute("SELECT 1 FROM account_receipts WHERE json_extract(receipt,'$.draft_id')=?",(resolved,)).fetchone():
                                raise HTTPException(409,"所引用原草稿已确认或已处理，不能当作待核材料解除")
                            db.execute("UPDATE account_drafts SET status='RESOLVED' WHERE id=?",(resolved,))
                projection=self.replay(history+events)
                projection.update(version=version,confirmed_at=confirmed_at,system_known_at=confirmed_at,latest_confirmed_input_at=draft["command"]["payload"]["effective_at"])
                receipt = {"receipt_id": receipt_id, "draft_id": command.draft_id, "idempotency_key": command.idempotency_key,
                           "account_version": version, "confirmed_at": confirmed_at, "event_ids": event_ids,
                           "diff": self.diff(account, projection)}
                db.execute("INSERT INTO account_versions VALUES(?,?)", (version, encode(projection)))
                db.execute("INSERT INTO account_receipts VALUES(?,?,?,?)", (receipt_id, command.idempotency_key, fingerprint, encode(receipt)))
                audit_id = str(uuid4())
                entry = {"audit_id": audit_id, "account_version": version, "action": "ACCOUNT_CONFIRMED", "receipt_id": receipt_id,
                         "recorded_at": confirmed_at, "source": draft["command"]["payload"]["source"]}
                db.execute("INSERT INTO account_audit VALUES(?,?,?)", (audit_id, version, encode(entry)))
                self.crash_point("before_commit")
                db.commit()
                self.crash_point("after_commit")
                return receipt
            except BaseException:
                db.rollback()
                raise

    @staticmethod
    def crash_point(point):
        # Explicit test-only process fault injection; never available via HTTP.
        if os.environ.get("ROLL_ENV") == "test" and os.environ.get("ROLL_TEST_CRASH_POINT") == point:
            os._exit(86)

    def receipt(self, receipt_id):
        with self.connection() as db:
            row = db.execute("SELECT receipt FROM account_receipts WHERE id=?", (receipt_id,)).fetchone()
        if row is None:
            raise HTTPException(404, "回执不存在")
        return json.loads(row["receipt"])

    def events(self,db=None):
        if db is None:
            with self.connection() as connection:
                return self.events(connection)
        return [json.loads(row[0]) for row in db.execute("SELECT event FROM account_events ORDER BY version,rowid")]

    def audit(self):
        with self.connection() as db:
            return [json.loads(row[0]) for row in db.execute("SELECT entry FROM account_audit ORDER BY version,rowid")]

    def versions(self, after=0, db=None):
        """Immutable confirmed facts in order, optionally inside a reader transaction."""
        if db is None:
            with self.connection() as connection:
                return self.versions(after, connection)
        return [json.loads(row[0]) for row in db.execute(
            "SELECT snapshot FROM account_versions WHERE version>? ORDER BY version", (after,))]

    def pending_drafts(self):
        with self.connection() as db:
            ids=[r[0] for r in db.execute("SELECT d.id FROM account_drafts d WHERE status IN ('READY','QUARANTINED') AND NOT EXISTS(SELECT 1 FROM account_receipts r WHERE json_extract(r.receipt,'$.draft_id')=d.id) ORDER BY d.created_at")]
            return [self.get_draft(i,db) for i in ids]

    def quarantined_drafts(self):
        with self.connection() as db:
            ids=[row[0] for row in db.execute("SELECT id FROM account_drafts WHERE status='QUARANTINED' ORDER BY created_at")]
            return [self.get_draft(draft_id,db) for draft_id in ids]

    def equity_hint(self,command: EquityHint):
        from roll.accounts.cash_events import instrument
        value=command.model_dump()
        value.update(source=text_value(value["source"],"source"),content=text_value(value["content"],"content"),
                     instrument=instrument(value["instrument"],text_value),hint_id=str(uuid4()),learned_at=now(),
                     actual_effective_at=None,status="PENDING_USER_CONFIRMATION")
        if value["declared_at"] is not None:
            value["declared_at"]=text_value(value["declared_at"],"declared_at")
        with self.connection() as db:
            db.execute("INSERT INTO account_equity_hints VALUES(?,?)",(value["hint_id"],encode(value)))
        return value

    def equity_hints(self):
        with self.connection() as db:
            return [json.loads(row[0]) for row in db.execute("SELECT material FROM account_equity_hints ORDER BY rowid")]

    def replay(self, events=None, known_by=None, effective_at=None):
        events=self.events() if events is None else events
        visible=[e for e in events if known_by is None or datetime.fromisoformat(e["recorded_at"])<=datetime.fromisoformat(known_by)]
        materialized,chain,_=active_events(visible)
        selected=[e for e in materialized if effective_at is None or datetime.fromisoformat(e["effective_at"])<=datetime.fromisoformat(effective_at)]
        selected=sorted(enumerate(selected),key=lambda pair:(datetime.fromisoformat(pair[1]["effective_at"]),pair[0]))
        account=empty_account()
        fill_fields={"effective_at","source","instrument","direction","quantity","price","record_id","fill_id","order_id","behavior_context","fee","broker_available_after"}
        adjustment_fields={"effective_at","source","target_record_id","actual_fee_amount","basis"}
        for _,event in selected:
            payload=event["payload"]
            prior_at=account["effective_at"]
            effective_kind=event.get("replacement_command",{}).get("kind",event["event_type"])
            if "replacement_command" in event:
                command=fact_command(event)
                account,new=self._prepare_fact(command,account)
                if command["kind"]=="FILL":
                    account["fills"][-1].update(event_id=event.get("event_id"),receipt_id=event.get("receipt_id"))
                elif command["kind"] in EVENT_FIELDS:
                    stamp_cash(account,new[0]["payload"],event_id=event.get("event_id"),receipt_id=event.get("receipt_id"),confirmed_at=event["recorded_at"])
                elif command["kind"]=="PERMISSIONS":
                    for p in account["permission_profile"]:p.update(confirmed_at=event["recorded_at"],account_version=event["account_version"])
                elif command["kind"]=="RECONCILIATION":
                    account["reconciliation"].update(recorded_at=event["recorded_at"],account_version=event["account_version"],receipt_id=event.get("receipt_id"))
                elif command["kind"]=="ACCOUNT_DECLARATION":
                    account["declarations"][-1].update(recorded_at=event["recorded_at"],account_version=event["account_version"],receipt_id=event.get("receipt_id"))
            elif event["event_type"]=="INITIAL_CASH":
                account.update(payload)
            elif event["event_type"]=="INITIAL_POSITION":
                account["positions"].append(payload)
            elif event["event_type"]=="PERMISSION_CONFIRMATION":
                account["permission_profile"]=payload
            elif event["event_type"]=="RECONCILIATION":
                account,_=self._prepare_fact({"kind":"RECONCILIATION","payload":{key:payload[key] for key in RECONCILIATION_FIELDS}},account)
                account["reconciliation"].update(recorded_at=event["recorded_at"],account_version=event["account_version"],receipt_id=event.get("receipt_id"))
            elif event["event_type"]=="ACCOUNT_DECLARATION":
                prior_at=account["effective_at"]
                account,_=self._prepare_fact({"kind":"ACCOUNT_DECLARATION","payload":{key:payload[key] for key in ["effective_at","source","record_id","scope","changes","basis"]}},account)
                account["declarations"][-1].update(recorded_at=event["recorded_at"],account_version=event["account_version"],receipt_id=event.get("receipt_id"))
                account["effective_at"]=prior_at
            elif event["event_type"] in {"BUY_FILL","SELL_FILL","FEE_ADJUSTMENT"}:
                fields=adjustment_fields if event["event_type"]=="FEE_ADJUSTMENT" else fill_fields
                kind="FEE_ADJUSTMENT" if event["event_type"]=="FEE_ADJUSTMENT" else "FILL"
                command={"kind":kind,"payload":{key:payload[key] for key in fields}}
                account,_=self._prepare_fact(command,account)
                if kind=="FILL":
                    account["fills"][-1].update(event_id=payload.get("event_id"),receipt_id=payload.get("receipt_id"))
            elif event["event_type"] in EVENT_FIELDS:
                kind=payload.get("kind",event["event_type"])
                fields=EVENT_FIELDS[kind]
                account,_=self._prepare_fact({"kind":kind,"payload":{key:payload[key] for key in fields}},account)
                stamp_cash(account,payload,event_id=payload.get("event_id"),receipt_id=payload.get("receipt_id"),confirmed_at=event["recorded_at"])
            account.update(version=event["account_version"],confirmed_at=event["recorded_at"],state="CONFIRMED_AS_OF")
            account["effective_at"]=prior_at if effective_kind=="ACCOUNT_DECLARATION" else event["effective_at"]
        if visible:
            latest=max(visible,key=lambda e:(e["account_version"],e["recorded_at"]))
            account.update(version=latest["account_version"],confirmed_at=latest["recorded_at"],system_known_at=latest["recorded_at"],latest_confirmed_input_at=latest["effective_at"])
        financial=[e for e in visible if e["event_type"]!="ACCOUNT_DECLARATION" and not (e["event_type"]=="CORRECTION" and e["payload"].get("replacement",{} ) is not None and e["payload"]["replacement"].get("kind")=="ACCOUNT_DECLARATION")]
        if financial:account["latest_fact_recorded_at"]=max(e["recorded_at"] for e in financial)
        account["latest_effective_fact_at"]=account["effective_at"]
        if chain:
            account["corrections"]=chain
        return account
