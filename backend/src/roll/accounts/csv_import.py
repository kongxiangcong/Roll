"""Versioned Roll CSV is data. Parsing never calls an agent or executes text."""
import csv
import hashlib
import io
import json
import os
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field
from roll.accounts.ledger import DraftCommand, encode, now
from roll.accounts.cash_events import EVENT_FIELDS

VERSION = "ROLL-CSV-3"


class CsvRevision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_account_version: int = Field(ge=0)
    encoding: str
COLUMNS_V1 = ["template_version", "kind", "effective_at", "source", "exchange", "code",
           "cash_balance", "broker_available", "broker_frozen", "withdrawable", "quantity",
           "sellable_quantity", "reference_cost", "board", "permission_status", "basis",
           "direction", "price", "record_id", "fill_id", "order_id", "behavior_context",
           "fee_status", "fee_amount", "reserve_amount", "broker_available_after",
           "target_record_id", "actual_fee_amount"]
COLUMNS_V2 = COLUMNS_V1 + ["amount", "item_type", "corrected_amount", "new_quantity"]
COLUMNS = COLUMNS_V2 + ["reason","target_event_id","replacement_kind","replacement_payload","scope","changes","snapshot","resolved_draft_ids"]
TEMPLATES = {"ROLL-CSV-1": COLUMNS_V1, "ROLL-CSV-2": COLUMNS_V2,"ROLL-CSV-3":COLUMNS}
COMMON = {"template_version", "kind", "effective_at", "source"}
FIELDS = {
    "BASELINE_CASH": {"cash_balance", "broker_available", "broker_frozen", "withdrawable"},
    "INITIAL_POSITION": {"exchange", "code", "quantity", "sellable_quantity", "reference_cost"},
    "PERMISSION": {"exchange", "board", "permission_status", "basis"},
    "FILL": {"exchange", "code", "direction", "quantity", "price", "record_id", "fill_id", "order_id", "behavior_context", "fee_status", "fee_amount", "reserve_amount", "basis", "broker_available_after"},
    "FEE_ADJUSTMENT": {"target_record_id", "actual_fee_amount", "basis"},
}
KINDS_V1 = frozenset(FIELDS)
for kind, fields in EVENT_FIELDS.items():
    FIELDS[kind] = fields - {"effective_at", "source", "instrument"} | ({"exchange", "code"} if "instrument" in fields else set())
KINDS_V2=frozenset(FIELDS)
FIELDS.update(CORRECTION={"record_id","target_event_id","reason","replacement_kind","replacement_payload"},
              ACCOUNT_DECLARATION={"record_id","scope","changes","basis"},
              RECONCILIATION={"record_id","reason","snapshot","resolved_draft_ids"})


def template(version=VERSION):
    if version not in TEMPLATES:
        raise HTTPException(422, "模板版本不支持")
    output = io.StringIO(newline="")
    csv.writer(output).writerow(TEMPLATES[version])
    return "\ufeff" + output.getvalue()


def guide():
    rows = "".join(f"<tr><td>{kind}</td><td>{', '.join(sorted(fields))}</td></tr>" for kind, fields in FIELDS.items())
    return f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>Roll CSV填写说明</title><style>body{{font:16px system-ui;max-width:960px;margin:32px auto;line-height:1.7}}td,th{{padding:10px;border:1px solid #ddd}}table{{border-collapse:collapse}}</style><h1>Roll CSV填写说明 · {VERSION}</h1><p>保留模板列名、顺序和每行版本号。每行需要 kind、effective_at（带时区ISO时间，例如2026-10-07T10:00:00+08:00）、source（已核对来源）。交易所填写SSE、SZSE或BSE；code为六位代码，前导零必须保留，建议以文本单元格编辑。</p><p>金额最多2位小数，数量/价格最多8位小数，均为非负十进制原文。空白表示未知或不适用，不能用空白代替必填值。不得用科学计数法或在金额内加逗号。表中此类型不使用的列留空。</p><table><tr><th>kind</th><th>类型使用的列</th></tr>{rows}</table><p>初始状态必须恰有一行BASELINE_CASH，配合零到多行INITIAL_POSITION和PERMISSION，所有行source与effective_at一致。cash_balance、持仓quantity必填；其他资金、可卖数和参考成本可空。初始状态与后续事件分别上传。独立权限更新可只填PERMISSION行；permission_status为OPEN、NOT_OPEN或UNKNOWN，basis必填。</p><p>FILL方向BUY/SELL；quantity、price、fee_status和basis必填。KNOWN费用必须填写fee_amount（已知零填0），reserve_amount留空；PROVISIONAL未知费用fee_amount留空，reserve_amount填写有依据的正数保守预留。record_id可空，由文件身份及行号产生；可靠的券商分笔标识填fill_id，委托标识填order_id，两者不能互代。behavior_context可空或填NO_RECOMMENDATION、CONTRARY、EXCESS_QUANTITY、OFFLINE、UNSPECIFIED。FEE_ADJUSTMENT指向已确认record_id，actual_fee_amount、basis必填。</p><p>ROLL-CSV-2 的RIGHTS_SUBSCRIPTION填写实际新增quantity和amount（已实际支付总额，包含费用）；fee_amount空白表示费用分拆未知，明确已知零才填0。FEE_ADJUSTMENT可指向配股record_id，填写总支付内实际费用分拆，不再次扣现金或改变取得总成本。SHARE_CHANGE只填免费送转/拆并后的new_quantity总量；不得用其代替实际配股支付。待结算与结算需填写各自record_id，SETTLEMENT的target_record_id指原PENDING_ITEM。</p><p>ROLL-CSV-3 新增ACCOUNT_DECLARATION（scope为JSON范围数组，changes为NONE/UNRECORDED/EXTERNAL_ORDER_PENDING）、RECONCILIATION（snapshot为完整逐项快照JSON，resolved_draft_ids为已处理草稿ID数组）及CORRECTION（target_event_id指当前替代链末端，reason必填；replacement_kind与replacement_payload完整事实JSON同时填写，两者空白为明确冲正）。结构化列是数据，JSON中的金额仍为十进制字符串，未知填null。CSV自动处理引号转义，不可手工拆分含逗号的JSON。v1与v2列和事件集合保持原含义，不接受这三个新类型。</p><p>整批只产生一个账户版本及回执。任何行错误都不入账；修订后重新上传，旧原件保留。来源文字仅为材料，不能给系统发出指令。尚未支持券商专用原始格式。</p></html>'''


def nullable(value):
    return value if value != "" else None


def parse(raw, encoding, fingerprint):
    errors, rows, commands = [], [], []
    try:
        if encoding not in {"utf-8", "utf-8-sig", "gb18030"}:
            raise ValueError("编码只支持 utf-8、utf-8-sig、gb18030；不自动猜测")
        text = raw.decode(encoding).lstrip("\ufeff")
    except (ValueError, UnicodeError) as error:
        return [], [], [{"row": 0, "reason": str(error)}]
    reader = csv.reader(io.StringIO(text, newline=""), strict=True)
    lines = text.splitlines(keepends=True)
    try:
        header = next(reader)
        header_version = next((v for v, columns in TEMPLATES.items() if header == columns), None)
        if header_version is None:
            return [], [], [{"row": 1, "reason": "列名及顺序必须与下载的 Roll CSV 模板一致"}]
        previous = reader.line_num
        for values in reader:
            row_number = previous + 1
            row = {"row": row_number, "raw": "".join(lines[previous:reader.line_num]), "fields": dict(zip(header, values))}
            previous = reader.line_num
            rows.append(row)
            if len(rows) > 5000:
                errors.append({"row": row_number, "reason": "单文件最多5000行"})
                break
            fields = {key: row["fields"].get(key, "") for key in COLUMNS}
            if len(values) != len(header):
                errors.append({"row": row_number, "reason": "列数不匹配"})
                continue
            kind = fields["kind"]
            if fields["template_version"] != header_version or kind not in FIELDS or (header_version == "ROLL-CSV-1" and kind not in KINDS_V1) or (header_version=="ROLL-CSV-2" and kind not in KINDS_V2):
                errors.append({"row": row_number, "reason": "模板版本或事件类型不支持"})
                continue
            unused = [key for key, value in fields.items() if value and key not in COMMON | FIELDS[kind]]
            if unused:
                errors.append({"row": row_number, "reason": "此类型不使用字段：" + ", ".join(unused)})
                continue
            common = {"source": fields["source"], "effective_at": fields["effective_at"]}
            instrument = fields["exchange"] + ":" + fields["code"]
            if kind in {"CORRECTION","ACCOUNT_DECLARATION","RECONCILIATION"}:
                try:
                    payload={**common,"record_id":fields["record_id"]}
                    if kind=="CORRECTION":
                        if bool(fields["replacement_kind"])!=bool(fields["replacement_payload"]):raise ValueError("替代类型与完整事实需同时填写；两者空白为明确冲正")
                        payload.update(reason=fields["reason"],target_event_id=fields["target_event_id"],replacement={"kind":fields["replacement_kind"],"payload":json.loads(fields["replacement_payload"])} if fields["replacement_kind"] else None)
                    elif kind=="ACCOUNT_DECLARATION":
                        payload.update(scope=json.loads(fields["scope"]),changes=fields["changes"],basis=fields["basis"])
                    else:
                        payload.update(reason=fields["reason"],snapshot=json.loads(fields["snapshot"]),resolved_draft_ids=json.loads(fields["resolved_draft_ids"] or "[]"))
                    commands.append({"kind":kind,"payload":payload,"csv_row":row_number})
                except (ValueError,TypeError) as error:
                    errors.append({"row":row_number,"reason":"结构化事实填写错误："+str(error)})
            elif kind == "FILL":
                payload = {**common, "instrument": instrument, **{key: fields[key] for key in ["direction", "quantity", "price"]},
                           "record_id": fields["record_id"] or f"csv:{fingerprint}:{row_number}",
                           "fill_id": nullable(fields["fill_id"]), "order_id": nullable(fields["order_id"]),
                           "behavior_context": fields["behavior_context"] or "UNSPECIFIED",
                           "broker_available_after": nullable(fields["broker_available_after"]),
                           "fee": {"status": fields["fee_status"], "amount": nullable(fields["fee_amount"]), "reserve_amount": nullable(fields["reserve_amount"]), "basis": fields["basis"]}}
                commands.append({"kind": kind, "payload": payload, "csv_row": row_number})
            elif kind == "FEE_ADJUSTMENT":
                commands.append({"kind": kind, "payload": {**common, **{key: fields[key] for key in FIELDS[kind]}}, "csv_row": row_number})
            elif kind in EVENT_FIELDS:
                payload = {**common}
                for key in EVENT_FIELDS[kind] - {"effective_at", "source"}:
                    if key == "instrument":
                        payload[key] = instrument if fields["exchange"] or fields["code"] else None
                    elif key == "record_id":
                        payload[key] = fields[key] or f"csv:{fingerprint}:{row_number}"
                    elif key in {"broker_available_after", "amount"} or (kind == "RIGHTS_SUBSCRIPTION" and key == "fee_amount"):
                        payload[key] = nullable(fields[key])
                    else:
                        payload[key] = fields[key]
                commands.append({"kind": kind, "payload": payload, "csv_row": row_number})
    except (StopIteration, csv.Error) as error:
        errors.append({"row": reader.line_num, "reason": "CSV 格式错误：" + str(error)})
    baseline = [r for r in rows if r["fields"].get("kind") in {"BASELINE_CASH", "INITIAL_POSITION", "PERMISSION"}]
    if baseline:
        cash = [r for r in baseline if r["fields"]["kind"] == "BASELINE_CASH"]
        if not cash and all(r["fields"]["kind"] == "PERMISSION" for r in baseline):
            if commands:
                errors.append({"row": 0, "reason": "权限确认与其他事件必须分别上传"})
            first = baseline[0]["fields"]
            common = {key: first[key] for key in ["effective_at", "source"]}
            profile = [{"market": r["fields"]["exchange"], "board": r["fields"]["board"], "status": r["fields"]["permission_status"], "basis": r["fields"]["basis"]} for r in baseline]
            if any(any(r["fields"][k] != v for k, v in common.items()) for r in baseline):
                errors.append({"row": 0, "reason": "同次权限确认所有行的时点与来源必须一致"})
            commands.insert(0, {"kind": "PERMISSIONS", "payload": {**common, "permission_profile": profile}, "csv_row": baseline[0]["row"],
                                "csv_checks": [{"kind": "PERMISSIONS", "payload": {**common, "permission_profile": [p]}, "csv_row": r["row"]} for p, r in zip(profile, baseline)]})
        elif len(cash) != 1:
            errors.append({"row": 0, "reason": "基线必须恰有一行 BASELINE_CASH"})
        else:
            values = cash[0]["fields"]
            common = {"effective_at": values["effective_at"], "source": values["source"]}
            if any(any(r["fields"][k] != v for k, v in common.items()) for r in baseline):
                errors.append({"row": 0, "reason": "同一基线所有行的时点与来源必须一致"})
            payload = {**common, **{key: nullable(values[key]) for key in FIELDS["BASELINE_CASH"]}, "positions": [], "permission_profile": []}
            for row in baseline:
                f = row["fields"]
                if f["kind"] == "INITIAL_POSITION":
                    payload["positions"].append({"instrument": f["exchange"] + ":" + f["code"], "quantity": f["quantity"], "sellable_quantity": nullable(f["sellable_quantity"]), "reference_cost": nullable(f["reference_cost"])})
                elif f["kind"] == "PERMISSION":
                    payload["permission_profile"].append({"market": f["exchange"], "board": f["board"], "status": f["permission_status"], "basis": f["basis"]})
            checks = []
            for row in baseline:
                f = row["fields"]
                check = {**common, "cash_balance": "0.00", "broker_available": None, "broker_frozen": None, "withdrawable": None, "positions": [], "permission_profile": []}
                if f["kind"] == "BASELINE_CASH":
                    check.update({key: nullable(f[key]) for key in FIELDS["BASELINE_CASH"]})
                elif f["kind"] == "INITIAL_POSITION":
                    check["positions"] = [{"instrument": f["exchange"] + ":" + f["code"], "quantity": f["quantity"], "sellable_quantity": nullable(f["sellable_quantity"]), "reference_cost": nullable(f["reference_cost"])}]
                else:
                    check["permission_profile"] = [{"market": f["exchange"], "board": f["board"], "status": f["permission_status"], "basis": f["basis"]}]
                checks.append({"kind": "BASELINE", "payload": check, "csv_row": row["row"]})
            if commands:
                errors.append({"row": 0, "reason": "初始状态与后续事件必须分别上传，不能改变文件事件顺序"})
            commands.insert(0, {"kind": "BASELINE", "payload": payload, "csv_row": cash[0]["row"], "csv_checks": checks})
    return rows, commands, errors


class CsvImports:
    def __init__(self, ledger):
        self.ledger = ledger
        self.directory = ledger.path.parent / "raw" / "account-csv"
        self.directory.mkdir(parents=True, exist_ok=True)
        with ledger.connection() as db:
            db.execute("CREATE TABLE IF NOT EXISTS account_csv_imports(draft_id TEXT PRIMARY KEY, sha256 TEXT NOT NULL, metadata TEXT NOT NULL)")
            db.execute("CREATE INDEX IF NOT EXISTS account_csv_file_identity ON account_csv_imports(sha256)")

    def upload(self, raw, filename, encoding, version, revision_of=None):
        if not raw or len(raw) > 4 * 1024 * 1024:
            raise HTTPException(413, "CSV 必须非空且最多4MiB")
        if revision_of and self.get(revision_of)["receipt"]:
            raise HTTPException(409, "已确认文件不能修订；更正须追加账户事件")
        fingerprint = hashlib.sha256(raw).hexdigest()
        with self.ledger.connection() as db:
            prior = db.execute("SELECT draft_id FROM account_csv_imports WHERE sha256=? ORDER BY rowid LIMIT 1", (fingerprint,)).fetchone()
        if prior and revision_of is None:
            return self.get(prior[0])
        path = self.directory / fingerprint
        if not path.exists():
            temporary = self.directory / (str(uuid4()) + ".tmp")
            with temporary.open("wb") as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        rows, commands, errors = parse(raw, encoding, fingerprint)
        account = self.ledger.account()
        if version != account["version"]:
            errors.append({"row": 0, "reason": {"code": "ACCOUNT_VERSION_CONFLICT", "expected": version, "current": account["version"]}})
        command = {"kind": "CSV_BATCH", "expected_account_version": version,
                   "payload": {"source": "Roll CSV " + fingerprint, "effective_at": commands[-1]["payload"]["effective_at"] if commands else now(), "commands": commands, "errors": errors, "file_sha256": fingerprint}}
        # Invalid and stale materials remain queryable, but cannot publish facts.
        if version != account["version"]:
            command["expected_account_version"] = account["version"]
        warnings = []
        for item in commands:
            if item["kind"] == "FILL" and not item["payload"]["fill_id"]:
                warnings.append({"row": item["csv_row"], "reason": "缺少可靠分笔标识；跨文件相似行需核对是否独立成交，确认不会按价量去重"})
        metadata = {"file": {"sha256": fingerprint, "filename": Path(filename).name, "encoding": encoding, "size": len(raw), "uploaded_at": now(), "expected_account_version": version}, "rows": rows, "warnings": warnings, "revision_of": revision_of}
        with self.ledger.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                prior = db.execute("SELECT draft_id FROM account_csv_imports WHERE sha256=? ORDER BY rowid LIMIT 1", (fingerprint,)).fetchone()
                if prior and revision_of is None:
                    db.rollback()
                    return self.get(prior[0])
                current = self.ledger.account(db=db)
                if version != current["version"]:
                    command["payload"]["errors"].append({"row": 0, "reason": {"code": "ACCOUNT_VERSION_CONFLICT", "expected": version, "current": current["version"]}})
                    command["expected_account_version"] = current["version"]
                draft = self.ledger.draft(DraftCommand(**command), db)
                db.execute("INSERT INTO account_csv_imports VALUES(?,?,?)", (draft["draft_id"], fingerprint, encode(metadata)))
                if revision_of and draft["status"] == "READY":
                    receipt = db.execute("SELECT receipt FROM account_receipts WHERE json_extract(receipt,'$.draft_id')=?", (revision_of,)).fetchone()
                    if receipt:
                        raise HTTPException(409, "原草稿已在并发处理中确认，不能修订")
                    db.execute("UPDATE account_drafts SET status='SUPERSEDED' WHERE id=?", (revision_of,))
                db.commit()
            except BaseException:
                db.rollback()
                raise
        return self.get(draft["draft_id"])

    def revise(self, draft_id, command):
        original = self.get(draft_id)
        if original["receipt"]:
            raise HTTPException(409, "已确认文件不能修订；更正须追加账户事件")
        return self.upload(self.file(original["file"]["sha256"]), original["file"]["filename"], command.encoding, command.expected_account_version, draft_id)

    def get(self, draft_id):
        with self.ledger.connection() as db:
            row = db.execute("SELECT metadata FROM account_csv_imports WHERE draft_id=?", (draft_id,)).fetchone()
            if row is None:
                raise HTTPException(404, "CSV 草稿不存在")
            receipt = db.execute("SELECT receipt FROM account_receipts WHERE json_extract(receipt,'$.draft_id')=? ORDER BY rowid LIMIT 1", (draft_id,)).fetchone()
        return {**self.ledger.get_draft(draft_id), **json.loads(row[0]), "receipt": json.loads(receipt[0]) if receipt else None}

    def file(self, fingerprint):
        with self.ledger.connection() as db:
            row = db.execute("SELECT sha256 FROM account_csv_imports WHERE sha256=?", (fingerprint,)).fetchone()
        if row is None:
            raise HTTPException(404, "原始CSV不存在")
        path = self.directory / row[0]
        try:
            raw = path.read_bytes()
        except OSError:
            raise HTTPException(409, "原始文件不可读，不能确认或重放此文件")
        if hashlib.sha256(raw).hexdigest() != fingerprint:
            raise HTTPException(409, "原始文件指纹不匹配")
        return raw
