"""On-demand command line for the single-process Roll workbench."""
import argparse
import json
from pathlib import Path
import sys

from fastapi import HTTPException
from roll.accounts.csv_import import CsvImports
from roll.accounts.ledger import ConfirmCommand, DraftCommand, Ledger
from roll.barometer import barometer_at
from roll.calibration import historical_calibration, forward_statistics
from roll.config import active_watchlist, data_directory
from roll.market.daily import read_bars, read_indicators
from roll.market.financials import financial_light
from roll.risk import risk_at
from roll.reports import freeze_report, read_report, report_markdown


def account_command(args):
    ledger = Ledger(args.data_dir)
    if args.operation == "import-csv":
        with args.file.open("rb") as stream:
            raw = stream.read(4 * 1024 * 1024 + 1)
        return CsvImports(ledger).upload(raw, args.file.name, args.encoding, ledger.account()["version"])
    if args.operation == "reconcile":
        return ledger.account_for_receipt(args.receipt_id)
    if args.operation == "draft":
        return ledger.draft(DraftCommand.model_validate_json(sys.stdin.read()))
    if args.operation == "confirm":
        command = ConfirmCommand(draft_id=args.draft_id, idempotency_key=args.key)
        return ledger.confirm(command)
    return ledger.account()


def sync_command(args):
    from roll.market.sync import sync_workbench
    return sync_workbench(
        args.data_dir, args.start, args.end, scope=args.sync_scope,
        watchlist=args.watchlist, groups=args.group,
    )


def main(argv=None):
    from roll.market.inputs import SYNC_GROUPS, UNITS, input_status, read_inputs
    parser = argparse.ArgumentParser(prog="roll")
    parser.add_argument("--data-dir", type=Path, default=data_directory() / "v2")
    commands = parser.add_subparsers(dest="command", required=True)
    account = commands.add_parser("account", help="核对本地账本")
    account.set_defaults(run=account_command)
    operations = account.add_subparsers(dest="operation", required=True)
    upload = operations.add_parser("import-csv", help="读取 Roll 成交 CSV，预览后用 confirm 确认")
    upload.add_argument("file", type=Path)
    upload.add_argument("--encoding", choices=["utf-8-sig", "utf-8", "gb18030"], default="utf-8-sig")
    reconcile = operations.add_parser("reconcile", help="按回执核对当时的现金、成交和逐证券持仓")
    reconcile.add_argument("receipt_id")
    operations.add_parser("show", help="显示最近确认的余额和持仓")
    operations.add_parser("draft", help="从标准输入读取 JSON 记账草稿")
    confirm = operations.add_parser("confirm", help="确认草稿并取得回执")
    confirm.add_argument("draft_id")
    confirm.add_argument("key", help="该次确认的幂等键，重试时使用同一个键")
    sync = commands.add_parser("sync", help="同步盘后行情")
    sync.add_argument("--start")
    sync.add_argument("--end")
    subset = sync.add_mutually_exclusive_group()
    subset.add_argument("--market-inputs", dest="sync_scope", action="store_const", const="inputs", help="仅同步 AKShare 市场输入")
    subset.add_argument("--financials-only", dest="sync_scope", action="store_const", const="financials", help="仅同步跟踪池财报")
    subset.add_argument("--daily-only", dest="sync_scope", action="store_const", const="daily", help="仅同步股票及指数日线")
    sync.add_argument("--group", choices=SYNC_GROUPS, action="append", help="指定 AKShare 输入，可重复")
    sync.set_defaults(run=sync_command, sync_scope="all")
    inputs = commands.add_parser("inputs", help="离线查看 AKShare 历史、单位与缺项")
    inputs.add_argument("series", choices=UNITS, nargs="?")
    inputs.add_argument("symbol", nargs="?", default="CN")
    inputs.add_argument("--start")
    inputs.add_argument("--end")
    inputs.set_defaults(run=lambda a: {"units": UNITS[a.series], "rows": read_inputs(
        a.data_dir, a.series, a.symbol, a.start, a.end)} if a.series else input_status(a.data_dir, a.start, a.end))
    sync.add_argument("--watchlist", type=Path, help="跟踪池 YAML 路径")
    financial = commands.add_parser("financials", help="按披露日回放个股财报灯")
    financial.add_argument("symbol")
    financial.add_argument("--as-of", required=True, metavar="YYYY-MM-DD")
    financial.set_defaults(run=lambda a: financial_light(a.data_dir, a.symbol, a.as_of))
    risk = commands.add_parser("risk", help="按交易日查看持仓与个股风险")
    risk.add_argument("trade_date")
    risk.set_defaults(run=lambda a: risk_at(a.data_dir, a.trade_date))
    watch = commands.add_parser("watchlist", help="读取上次同步生效的跟踪池")
    watch.set_defaults(run=lambda a: active_watchlist(a.data_dir))
    prices = commands.add_parser("prices", help="离线读取行情")
    prices.add_argument("symbol")
    prices.add_argument("--start")
    prices.add_argument("--end")
    prices.add_argument("--adjustment", choices=["raw", "forward", "backward"], default="raw")
    prices.add_argument("--indicators", action="store_true", help="附带同锚点的 MA20、MA60 和 ATR14")
    prices.set_defaults(run=lambda a: (read_indicators if a.indicators else read_bars)(
        a.data_dir, a.symbol, a.start, a.end, a.adjustment))
    report = commands.add_parser("report", help="冻结或重读盘后日报")
    report.add_argument("operation", choices=["freeze", "read"])
    report.add_argument("trade_date", metavar="YYYY-MM-DD")
    report.add_argument("--format", choices=["json", "markdown"], default="json")
    report.set_defaults(run=lambda a: (freeze_report if a.operation == "freeze" else read_report)(
        a.data_dir, a.trade_date))
    gauge = commands.add_parser("barometer", help="读取指定交易日的实时工作台晴雨表")
    gauge.add_argument("trade_date", metavar="YYYY-MM-DD")
    gauge.set_defaults(run=lambda a: barometer_at(a.data_dir, a.trade_date))
    from roll.backtest import run_backtest
    backtest = commands.add_parser("backtest", help="比较晴雨表控仓与 510300.SH 买入持有")
    backtest.add_argument("--start", default="2020-01-01")
    backtest.add_argument("--end", help="默认取最近可得的完整 ETF 交易日")
    backtest.set_defaults(run=lambda a: run_backtest(a.data_dir, a.start, a.end))
    calibration = commands.add_parser("calibration", help="查看所选期间四档历史预测及 Brier")
    calibration.add_argument("--start", required=True)
    calibration.add_argument("--end", required=True)
    calibration.set_defaults(run=lambda a: historical_calibration(a.data_dir, a.start, a.end))
    forward = commands.add_parser("forward", help="查看所选期间实际冻结的前向预测与成熟成绩")
    forward.add_argument("--start", required=True)
    forward.add_argument("--end", required=True)
    forward.set_defaults(run=lambda a: forward_statistics(a.data_dir, a.start, a.end))
    server = commands.add_parser("serve",help="启动本机网页工作台")
    server.add_argument("--port",type=int,default=8010)
    args = parser.parse_args(argv)
    if args.command == "serve":
        from roll.web import serve
        return serve(args.data_dir,args.port)
    try:
        result = args.run(args)
    except HTTPException as error:
        parser.exit(1, json.dumps(error.detail, ensure_ascii=False) + "\n")
    except (ValueError, OSError) as error:
        parser.exit(1, str(error) + "\n")
    if args.command == "report" and args.format == "markdown":
        print(report_markdown(result))
    else:
        print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
