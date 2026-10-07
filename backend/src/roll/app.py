from pathlib import Path
import os

from fastapi import FastAPI, HTTPException

from roll.accounts.ledger import ConfirmCommand, DraftCommand, Ledger
from roll.config import data_directory
from roll.decisions.funding import Funding, FundingConfirmation, LossSample, capabilities


def create_app(directory: Path | None = None):
    app = FastAPI(title="Roll", version="0.1.0")
    ledger = Ledger(directory or data_directory())
    app.state.ledger = ledger
    funding = Funding(ledger)

    if os.environ.get("ROLL_ENV") == "test":
        @app.post("/api/testing/funding-loss-samples")
        def loss_sample(command: LossSample):
            return funding.sample(command)

        @app.get("/api/testing/funding-loss-samples/{series_id}")
        def loss_samples(series_id: str):
            return funding.samples(series_id)

    @app.get("/api/funding")
    def current_funding():
        return funding.current()

    @app.get("/api/funding/versions/{version}")
    def funding_version(version: int):
        return funding.current(version)

    @app.post("/api/funding/confirm")
    def confirm_funding(command: FundingConfirmation):
        return funding.confirm(command)

    @app.get("/api/capabilities")
    def current_capabilities():
        return capabilities()

    @app.post("/api/formal/evaluate")
    @app.post("/api/formal/probability")
    def formal_closed():
        raise HTTPException(403, {"code": "TECHNICAL_CAPABILITY_UNGRANTED", "reason": capabilities()["reason"]})

    @app.get("/api/runtime/health")
    def runtime_health():
        ledger.account()
        return {"service": "RUNNING", "storage": "READABLE", "market": "NOT_CONNECTED",
                "backend": "NOT_CONFIGURED", "reason": "本机账户服务在线；市场和模型接入尚未配置"}

    @app.get("/api/health")
    def health():
        return {"status": "ok","environment":"test" if os.environ.get("ROLL_ENV")=="test" else "local"}

    @app.get("/api/account")
    def account():
        account=ledger.account()
        if ledger.quarantined_drafts():
            account["state"]="RECONCILE_REQUIRED"
        return account

    @app.get("/api/account/versions/{version}")
    def version(version: int):
        return ledger.account(version)

    @app.post("/api/account/drafts", status_code=201)
    def draft(command: DraftCommand):
        return ledger.draft(command)

    @app.get("/api/account/drafts/{draft_id}")
    def get_draft(draft_id: str):
        return ledger.get_draft(draft_id)

    @app.post("/api/account/confirm")
    def confirm(command: ConfirmCommand):
        return ledger.confirm(command)

    @app.get("/api/account/receipts/{receipt_id}")
    def receipt(receipt_id: str):
        return ledger.receipt(receipt_id)

    @app.get("/api/account/events")
    def events():
        return ledger.events()

    @app.get("/api/account/audit")
    def audit():
        return ledger.audit()

    @app.get("/api/account/replay")
    def replay():
        return ledger.replay()

    @app.get("/api/account/quarantined-drafts")
    def quarantined_drafts():
        return ledger.quarantined_drafts()

    @app.get("/api/today")
    def today():
        account = ledger.account()
        pending = []
        for position in account["positions"]:
            if position["sellable_quantity"] is None:
                pending.append(f"{position['instrument']} 可卖数量未知")
        for field, label in [("broker_available", "券商可用资金"), ("broker_frozen", "冻结资金")]:
            if account[field] is None:
                pending.append(f"{label}未知")
        if not account["permission_profile"] or any(p["status"] == "UNKNOWN" for p in account["permission_profile"]):
            pending.append("账户部分交易权限未知，未登记范围也按未知处理")
        for record in account.get("fees_pending",[]):
            pending.append(f"成交 {record} 费用暂估，现金与净收益待核")
        if ledger.quarantined_drafts():
            account["state"]="RECONCILE_REQUIRED"
            pending.append("成交输入待核，原始材料已保留，尚未影响账面现金与持仓")
        pending.extend(account.get("latest_fill_facts",[]))
        return {"account": account, "formal_judgment": "DISABLED", "pending_items": pending,
                "funding": funding.current(), "technical_capability": capabilities(), "runtime_health": runtime_health()}

    return app
