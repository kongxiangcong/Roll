from pathlib import Path

from fastapi import FastAPI

from roll.accounts.ledger import ConfirmCommand, DraftCommand, Ledger
from roll.config import data_directory


def create_app(directory: Path | None = None):
    app = FastAPI(title="Roll", version="0.1.0")
    ledger = Ledger(directory or data_directory())
    app.state.ledger = ledger

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    @app.get("/api/account")
    def account():
        return ledger.account()

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
        return {"account": account, "formal_judgment": "DISABLED", "pending_items": pending}

    return app
