from pathlib import Path
from datetime import date, datetime
import os
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Query, HTTPException, Request, Response
from fastapi.responses import FileResponse
from roll.accounts.csv_import import CsvImports, CsvRevision, template, guide,VERSION

from roll.accounts.ledger import ConfirmCommand, DraftCommand, EquityHint, Ledger
from roll.accounts.cash_events import EVENT_FIELDS
from roll.accounts.reconcile import UseCheck,use_check,consistency
from roll.accounts.valuation import Valuations,ValuationRequest
from roll.accounts.corrections import active_events,fact_command
from roll.config import data_directory
from roll.market.directory import MarketDirectory, WatchCommand, IdentityCommand, ScopeCommand
from roll.market.evidence import EvidenceStore, DataRequest
from roll.market.source_facts import REGISTRY
from roll.agents.codex_evidence import CodexEvidence, CodexQuestion
from roll.agents.deepseek_evidence import DeepSeekEvidence, DeepSeekQuestion
from roll.market.resolution import SourceResolutions, ResolutionCommand
from roll.market.verification import IndependentVerifications, VerificationCommand
from roll.research.registry import ExperimentRegistry, ProtocolCommand, AttemptCommand, FinishCommand, FreezeCommand, ReasonCommand, CheckpointCommand, deadline_preview
from roll.research.datasets import DatasetCommand
from roll.research.execution import DailyExecutions,ExecutionCommand,AssessmentCommand
from roll.decisions.funding import Funding, FundingConfirmation, LossSample, capabilities


def create_app(directory: Path | None = None, market_transport=None, market_clock=None, codex_worker: Path | None = None, deepseek_endpoint: str | None = None):
    @asynccontextmanager
    async def lifespan(application):
        yield
        await asyncio.to_thread(application.state.codex.close)
        await asyncio.to_thread(application.state.deepseek.close)

    app = FastAPI(title="Roll", version="0.1.0", lifespan=lifespan)
    ledger = Ledger(directory or data_directory())
    app.state.ledger = ledger
    imports = CsvImports(ledger)

    @app.get("/api/account/csv/template")
    def csv_template(version: str = VERSION):
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
    evidence=EvidenceStore(ledger,market,market_transport)
    app.state.evidence=evidence
    research=ExperimentRegistry(ledger,evidence)
    app.state.research=research
    executions=DailyExecutions(research)
    app.state.executions=executions

    @app.post('/api/research/protocols/{protocol_id}/executions',status_code=201)
    def research_execution(protocol_id:str,command:ExecutionCommand):
        return executions.create(protocol_id,command)

    @app.get('/api/research/executions/{execution_id}')
    def research_execution_get(execution_id:str):
        return executions.get(execution_id)

    @app.post('/api/research/executions/{execution_id}/replay')
    def research_execution_replay(execution_id:str):
        return executions.replay(execution_id)

    @app.post('/api/research/executions/{execution_id}/assessments',status_code=201)
    def research_execution_assess(execution_id:str,command:AssessmentCommand):
        return executions.assess(execution_id,command)

    @app.get('/api/research/protocols/{protocol_id}/execution-support')
    def research_execution_support(protocol_id:str,partition:str|None=None):
        if partition is not None and partition not in {'DEVELOPMENT','CALIBRATION'}:raise HTTPException(422,'支持查询仅开发/校准')
        return executions.support(protocol_id,partition)

    @app.get('/api/research/deadline-preview')
    def research_deadline_preview(start:datetime):
        return deadline_preview(start)

    @app.post('/api/research/datasets',status_code=201)
    def register_research_dataset(command:DatasetCommand):
        return research.register_dataset(command)

    @app.get('/api/research/datasets')
    def research_datasets():
        return research.datasets()

    @app.get('/api/research/datasets/{dataset_id}')
    def research_dataset(dataset_id:str):
        return research.dataset(dataset_id)

    @app.get('/api/research/datasets/{dataset_id}/partitions/{name}')
    def research_partition(dataset_id:str,name:str):
        return research.partition(dataset_id,name)

    @app.post('/api/research/protocols',status_code=201)
    def register_protocol(command:ProtocolCommand):
        return research.register(command)

    @app.get('/api/research/protocols')
    def research_protocols():
        return research.protocols()

    @app.get('/api/research/protocols/{protocol_id}')
    def research_protocol(protocol_id:str):
        return research.get(protocol_id)

    @app.post('/api/research/protocols/{protocol_id}/attempts',status_code=201)
    def research_attempt(protocol_id:str,command:AttemptCommand):
        return research.start_attempt(protocol_id,command)

    @app.get('/api/research/protocols/{protocol_id}/attempts')
    def research_attempts(protocol_id:str):
        return research.attempts(protocol_id)

    @app.get('/api/research/protocols/{protocol_id}/attempt-manifest')
    def research_attempt_manifest(protocol_id:str):
        return research.attempt_manifest(protocol_id)

    @app.post('/api/research/attempts/{attempt_id}/finish')
    def finish_research_attempt(attempt_id:str,command:FinishCommand):
        return research.finish_attempt(attempt_id,command)

    @app.get('/api/research/protocols/{protocol_id}/audit')
    def research_audit(protocol_id:str):
        return research.audit(protocol_id)

    @app.post('/api/research/protocols/{protocol_id}/freeze')
    def research_freeze(protocol_id:str,command:FreezeCommand):
        return research.freeze(protocol_id,command)

    @app.post('/api/research/protocols/{protocol_id}/sealed-input')
    def research_sealed(protocol_id:str,command:ReasonCommand):
        return research.sealed_input(protocol_id,command)

    @app.post('/api/research/protocols/{protocol_id}/checkpoints',status_code=201)
    def research_checkpoint(protocol_id:str,command:CheckpointCommand):
        return research.checkpoint(protocol_id,command)
    valuations=Valuations(ledger,evidence)
    app.state.valuations=valuations

    @app.post('/api/account/valuations',status_code=201)
    def publish_valuation(command:ValuationRequest):
        return valuations.publish(command)

    @app.get('/api/account/valuation-basis')
    def valuation_basis():
        return valuations.basis()

    @app.get('/api/account/valuations')
    def valuation_history():
        return valuations.history()

    @app.get('/api/account/valuations/current')
    def current_valuation():
        return valuations.get()

    @app.get('/api/account/valuations/{identifier}')
    def get_valuation(identifier:str):
        return valuations.get(identifier)

    @app.post('/api/account/valuations/{identifier}/replay')
    def replay_valuation(identifier:str):
        return valuations.get(identifier,replay=True)
    codex = CodexEvidence(evidence, codex_worker, input_observer=research.market_input_exposed)
    app.state.codex = codex
    deepseek=DeepSeekEvidence(evidence,deepseek_endpoint,input_observer=research.market_input_exposed)
    app.state.deepseek=deepseek

    @app.post('/api/data/requests/{request_id}/deepseek',status_code=202)
    def deepseek_start(request_id:str,command:DeepSeekQuestion):
        return deepseek.start(request_id,command)

    @app.post('/api/data/requests/{request_id}/codex', status_code=202)
    def codex_start(request_id: str, command: CodexQuestion):
        return codex.start(request_id, command)

    @app.post('/api/data/runs/{run_id}/cancel')
    def codex_cancel(run_id: str):
        run=evidence.get('retrieval_runs',run_id)
        return deepseek.cancel(run_id) if run['backend']=='DEEPSEEK' else codex.cancel(run_id)
    resolutions=SourceResolutions(evidence,market_clock)
    app.state.resolutions=resolutions
    verifications=IndependentVerifications(evidence)
    app.state.verifications=verifications

    @app.post('/api/data/verifications',status_code=201)
    def verify_review_evidence(command:VerificationCommand):
        return research.market_input_exposed(verifications.create(command),'verification-create')

    @app.get('/api/data/verifications')
    def verification_history():
        return research.market_input_exposed(verifications.history(),'verification-history')

    @app.get('/api/data/verifications/{verification_id}')
    def verification(verification_id:str):
        return research.market_input_exposed(verifications.get(verification_id),'verification-query')

    @app.post('/api/data/verifications/{verification_id}/replay')
    def verification_replay(verification_id:str):
        return research.market_input_exposed(verifications.replay(verification_id),'verification-replay')

    @app.post('/api/data/requests/{request_id}/resolve',status_code=202)
    def data_resolve(request_id:str,command:ResolutionCommand):
        return resolutions.start(request_id,command)

    @app.get('/api/data/resolutions')
    def data_resolutions():
        return resolutions.history()

    @app.get('/api/data/resolutions/{resolution_id}')
    def data_resolution(resolution_id:str):
        return research.market_input_exposed(resolutions.get(resolution_id),'resolution')

    @app.get('/api/data/dependencies')
    def data_dependencies(resolution_id:str|None=None):
        return resolutions.dependencies(resolution_id)

    @app.post('/api/data/resolutions/{resolution_id}/replay')
    def replay_resolution(resolution_id:str):
        return research.market_input_exposed(resolutions.replay(resolution_id),'resolution-replay')

    @app.get('/api/data/replays/{replay_id}')
    def data_resolution_replay(replay_id:str):
        return research.market_input_exposed(evidence.get('source_resolution_replays',replay_id),'resolution-replay-query')

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
        return research.market_input_exposed(evidence.snapshots(instrument,group,available_before),'snapshots-query')

    @app.get('/api/data/coverage')
    def data_coverage(instrument:str|None=None,group:str|None=None):
        return evidence.coverage(instrument,group)

    @app.get('/api/data/observations')
    def data_observations(instrument:str|None=None):
        return research.market_input_exposed([{**observation,'snapshot_id':snapshot['snapshot_id'],'run_id':snapshot['run_id'],
            'dependency_status':'INVALIDATED' if resolutions.dependencies(target_id=observation['observation_id']) else 'CURRENT'}
            for snapshot in evidence.snapshots(instrument) for observation in snapshot['observations']
            if not instrument or observation['instrument']==instrument],'observations-query')

    @app.post('/api/data/requests',status_code=201)
    def data_request(command:DataRequest):
        return evidence.request(command)

    @app.get('/api/data/requests/{request_id}')
    def get_data_request(request_id:str):
        return evidence.get('data_requests',request_id)

    @app.post('/api/data/requests/{request_id}/retrieve')
    def data_retrieve(request_id:str):
        return research.market_input_exposed(evidence.retrieve(request_id),'direct-retrieval')

    @app.get('/api/data/runs/{run_id}')
    def data_run(run_id:str):
        return evidence.get('retrieval_runs',run_id)

    @app.get('/api/data/snapshots/{snapshot_id}')
    def data_snapshot(snapshot_id:str):
        return research.market_input_exposed(evidence.get('market_evidence_snapshots',snapshot_id),'snapshot-query')

    @app.get('/api/data/archives/{sha}')
    def data_archive(sha:str):
        path=evidence.raw(sha)
        research.archive_exposed(sha)
        return FileResponse(path,media_type='application/octet-stream',filename=path.name,headers={'X-Content-Type-Options':'nosniff'})

    @app.post('/api/data/runs/{run_id}/replay')
    def data_replay(run_id:str):
        return research.market_input_exposed(evidence.replay(run_id),'run-replay')

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

    @app.post("/api/account/use-check")
    def account_use(command:UseCheck):
        from roll.accounts.ledger import timestamp
        return use_check(ledger.account(),ledger.pending_drafts(),command,timestamp,ledger.events())

    @app.get("/api/account")
    def account():
        account=ledger.account()
        account["state"],reasons=consistency(account,ledger.pending_drafts())
        if reasons:account["state_reasons"]=reasons
        return account

    @app.get("/api/account/versions/{version}")
    def version(version: int):
        return ledger.account(version)

    @app.get("/api/account/as-of")
    def as_of(known_by: datetime | None = None, effective_at: datetime | None = None):
        from roll.accounts.ledger import timestamp,now
        known=timestamp(known_by.isoformat(),"known_by") if known_by else now()
        effective=timestamp(effective_at.isoformat()) if effective_at else now()
        return {"known_by":known,"effective_at":effective,"account":ledger.replay(known_by=known,effective_at=effective),"limitation":"按当时已知与实际发生时点重建；已发布版本仍由原版本查询"}

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

    @app.get("/api/account/correction-candidates")
    def correction_candidates():
        history=ledger.events()
        active,chain,heads=active_events(history)
        candidates=[]
        for root,head in heads.items():
            original=next(e for e in history if e["event_id"]==root)
            if original["event_type"] in {"INITIAL_CASH","INITIAL_POSITION"}:continue
            fact=next((e for e in active if e.get("root_event_id",e.get("event_id"))==root),original)
            candidates.append({"root_event_id":root,"target_event_id":head,"reversed":not any(e.get("root_event_id",e.get("event_id"))==root for e in active),"command":fact_command(fact)})
        return candidates

    @app.get("/api/account/audit")
    def audit():
        return ledger.audit()

    @app.get("/api/account/replay")
    def replay():
        return ledger.replay()

    @app.get("/api/account/quarantined-drafts")
    def quarantined_drafts():
        return ledger.quarantined_drafts()

    @app.get("/api/account/pending-drafts")
    def pending_drafts():
        return ledger.pending_drafts()

    @app.post("/api/account/equity-hints",status_code=201)
    def equity_hint(command: EquityHint):
        return ledger.equity_hint(command)

    @app.get("/api/account/equity-hints")
    def equity_hints():
        return ledger.equity_hints()

    @app.get("/api/today")
    def today():
        account = ledger.account()
        account["state"],reasons=consistency(account,ledger.pending_drafts())
        if reasons:account["state_reasons"]=reasons
        pending = list(reasons)
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
            if any(d["command"]["kind"] in EVENT_FIELDS for d in ledger.quarantined_drafts()):
                pending.append("资金或权益输入待核，原始材料已保留，尚未影响账面现金与持仓")
            if any(d["command"]["kind"] == "CSV_BATCH" for d in ledger.quarantined_drafts()):
                pending.append("CSV文件输入待核，原始材料已保留，尚未影响账面现金与持仓")
        pending.extend(account.get("latest_fill_facts",[]))
        for record in account.get("rights_fee_breakdown_pending",[]):
            pending.append(f"配股 {record} 费用分拆待核；实际总支付已确认，费用前损益未知")
        for item in account.get("pending_items",[]):
            if item["status"] in {"OPEN","PARTIAL"}:
                pending.append(f"{item['record_id']} {'应收' if item['flow_category']=='INVESTMENT_INCOME' else '应付'}待结算 {item['outstanding_amount']} 元")
        for hint in ledger.equity_hints():
            pending.append(f"外部权益线索待核：{hint['content']}；来源 {hint['source']}，获知于 {hint['learned_at']}，未确认个人账户实际发生")
        return {"account": account, "formal_judgment": "DISABLED", "pending_items": pending,
                "funding": funding.current(), "technical_capability": capabilities(), "runtime_health": runtime_health()}

    return app
