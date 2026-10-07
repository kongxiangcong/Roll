"""User funding boundaries; this module does not grant technical capability."""
import hashlib
import json
import re
from typing import Literal
from uuid import uuid4
from datetime import datetime, timezone

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field
from decimal import Decimal, localcontext

from roll.accounts.ledger import encode, now, number, timestamp, text_value


FORMULA_VERSION = "cashflow-adjusted-loss-v1"


def instant(raw, field="effective_at"):
    return datetime.fromisoformat(timestamp(raw, field)).astimezone(timezone.utc).isoformat()


class LossFacts(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    scope_kind: Literal["ACCOUNT", "TRIAL_ACTUAL"]
    scope_id: str
    baseline_account_version: int
    origin_at: str
    as_of: str
    facts_version: str = Field(min_length=1)
    valuation_status: Literal["COMPLETE", "STALE", "MISSING"]
    baseline_assets: str | None
    net_assets: str | None
    external_in: str | None
    external_out: str | None
    realized_pnl: str | None
    unrealized_pnl: str | None
    income: str | None
    fees: str | None
    pending_income_delta: str | None
    pending_expense_delta: str | None


class LossSample(BaseModel):
    model_config = ConfigDict(extra="forbid")
    series_id: str = Field(min_length=1, max_length=128)
    facts: LossFacts


def evaluate_loss(authorization, facts: LossFacts, previous=None):
    """Pure contract for future trusted ACTUAL facts; caller owns storage/authority.

    All components are cumulative changes from the same immutable loss origin.
    Net assets include pending claims/liabilities. Frozen cash is not subtracted.
    """
    value = facts.model_dump()
    origin, as_of = instant(value["origin_at"]), instant(value["as_of"], "as_of")
    if any(value[key] != authorization[key] for key in ["scope_kind", "scope_id", "baseline_account_version"]) or origin != authorization["loss_origin_at"]:
        raise HTTPException(422, "损失事实与授权范围/基线/起点不匹配")
    if as_of < origin:
        raise HTTPException(422, "损失事实不能早于起点")
    amounts = {}
    for key in ["baseline_assets", "net_assets", "external_in", "external_out", "realized_pnl", "unrealized_pnl", "income", "fees", "pending_income_delta", "pending_expense_delta"]:
        raw = value[key]
        if raw is None:
            amounts[key] = None
        elif not re.fullmatch(r"-?\d{1,18}(?:\.\d{1,2})?", raw):
            raise HTTPException(422, f"{key}: 需要最多两位小数的精确十进制字符串")
        else:
            amounts[key] = Decimal(raw)
    for key in ["baseline_assets", "external_in", "external_out"]:
        if amounts[key] is not None and amounts[key] < 0:
            raise HTTPException(422, f"{key}: 不能为负")
    known_baseline = previous.get("baseline_assets") if previous else None
    current_baseline = format(amounts["baseline_assets"], ".2f") if amounts["baseline_assets"] is not None else None
    if previous and (as_of < previous["as_of"] or (known_baseline is not None and current_baseline is not None and current_baseline != known_baseline)):
        raise HTTPException(409, "不能倒退损失观察时点或改写基线净资产")
    result = {"formula_version": FORMULA_VERSION, "authorization_version": authorization["version"],
              "scope_kind": value["scope_kind"], "scope_id": value["scope_id"], "origin_at": origin,
              "baseline_account_version": value["baseline_account_version"], "as_of": as_of,
              "facts_version": value["facts_version"], "baseline_assets": current_baseline or known_baseline, "pnl": None, "loss": None,
              "remaining_loss_allowance": None, "peak_loss": previous.get("peak_loss") if previous else None,
              "triggered": previous.get("triggered", False) if previous else False}
    if value["valuation_status"] != "COMPLETE" or None in amounts.values():
        return {**result, "status": "RESTRICTED", "reason": "陈旧/缺失估值或必需事实不足，损失与剩余额度未知"}
    with localcontext() as context:
        context.prec = 50
        pnl = amounts["realized_pnl"] + amounts["unrealized_pnl"] + amounts["income"] - amounts["fees"] + amounts["pending_income_delta"] - amounts["pending_expense_delta"]
        assets_pnl = amounts["net_assets"] - amounts["baseline_assets"] - amounts["external_in"] + amounts["external_out"]
        if pnl != assets_pnl:
            return {**result, "status": "RESTRICTED", "reason": "净资产现金流口径与损益分项不守恒，须核对"}
        loss = max(Decimal(0), -pnl)
        peak = max(Decimal(result["peak_loss"] or "0.00"), loss)
        threshold = Decimal(authorization["loss_threshold"])
        return {**result, "pnl": format(pnl, ".2f"), "loss": format(loss, ".2f"), "peak_loss": format(peak, ".2f"),
                "remaining_loss_allowance": format(max(Decimal(0), threshold - peak), ".2f"),
                "triggered": result["triggered"] or peak >= threshold, "status": "PAUSED" if result["triggered"] or peak >= threshold else "WITHIN_BOUNDARY"}


class Authorization(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    scope_kind: Literal["ACCOUNT", "TRIAL_ACTUAL"]
    scope_id: str = Field(min_length=1)
    purpose: str = Field(min_length=1)
    capital_amount: str
    total_exposure: str
    single_exposure: str
    cash_reserve: str
    loss_threshold: str
    effective_at: str
    basis: str = Field(min_length=1)
    enabled: bool
    pause: bool = False


class FundingConfirmation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=0)
    idempotency_key: str = Field(min_length=1, max_length=128)
    authorization: Authorization


class Funding:
    def __init__(self, ledger):
        self.ledger = ledger
        with ledger.connection() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS funding_versions(version INTEGER PRIMARY KEY, snapshot TEXT NOT NULL,
                    idempotency_key TEXT UNIQUE NOT NULL, content_hash TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS schema_migrations(name TEXT PRIMARY KEY, applied_at TEXT NOT NULL);
            """)
            db.execute("INSERT OR IGNORE INTO schema_migrations VALUES(?,?)", ("10-funding-v1", now()))

    def current(self, version=None, db=None):
        if db is None:
            with self.ledger.connection() as connection:
                return self.current(version, connection)
        row = db.execute("SELECT snapshot FROM funding_versions ORDER BY version DESC LIMIT 1" if version is None
                         else "SELECT snapshot FROM funding_versions WHERE version=?", () if version is None else (version,)).fetchone()
        if row:
            return json.loads(row[0])
        if version not in (None, 0):
            raise HTTPException(404, "资金授权版本不存在")
        return {"version": 0, "state": "UNCONFIRMED", "loss_status": "PENDING_FACTS",
                "remaining_loss_allowance": None, "formula_version": FORMULA_VERSION}

    def confirm(self, command: FundingConfirmation):
        fingerprint = hashlib.sha256(encode(command.model_dump(exclude={"idempotency_key"})).encode()).hexdigest()
        with self.ledger.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                prior = db.execute("SELECT content_hash,snapshot FROM funding_versions WHERE idempotency_key=?",
                                   (command.idempotency_key,)).fetchone()
                if prior:
                    if prior[0] != fingerprint:
                        raise HTTPException(409, {"code": "IDEMPOTENCY_CONTENT_CONFLICT"})
                    db.rollback()
                    return json.loads(prior[1])
                current = self.current(db=db)
                if current["version"] != command.expected_version:
                    raise HTTPException(409, {"code": "FUNDING_VERSION_CONFLICT", "current": current})
                account = self.ledger.account(db=db)
                if account["version"] == 0:
                    raise HTTPException(409, "请先确认真实账户基线")
                value = command.authorization.model_dump()
                value["effective_at"] = instant(value["effective_at"])
                for field in ["scope_id", "purpose", "basis"]:
                    value[field] = text_value(value[field], field)
                for field in ["capital_amount", "total_exposure", "single_exposure", "cash_reserve", "loss_threshold"]:
                    value[field] = number(value[field], field)
                amount, total, single, reserve, threshold = [Decimal(value[key]) for key in
                    ["capital_amount", "total_exposure", "single_exposure", "cash_reserve", "loss_threshold"]]
                if amount <= 0 or threshold <= 0 or single > total or total + reserve > amount or threshold > amount:
                    raise HTTPException(422, "金额/损失阈值须正数，单票不超过总暴露，总暴露加现金保留不超过资金金额，阈值不超过金额")
                value.update(version=current["version"] + 1, confirmed_at=now(), receipt_id=str(uuid4()),
                             formula_version=FORMULA_VERSION, loss_status="PENDING_FACTS", remaining_loss_allowance=None,
                             baseline_account_version=current.get("baseline_account_version", account["version"]),
                             loss_origin_at=current.get("loss_origin_at", value["effective_at"]))
                if current["version"] and (value["scope_id"], value["scope_kind"]) != (current["scope_id"], current["scope_kind"]):
                    raise HTTPException(409, "当前授权链不能更换损失范围；须保留原范围历史")
                if value["effective_at"] < value["loss_origin_at"]:
                    raise HTTPException(422, "授权生效时点不能早于首次授权起点")
                value["pause_latched"] = current.get("pause_latched", False) or value["pause"]
                value["state"] = "REVOKED" if not value["enabled"] else "PAUSED" if value["pause_latched"] else "CONFIRMED"
                db.execute("INSERT INTO funding_versions VALUES(?,?,?,?)", (value["version"], encode(value), command.idempotency_key, fingerprint))
                db.commit()
                return value
            except BaseException:
                db.rollback()
                raise

    def sample(self, command: LossSample):
        # Only called by the test-only route. Never writes production loss state.
        with self.ledger.connection() as db:
            db.execute("CREATE TABLE IF NOT EXISTS funding_method_samples(series_id TEXT, sequence INTEGER, facts_version TEXT, input_hash TEXT, result TEXT, PRIMARY KEY(series_id,sequence), UNIQUE(series_id,facts_version))")
            db.execute("BEGIN IMMEDIATE")
            try:
                authorization = self.current(db=db)
                if not authorization["version"]:
                    raise HTTPException(409, "请先确认资金边界")
                fingerprint = hashlib.sha256(encode({"authorization_version": authorization["version"], "facts": command.facts.model_dump()}).encode()).hexdigest()
                prior = db.execute("SELECT input_hash,result FROM funding_method_samples WHERE series_id=? AND facts_version=?", (command.series_id, command.facts.facts_version)).fetchone()
                if prior:
                    if prior[0] != fingerprint:
                        raise HTTPException(409, "样例事实版本内容冲突")
                    db.rollback()
                    return json.loads(prior[1])
                previous = db.execute("SELECT sequence,result FROM funding_method_samples WHERE series_id=? ORDER BY sequence DESC LIMIT 1", (command.series_id,)).fetchone()
                result = {**evaluate_loss(authorization, command.facts, json.loads(previous[1]) if previous else None),
                          "namespace": "ACCOUNT_CONDITIONAL", "input_authority": "UNTRUSTED_SAMPLE", "purpose": "METHOD_VALIDATION"}
                db.execute("INSERT INTO funding_method_samples VALUES(?,?,?,?,?)", (command.series_id, previous[0]+1 if previous else 1, command.facts.facts_version, fingerprint, encode(result)))
                db.commit()
                return result
            except BaseException:
                db.rollback()
                raise

    def samples(self, series_id):
        with self.ledger.connection() as db:
            exists = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='funding_method_samples'").fetchone()
            return [json.loads(row[0]) for row in db.execute("SELECT result FROM funding_method_samples WHERE series_id=? ORDER BY sequence", (series_id,))] if exists else []


def capabilities():
    return {"state": "UNGRANTED", "formal_judgment": "DISABLED", "reason": "尚无通过验证及受控登记的技术能力", "allowed_actions": []}
