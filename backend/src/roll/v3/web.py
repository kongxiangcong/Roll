"""Local HTTP and browser adapters for the Roll v3 application."""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from roll.v3.account import AccountLedger
from roll.v3.development_archive import archive_development
from roll.v3.development_experiment import PRESET_ID, development_preset
from roll.v3.development_interpretation import is_development
from roll.v3.development_replay import prepare_development, read_development_receipt
from roll.v3.experiment import list_experiments, read_experiment
from roll.v3.harness_settings import settings as harness_settings
from roll.v3.market import list_snapshots, utc_timestamp
from roll.v3.market_research import DEFAULT_BENCHMARK, DEFAULT_START, export_market_research
from roll.v3.market_sources import sync_daily_market
from roll.v3.overview import MarketSyncRunner, build_overview
from roll.v3.plan import PlanLedger, generate_plans
from roll.v3.watchlist import add_watchlist, list_watchlist, remove_watchlist, reorder_watchlist
from roll.v3.research import ResearchDossiers
from roll.v3.research_runner import ResearchRunner
from roll.v3.research_tasks import (
    _DEFAULT_HARNESS,
    _default_snapshot_for_symbol,
    build_followup_manifest,
    cancel_attempt,
    collect_materials,
    enqueue_retry,
    enqueue_task,
    freeze_manifest,
    get_attempt,
    get_task,
    list_tasks,
)
from roll.v3.review import DecisionLedger
from roll.v3.storage import instant
from roll.v3.strategy import StrategyRegistry


ASSETS = Path(__file__).with_name("workbench")


class HarnessSelection(BaseModel):
    name: str | None


class DraftInput(BaseModel):
    markdown: str
    version: str | None = None


class PublicationInput(BaseModel):
    version: str
    reviewer: str
    effective_at: str | None = None


class PlanInput(BaseModel):
    book_id: str = "real"
    as_of: str | None = None
    symbols: list[str] = Field(default_factory=list)
    snapshot_id: str | None = None


class RegistrationInput(PlanInput):
    strategy_versions: list[str] = Field(default_factory=list)
    price_only: bool | None = None
    mode: str = "live"
    now: str | None = None


class ReviewClock(BaseModel):
    now: str | None = None


class OutcomeInput(ReviewClock):
    symbol: str
    status: str
    reason: str | None = None
    reported_at: str | None = None
    plan_id: str | None = None
    fill: dict | None = None


class FindingInput(ReviewClock):
    symbol: str
    category: str
    reason: str
    evidence_refs: list[str] = Field(default_factory=list)
    trigger_id: str | None = None


class ResearchTaskInput(BaseModel):
    symbol: str
    question: str
    as_of: str | None = None
    snapshot_id: str | None = None
    basis: str | None = None
    required_titles: list[str] = Field(default_factory=list)
    materials: list[dict] = Field(default_factory=list)
    executor: str | None = None
    timeout: float = 180


class FollowupTaskInput(BaseModel):
    followup_id: str
    as_of: str | None = None
    snapshot_id: str | None = None
    basis: str | None = None
    materials: list[dict] = Field(default_factory=list)
    executor: str | None = None
    timeout: float = 180


class RetryTaskInput(BaseModel):
    executor: str | None = None
    timeout: float = 180


class SupplementTaskInput(BaseModel):
    materials: list[dict] = Field(default_factory=list)
    snapshot_id: str | None = None
    as_of: str | None = None
    executor: str | None = None
    timeout: float = 180


class DevelopmentTaskInput(BaseModel):
    preset_id: str = PRESET_ID
    snapshot_id: str | None = None
    executor: str | None = None
    timeout: float = 180


class DevelopmentArchiveInput(BaseModel):
    attempt_id: str
    report_version: str
    conclusion: str
    reviewer: str
    decision: str
    reason: str
    segment_refs: list[str] = Field(default_factory=list)
    sizing_rule: str | None = None
    measurement: str | None = None


class WatchlistAddInput(BaseModel):
    symbol: str
    name: str | None = None


class WatchlistOrderInput(BaseModel):
    symbols: list[str] = Field(default_factory=list)


class MarketSyncInput(BaseModel):
    symbols: list[str] = Field(default_factory=list)
    start: str = "2020-01-02"
    refresh: bool = False


def create_app(data_dir, *, research_executor=_DEFAULT_HARNESS, market_sync_fn=sync_daily_market):
    runner = ResearchRunner(data_dir, default_executor=research_executor)
    sync_runner = MarketSyncRunner(data_dir, sync_fn=market_sync_fn)

    @asynccontextmanager
    async def lifespan(_app):
        runner.recover_orphans()
        try:
            yield
        finally:
            runner.shutdown(wait=True)

    app = FastAPI(title="Roll 盘后工作台", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    app.state.research_runner = runner
    app.state.market_sync_runner = sync_runner
    dossiers = ResearchDossiers(data_dir)
    decisions = DecisionLedger(data_dir)
    plans = PlanLedger(data_dir)
    accounts = AccountLedger(data_dir)
    registry = StrategyRegistry(data_dir)

    def _submit(receipt, executor_name=None, timeout=180):
        if receipt["status"] == "pending":
            runner.submit(receipt["attempt_id"], executor_name=executor_name, timeout=timeout)
        return receipt

    @app.get("/")
    def index():
        return FileResponse(ASSETS / "index.html")

    @app.get("/api/overview")
    def overview(book_id: str = "real", as_of: str | None = None):
        return build_overview(data_dir, book_id=book_id, as_of=as_of)

    @app.get("/api/watchlist")
    def get_watchlist():
        return list_watchlist(data_dir)

    @app.post("/api/watchlist")
    def create_watchlist_item(payload: WatchlistAddInput):
        return add_watchlist(data_dir, payload.symbol, name=payload.name)

    @app.delete("/api/watchlist/{symbol}")
    def delete_watchlist_item(symbol: str):
        return remove_watchlist(data_dir, symbol)

    @app.put("/api/watchlist/order")
    def update_watchlist_order(payload: WatchlistOrderInput):
        return reorder_watchlist(data_dir, payload.symbols)

    @app.get("/api/market/sync/status")
    def market_sync_status():
        return sync_runner.status()

    @app.post("/api/market/sync")
    def trigger_market_sync(payload: MarketSyncInput):
        return sync_runner.start(payload.symbols or None, start=payload.start, refresh=payload.refresh)

    @app.get("/api/settings/research-harness")
    def get_harness():
        return harness_settings(data_dir)

    @app.post("/api/settings/research-harness")
    def set_harness(selection: HarnessSelection):
        return harness_settings(data_dir, save=True, selection=selection.name)

    @app.get("/api/market/snapshots")
    def snapshots(symbol: str):
        return list_snapshots(data_dir, symbol)

    @app.get("/api/research/tasks")
    def research_tasks(symbol: str | None = None, kind: str | None = None):
        return list_tasks(data_dir, symbol=symbol, kind=kind)

    @app.post("/api/research/tasks")
    def create_research_task(payload: ResearchTaskInput):
        cutoff = utc_timestamp(payload.as_of)
        symbol = payload.symbol.strip().upper()
        snapshot_id = payload.snapshot_id or _default_snapshot_for_symbol(data_dir, symbol, cutoff)
        manifest = freeze_manifest(
            data_dir, symbol, question=payload.question, snapshot_id=snapshot_id, as_of=cutoff,
            materials=payload.materials, required_titles=payload.required_titles, basis=payload.basis,
        )
        receipt = enqueue_task(data_dir, manifest)
        return _submit(receipt, executor_name=payload.executor, timeout=payload.timeout)

    @app.post("/api/research/tasks/from-followup")
    def create_followup_research_task(payload: FollowupTaskInput):
        manifest, link = build_followup_manifest(
            data_dir, payload.followup_id, snapshot_id=payload.snapshot_id,
            as_of=payload.as_of, materials=payload.materials, basis=payload.basis,
        )
        receipt = enqueue_task(data_dir, manifest, followup_link=link)
        return _submit(receipt, executor_name=payload.executor, timeout=payload.timeout)

    @app.get("/api/research/tasks/{task_id}")
    def read_research_task(task_id: str):
        task = get_task(data_dir, task_id)
        if is_development(task["manifest"]):
            task["development_receipt"] = read_development_receipt(data_dir, task_id)
        return task

    @app.post("/api/research/tasks/{task_id}/retry")
    def retry_research_task(task_id: str, payload: RetryTaskInput):
        receipt = enqueue_retry(data_dir, task_id)
        return _submit(receipt, executor_name=payload.executor, timeout=payload.timeout)

    @app.post("/api/research/tasks/{task_id}/supplement")
    def supplement_research_task(task_id: str, payload: SupplementTaskInput):
        manifest = get_task(data_dir, task_id)["manifest"]
        if is_development(manifest):
            raise ValueError("开发任务使用冻结预设与快照；更换快照请发起新的开发实验")
        cutoff = utc_timestamp(payload.as_of) if payload.as_of is not None else manifest["as_of"]
        combined = collect_materials(payload.materials, cutoff, manifest["materials"])
        snapshot = payload.snapshot_id if payload.snapshot_id is not None else manifest["snapshot_id"]
        new_basis = snapshot != manifest["snapshot_id"] or cutoff != manifest["as_of"]
        if new_basis:
            market = export_market_research(data_dir, manifest["symbol"], snapshot_id=snapshot, as_of=cutoff)
            manifest.update(snapshot_id=snapshot, market=market, purpose=market["snapshot"]["use_mode"])
        if cutoff != manifest["as_of"]:
            manifest["as_of"] = cutoff
            manifest["dossier"] = dossiers.public_version(manifest["symbol"], cutoff)
        if not new_basis and combined == manifest["materials"]:
            raise ValueError("补证须提供新材料、行情快照或截止时点；相同清单请重试原任务")
        manifest["materials"] = combined
        receipt = enqueue_task(data_dir, manifest, parent_task_id=task_id)
        return _submit(receipt, executor_name=payload.executor, timeout=payload.timeout)

    @app.get("/api/research/attempts/{attempt_id}")
    def read_research_attempt(attempt_id: str):
        return get_attempt(data_dir, attempt_id)

    @app.post("/api/research/attempts/{attempt_id}/cancel")
    def cancel_research_attempt(attempt_id: str):
        return cancel_attempt(data_dir, attempt_id)

    @app.get("/api/development/presets")
    def development_presets():
        return [development_preset(PRESET_ID)]

    @app.post("/api/development/tasks")
    def create_development_task(payload: DevelopmentTaskInput):
        preset = development_preset(payload.preset_id)
        snapshot_id = payload.snapshot_id
        if not snapshot_id:
            candidates = [
                item for item in list_snapshots(data_dir, preset["symbol"])
                if item["use_mode"] in ("RECONSTRUCTED_RESEARCH", "STRICT_HISTORICAL_AS_OF")
            ]
            if not candidates:
                raise ValueError("缺少可用于开发实验的历史数据快照")
            snapshot_id = candidates[-1]["snapshot_id"]
        manifest, dev_receipt = prepare_development(data_dir, snapshot_id, preset_id=payload.preset_id)
        receipt = enqueue_task(data_dir, manifest, development_receipt=dev_receipt)
        return _submit(receipt, executor_name=payload.executor, timeout=payload.timeout)

    @app.get("/api/development/tasks/{task_id}")
    def read_development_task(task_id: str):
        task = get_task(data_dir, task_id)
        if not is_development(task["manifest"]):
            raise ValueError(f"任务 {task_id} 不是开发对照实验")
        task["development_receipt"] = read_development_receipt(data_dir, task_id)
        return task

    @app.post("/api/development/tasks/{task_id}/archive")
    def archive_development_task(task_id: str, payload: DevelopmentArchiveInput):
        return archive_development(
            data_dir, task_id, payload.attempt_id, payload.report_version,
            conclusion=payload.conclusion, reviewer=payload.reviewer,
            decision=payload.decision, reason=payload.reason,
            segment_refs=payload.segment_refs, sizing_rule=payload.sizing_rule,
            measurement=payload.measurement,
        )

    @app.get("/api/research/{symbol}/inputs")
    def research_inputs(symbol: str, as_of: str | None = None):
        return dossiers.inputs(symbol, as_of)

    @app.get("/api/research/{symbol}/export")
    def research_export(symbol: str, snapshot_id: str, start: str = DEFAULT_START,
                        end: str | None = None, as_of: str | None = None,
                        benchmark: str = DEFAULT_BENCHMARK, download: bool = False):
        report = export_market_research(
            data_dir, symbol, snapshot_id=snapshot_id, start=start, end=end, as_of=as_of, benchmark=benchmark,
        )
        if download:
            return JSONResponse(report, headers={"Content-Disposition": 'attachment; filename="research-export.json"'})
        return report

    @app.get("/api/research/{symbol}/dossiers")
    def read_dossier(symbol: str, version: str | None = None, as_of: str | None = None):
        return dossiers.version(symbol, version) if version else dossiers.active(symbol, as_of)

    @app.get("/api/research/{symbol}/drafts")
    def read_draft(symbol: str, version: str | None = None):
        return dossiers.draft(symbol, version)

    @app.post("/api/research/{symbol}/drafts")
    def import_draft(symbol: str, draft: DraftInput):
        return dossiers.import_draft(symbol, draft.markdown, version=draft.version)

    @app.post("/api/research/{symbol}/dossiers")
    def publish_dossier(symbol: str, publication: PublicationInput):
        return dossiers.publish(symbol, **publication.model_dump())

    @app.get("/api/research/{symbol}/followups")
    def followups(symbol: str, mode: str = "live", as_of: str | None = None):
        return decisions.research_followups(symbol, mode=mode, as_of=as_of)

    @app.get("/api/experiments")
    def experiments(symbol: str):
        return list_experiments(data_dir, symbol)

    @app.get("/api/experiments/{reference}")
    def experiment(reference: str, trace: bool = False, download: bool = False):
        report = read_experiment(data_dir, reference, trace=trace)
        if download:
            return JSONResponse(report, headers={"Content-Disposition": 'attachment; filename="experiment.json"'})
        return report

    @app.get("/api/strategies/{symbol}")
    def strategies(symbol: str, as_of: str | None = None):
        return registry.for_symbol(symbol, as_of, include_ineligible=True)

    @app.get("/api/account")
    def account(book_id: str = "real", as_of: str | None = None, known_at: str | None = None,
                snapshot_id: str | None = None):
        if snapshot_id is not None:
            return accounts.read_snapshot(snapshot_id).as_dict()
        return accounts.snapshot(book_id, as_of=instant(as_of), known_at=known_at).as_dict()

    @app.get("/api/plans")
    def active_plans(book_id: str = "real", session: str | None = None):
        return plans.active(book_id, session)

    @app.post("/api/plans/preview")
    def preview_plan(inputs: PlanInput):
        return generate_plans(data_dir, **inputs.model_dump(), publish=False)

    @app.get("/api/plans/{plan_id}")
    def read_plan(plan_id: str):
        plan = plans.read(plan_id)
        if plan is None:
            raise HTTPException(404, f"计划版本 {plan_id} 不存在")
        return plan

    @app.get("/api/reviews")
    def reviews(book_id: str = "real", start: str | None = None, end: str | None = None,
                as_of: str | None = None, mode: str | None = None):
        return decisions.registrations(book_id=book_id, start=start, end=end, as_of=as_of, mode=mode)

    @app.post("/api/reviews")
    def register_review(inputs: RegistrationInput):
        return decisions.register(**inputs.model_dump())

    @app.get("/api/reviews/{registration_id}")
    def read_review(registration_id: str, as_of: str | None = None):
        return decisions.read(registration_id, as_of=as_of)

    @app.post("/api/reviews/{registration_id}/settle")
    def settle_review(registration_id: str, clock: ReviewClock):
        return decisions.settle(registration_id, now=clock.now)

    @app.post("/api/reviews/{registration_id}/outcomes")
    def record_outcome(registration_id: str, outcome: OutcomeInput):
        return decisions.record_outcome(registration_id, **outcome.model_dump())

    @app.post("/api/reviews/{registration_id}/findings")
    def record_finding(registration_id: str, finding: FindingInput):
        return decisions.record_finding(registration_id, **finding.model_dump())

    @app.exception_handler(ValueError)
    @app.exception_handler(KeyError)
    @app.exception_handler(FileNotFoundError)
    async def application_error(request: Request, error: Exception):
        return JSONResponse(status_code=400, content={"detail": str(error)})

    app.mount("/assets", StaticFiles(directory=ASSETS), name="workbench")
    return app
