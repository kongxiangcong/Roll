"""Loopback HTTP interface for the single-process desktop workbench."""

from datetime import date, datetime, time, timedelta
import json
from pathlib import Path
from typing import Literal

from fastapi import Body, FastAPI, HTTPException, Response
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel

from roll.accounts.csv_import import CsvImports, template
from roll.accounts.ledger import ConfirmCommand, DraftCommand, Ledger
from roll.backtest import run_backtest
from roll.barometer import barometer_at
from roll.calibration import forward_statistics, historical_calibration
from roll.market.calendar import is_session
from roll.market.daily import SHANGHAI, market_status
from roll.market.inputs import input_status
from roll.market.sync import sync_workbench
from roll.reports import freeze_report, read_report, report_markdown
from roll.risk import risk_at


class SyncRequest(BaseModel):
    scope: Literal["all", "daily", "inputs", "financials"] = "all"
    start: date | None = None
    end: date | None = None


def last_session():
    now = datetime.now(SHANGHAI)
    day = now.date() if now.time() >= time(15) else now.date() - timedelta(days=1)
    while not is_session(day):
        day -= timedelta(days=1)
    return day.isoformat()


def create_app(data_dir: Path):
    app = FastAPI(title="Roll 盘后工作台")
    app.add_middleware(
        TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "testserver"]
    )
    dist = Path(__file__).resolve().parents[3] / "frontend" / "dist"

    @app.middleware("http")
    async def check_origin(request, call_next):
        origin = request.headers.get("origin")
        if request.method == "POST" and origin and origin != str(request.base_url).rstrip("/"):
            return JSONResponse({"detail": "只接受来自本机工作台的写入"}, status_code=403)
        return await call_next(request)

    @app.exception_handler(ValueError)
    async def invalid(_, error):
        return JSONResponse({"detail": str(error)}, status_code=422)

    @app.get("/api/session")
    def session():
        return {"trade_date": last_session()}

    @app.get("/api/market")
    def market(day: date):
        selected = day.isoformat()
        return {
            "barometer": barometer_at(data_dir, selected),
            "market": market_status(data_dir, selected),
            "inputs": input_status(data_dir, end=selected),
            "calibration": historical_calibration(data_dir, selected, selected)[
                "current"
            ],
        }

    @app.post("/api/sync")
    def synchronize(command: SyncRequest):
        return sync_workbench(
            data_dir,
            str(command.start) if command.start else None,
            str(command.end) if command.end else None,
            scope=command.scope,
        )

    @app.get("/api/account")
    def account():
        return Ledger(data_dir).account()

    @app.post("/api/account/drafts")
    def draft(command: DraftCommand):
        return Ledger(data_dir).draft(command)

    @app.post("/api/account/confirm")
    def confirm(command: ConfirmCommand):
        return Ledger(data_dir).confirm(command)

    @app.get("/api/account/template")
    def csv_template():
        return Response(
            template(),
            media_type="text/csv",
            headers={"Content-Disposition": 'attachment; filename="roll-trades.csv"'},
        )

    @app.post("/api/account/import")
    def import_trades(
        filename: str,
        version: int,
        encoding: Literal["utf-8-sig", "utf-8", "gb18030"] = "utf-8-sig",
        content: bytes = Body(media_type="application/octet-stream"),
    ):
        if len(content) > 4 * 1024 * 1024:
            raise HTTPException(413, "CSV 超过 4 MiB")
        return CsvImports(Ledger(data_dir)).upload(
            content, Path(filename).name, encoding, version
        )

    @app.get("/api/account/receipts/{receipt_id}")
    def reconcile(receipt_id: str):
        return Ledger(data_dir).account_for_receipt(receipt_id)

    @app.get("/api/risk")
    def risk(day: date):
        return risk_at(data_dir, day.isoformat())

    @app.get("/api/backtest")
    def backtest(start: date, end: date):
        return run_backtest(data_dir, start.isoformat(), end.isoformat())

    @app.get("/api/calibration")
    def calibration(start: date, end: date):
        history = historical_calibration(data_dir, start.isoformat(), end.isoformat())
        return {
            "current": history["current"],
            "by_regime": history["by_regime"],
            "forward": forward_statistics(data_dir, start.isoformat(), end.isoformat()),
        }

    @app.post("/api/reports/{day}")
    def freeze(day: date):
        return freeze_report(data_dir, day.isoformat())

    @app.get("/api/reports/{day}/export")
    def export(day: date, format: Literal["json", "markdown"] = "json"):
        try:
            frozen = read_report(data_dir, day.isoformat())
        except ValueError as exc:
            raise HTTPException(404, str(exc)) from exc
        markdown = format == "markdown"
        content = (
            report_markdown(frozen)
            if markdown
            else json.dumps(frozen, ensure_ascii=False, indent=2)
        )
        filename = f"roll-{day}.{'md' if markdown else 'json'}"
        return Response(
            content,
            media_type="text/markdown" if markdown else "application/json",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    app.mount(
        "/assets",
        StaticFiles(directory=dist / "assets", check_dir=False),
        name="assets",
    )

    @app.get("/")
    @app.get("/holdings")
    @app.get("/validation")
    def page():
        index = dist / "index.html"
        if not index.is_file() or 'name="roll-workbench"' not in index.read_text(
            encoding="utf-8"
        ):
            raise HTTPException(
                503,
                "请在 frontend 运行 npm ci 和 npm run build，或使用 scripts/start.ps1 启动",
            )
        return FileResponse(dist / "index.html")

    return app


def serve(data_dir, port):
    import uvicorn

    uvicorn.run(create_app(data_dir), host="127.0.0.1", port=port)
