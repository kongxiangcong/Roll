from pathlib import Path
from datetime import date, datetime
import os

from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import FileResponse

from roll.accounts.ledger import ConfirmCommand, DraftCommand, Ledger
from roll.config import data_directory
from roll.market.directory import MarketDirectory, WatchCommand, IdentityCommand, ScopeCommand
from roll.market.evidence import EvidenceStore, DataRequest
from roll.market.source_facts import REGISTRY
from roll.decisions.funding import Funding, FundingConfirmation, LossSample, capabilities


def create_app(directory: Path | None = None, market_transport=None):
    app = FastAPI(title="Roll", version="0.1.0")
    ledger = Ledger(directory or data_directory())
    app.state.ledger = ledger
    market = MarketDirectory(ledger)
    app.state.market = market
    evidence=EvidenceStore(ledger,market,market_transport)
    app.state.evidence=evidence

    @app.get('/api/data/sources')
    def data_sources():
        return REGISTRY

    @app.get('/api/data/runs')
    def data_runs():
        with ledger.connection() as db:
            import json
            return [json.loads(row[0]) for row in db.execute('SELECT value FROM retrieval_runs ORDER BY rowid DESC LIMIT 100')]

    @app.get('/api/data/snapshots')
    def data_snapshots(instrument:str|None=None,group:str|None=None,available_before:datetime|None=None):
        return evidence.snapshots(instrument,group,available_before)

    @app.get('/api/data/coverage')
    def data_coverage(instrument:str|None=None,group:str|None=None):
        return evidence.coverage(instrument,group)

    @app.get('/api/data/observations')
    def data_observations(instrument:str|None=None):
        return [{**observation,'snapshot_id':snapshot['snapshot_id'],'run_id':snapshot['run_id']}
            for snapshot in evidence.snapshots(instrument) for observation in snapshot['observations']
            if not instrument or observation['instrument']==instrument]

    @app.post('/api/data/requests',status_code=201)
    def data_request(command:DataRequest):
        return evidence.request(command)

    @app.get('/api/data/requests/{request_id}')
    def get_data_request(request_id:str):
        return evidence.get('data_requests',request_id)

    @app.post('/api/data/requests/{request_id}/retrieve')
    def data_retrieve(request_id:str):
        return evidence.retrieve(request_id)

    @app.get('/api/data/runs/{run_id}')
    def data_run(run_id:str):
        return evidence.get('retrieval_runs',run_id)

    @app.get('/api/data/snapshots/{snapshot_id}')
    def data_snapshot(snapshot_id:str):
        return evidence.get('market_evidence_snapshots',snapshot_id)

    @app.get('/api/data/archives/{sha}')
    def data_archive(sha:str):
        path=evidence.raw(sha)
        return FileResponse(path,media_type='application/octet-stream',filename=path.name,headers={'X-Content-Type-Options':'nosniff'})

    @app.post('/api/data/runs/{run_id}/replay')
    def data_replay(run_id:str):
        return evidence.replay(run_id)

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
        return FileResponse(market.rules.directory / source['archive_path'], media_type='application/octet-stream', filename=source['file'],headers={'X-Content-Type-Options':'nosniff'})
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
        return {"service": "RUNNING", "storage": "READABLE", "market": "FINITE_REQUEST_ADAPTER_AVAILABLE",
                "backend": "NOT_CONFIGURED", "reason": "本机账户与有限市场取证接口在线；实际覆盖、缺口及时效逐请求核对，模型接入尚未配置"}

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
