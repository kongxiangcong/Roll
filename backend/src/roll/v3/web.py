"""Local HTTP and browser adapters for the Roll v3 application."""
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from roll.v3.account import AccountLedger
from roll.v3.experiment import list_experiments, read_experiment
from roll.v3.market import list_snapshots
from roll.v3.market_research import DEFAULT_BENCHMARK, DEFAULT_START, export_market_research
from roll.v3.plan import PlanLedger, generate_plans
from roll.v3.research import ResearchDossiers
from roll.v3.review import DecisionLedger
from roll.v3.storage import instant
from roll.v3.strategy import StrategyRegistry


ASSETS = Path(__file__).with_name("workbench")


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
    fill: dict | None = None


class FindingInput(ReviewClock):
    symbol: str
    category: str
    reason: str
    evidence_refs: list[str] = Field(default_factory=list)
    trigger_id: str | None = None


def create_app(data_dir):
    app = FastAPI(title="Roll 盘后工作台", docs_url=None, redoc_url=None, openapi_url=None)
    dossiers = ResearchDossiers(data_dir)
    decisions = DecisionLedger(data_dir)
    plans = PlanLedger(data_dir)
    accounts = AccountLedger(data_dir)
    registry = StrategyRegistry(data_dir)

    @app.get("/")
    def index():
        return FileResponse(ASSETS / "index.html")

    @app.get("/api/market/snapshots")
    def snapshots(symbol: str):
        return list_snapshots(data_dir, symbol)

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
