from pathlib import Path
from datetime import date, datetime
import os

from fastapi import FastAPI, Query, HTTPException, Request, Response
from fastapi.responses import FileResponse
from roll.accounts.csv_import import CsvImports, CsvRevision, template, guide

from roll.accounts.ledger import ConfirmCommand, DraftCommand, EquityHint, Ledger
from roll.config import data_directory
from roll.market.directory import MarketDirectory, WatchCommand, IdentityCommand, ScopeCommand
from roll.decisions.funding import Funding, FundingConfirmation, LossSample, capabilities


def create_app(directory: Path | None = None):
    app = FastAPI(title="Roll", version="0.1.0")
    ledger = Ledger(directory or data_directory())
    app.state.ledger = ledger
    imports = CsvImports(ledger)

    @app.get("/api/account/csv/template")
    def csv_template(version: str = "ROLL-CSV-2"):
        content = template(version)
        return Response(content, media_type="text/csv; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="roll-csv-{version[-1]}.csv"'})

    @app.get("/api/account/csv/guide")
    def csv_guide():
        return Response(guide(), media_type="text/html")

    @app.post("/api/account/csv/drafts", status_code=201)
    async def csv_draft(request: Request, filename: str, encoding: str, expected_account_version: int, revision_of: str | None = None):
        if expected_account_version < 0:
            raise HTTPException(422, "账户版本必须非负")
        raw = bytearray()
        async for chunk in request.stream():
            raw.extend(chunk)
            if len(raw) > 4 * 1024 * 1024:
                raise HTTPException(413, "CSV 最多4MiB")
        return imports.upload(bytes(raw), filename, encoding, expected_account_version, revision_of)

    @app.get("/api/account/csv/drafts/{draft_id}")
    def csv_get(draft_id: str):
        return imports.get(draft_id)

    @app.post("/api/account/csv/drafts/{draft_id}/revise", status_code=201)
    def csv_revise(draft_id: str, command: CsvRevision):
        return imports.revise(draft_id, command)

    @app.get("/api/account/csv/files/{fingerprint}")
    def csv_file(fingerprint: str):
        return Response(imports.file(fingerprint), media_type="application/octet-stream")
    market = MarketDirectory(ledger)
    app.state.market = market

    @app.get('/api/market/list')
    def market_list():
        return market.listing()

    @app.get('/api/market/list/versions/{version}')
    def market_version(version: int):
        return market.listing(version)

    @app.post('/api/market/watch')
    def market_watch(command: WatchCommand):
        return market.watch(command)

    @app.post('/api/market/identities')
    def market_identity(command: IdentityCommand):
        return market.identify(command)

    @app.post('/api/market/scope/check')
    def market_scope(command: ScopeCommand):
        return market.check_scope(command)

    @app.get('/api/market/history')
    def market_history():
        return market.history()

    @app.get('/api/market/calendar')
    def market_calendar(exchange: str, on: date = Query(alias='date'), at: datetime | None = None):
        result = market.rules.calendar(exchange, on, at)
        result['next_trading_day'] = market.rules.next_trading_day(exchange, on) if result['coverage'] != 'UNKNOWN' else None
        return result

    @app.get('/api/market/rules')
    def market_rules(exchange: str, board: str, instrument_type: str = 'STOCK', on: date | None = Query(None, alias='date')):
        return market.rules.rule(exchange, board, instrument_type, on)

    @app.get('/api/market/resale-date')
    def resale_date(exchange: str, board: str, buy_date: date, instrument_type: str = 'STOCK'):
        rule = market.rules.rule(exchange, board, instrument_type, buy_date)
        calendar = market.rules.calendar(exchange, buy_date)
        allowed = rule['implementation_status'] == 'ADAPTED' and calendar['is_trading_day'] is True
        return {'buy_date': buy_date.isoformat(), 'earliest_sell_date': market.rules.next_trading_day(exchange, buy_date) if allowed else None,
                'rule': rule, 'calendar': calendar, 'resale_source': market.rules.source('szse-a-share-resale'),
                'limitation': '最早日期不代表实际可卖数量或可成交，停牌/当前状态与账户事实须另核对'}

    @app.get('/api/market/sources')
    def market_sources():
        return list(market.rules.sources.values())

    @app.get('/api/market/sources/{source_id}/raw')
    def market_source_raw(source_id: str):
        source = market.rules.source(source_id)
        return FileResponse(market.rules.directory / source['archive_path'], media_type='application/octet-stream', filename=source['file'])
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
        if command.kind == "CSV_BATCH":
            raise HTTPException(422, "CSV 整批草稿只接受原文件上传，不接受外部生成的批命令")
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

    @app.post("/api/account/equity-hints",status_code=201)
    def equity_hint(command: EquityHint):
        return ledger.equity_hint(command)

    @app.get("/api/account/equity-hints")
    def equity_hints():
        return ledger.equity_hints()

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
            if any(d["command"]["kind"] in {"FILL","FEE_ADJUSTMENT"} for d in ledger.quarantined_drafts()):
                pending.append("成交输入待核，原始材料已保留，尚未影响账面现金与持仓")
            if any(d["command"]["kind"] in {"CASH_IN","CASH_OUT","DIVIDEND","INTEREST","TAX","FEE","PENDING_ITEM","SETTLEMENT","CASH_CORRECTION","SHARE_CHANGE"} for d in ledger.quarantined_drafts()):
                pending.append("资金或权益输入待核，原始材料已保留，尚未影响账面现金与持仓")
            if any(d["command"]["kind"] == "CSV_BATCH" for d in ledger.quarantined_drafts()):
                pending.append("CSV文件输入待核，原始材料已保留，尚未影响账面现金与持仓")
        pending.extend(account.get("latest_fill_facts",[]))
        for item in account.get("pending_items",[]):
            if item["status"] in {"OPEN","PARTIAL"}:
                pending.append(f"{item['record_id']} {'应收' if item['flow_category']=='INVESTMENT_INCOME' else '应付'}待结算 {item['outstanding_amount']} 元")
        for hint in ledger.equity_hints():
            pending.append(f"外部权益线索待核：{hint['content']}；来源 {hint['source']}，获知于 {hint['learned_at']}，未确认个人账户实际发生")
        return {"account": account, "formal_judgment": "DISABLED", "pending_items": pending,
                "funding": funding.current(), "technical_capability": capabilities(), "runtime_health": runtime_health()}

    return app
