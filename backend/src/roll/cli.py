"""On-demand command line for the single-process Roll workbench."""
import argparse
import json
from pathlib import Path
import sys

from fastapi import HTTPException
from roll.accounts.csv_import import CsvImports
from roll.accounts.ledger import ConfirmCommand, DraftCommand, Ledger
from roll.config import data_directory
from roll.reports import freeze_report, read_report, report_markdown
from roll.market.daily import sync_market, read_bars


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


def main(argv=None):
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
    sync.set_defaults(run=lambda a: sync_market(a.data_dir, a.start, a.end))
    prices = commands.add_parser("prices", help="离线读取行情")
    prices.add_argument("symbol")
    prices.add_argument("--start")
    prices.add_argument("--end")
    prices.add_argument("--adjustment", choices=["raw", "forward", "backward"], default="raw")
    prices.set_defaults(run=lambda a: read_bars(a.data_dir, a.symbol, a.start, a.end, a.adjustment))
    report = commands.add_parser("report", help="冻结或重读盘后日报")
    report.add_argument("operation", choices=["freeze", "read"])
    report.add_argument("trade_date", metavar="YYYY-MM-DD")
    report.add_argument("--format", choices=["json", "markdown"], default="json")
    report.set_defaults(run=lambda a: (freeze_report if a.operation == "freeze" else read_report)(
        a.data_dir, a.trade_date))
    args = parser.parse_args(argv)
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
