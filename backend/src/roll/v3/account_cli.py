"""CLI commands for recording and reading local account facts."""
import json
import sys
from datetime import datetime, timezone
from decimal import Decimal

from roll.v3.account import AccountLedger, PositionLot


def register_account_commands(commands):
    account = commands.add_parser("account", help="录入并查询本地账户")
    operations = account.add_subparsers(required=True)

    writes = (
        ("init", _initialize, "建立现金及持仓基线，字段 cash、available_cash、lots、effective_at"),
        ("fill", _record_event, "录入券商成交，字段 event_id、symbol、side、quantity、price、fee、effective_at"),
        ("correct", _record_event, "更正成交，字段 event_id、target_event_id、replacement、known_at"),
        ("cash", _record_event, "登记资金变动，字段 event_id、delta、effective_at"),
        ("shares", _record_shares, "登记到账股份，字段 event_id、lot、effective_at"),
        ("budget", _set_budget, "登记风险预算版本，字段 budget_id、effective_at、cash_reserve、max_total_exposure、"
         "max_symbol_exposure、max_industry_exposure"),
    )
    for operation, handler, description in writes:
        parser = operations.add_parser(
            operation, help=description.split("，字段")[0], description=f"从标准输入读取 JSON。{description}。",
        )
        parser.add_argument("--book-id", default="real")
        parser.set_defaults(handler=handler, account_operation=operation)

    show = operations.add_parser("show", help="按决策时点或冻结标识读取账户")
    show.add_argument("--book-id", default="real")
    cutoff = show.add_mutually_exclusive_group()
    cutoff.add_argument("--as-of", help="生效截止时点（带时区）")
    cutoff.add_argument("--snapshot-id")
    show.add_argument("--known-at", help="获知截止时点（默认同生效截止）")
    show.set_defaults(handler=_show)

    log = operations.add_parser("log", help="读取按发生和获知截止时点可见的账户流水")
    log.add_argument("--book-id", default="real")
    log.add_argument("--as-of", help="生效截止时点（带时区）")
    log.add_argument("--known-at", help="获知截止时点（默认同生效截止）")
    log.add_argument("--plan-id")
    log.set_defaults(handler=_log)


def _payload():
    return json.load(sys.stdin, parse_float=Decimal)


def _initialize(args, data_dir):
    payload = _payload()
    payload["lots"] = [PositionLot(**lot) for lot in payload.get("lots", ())]
    event_id = AccountLedger(data_dir).initialize(args.book_id, **payload)
    return {"book_id": args.book_id, "event_id": event_id}


def _record_event(args, data_dir):
    ledger = AccountLedger(data_dir)
    record = {"fill": ledger.record_fill, "correct": ledger.correct, "cash": ledger.record_cash}
    return {"book_id": args.book_id, "event_id": record[args.account_operation](args.book_id, **_payload())}


def _record_shares(args, data_dir):
    payload = _payload()
    payload["lot"] = PositionLot(**payload["lot"])
    event_id = AccountLedger(data_dir).record_shares(args.book_id, **payload)
    return {"book_id": args.book_id, "event_id": event_id}


def _set_budget(args, data_dir):
    budget_id = AccountLedger(data_dir).set_risk_budget(args.book_id, **_payload())
    return {"book_id": args.book_id, "budget_id": budget_id}


def _show(args, data_dir):
    ledger = AccountLedger(data_dir)
    if args.snapshot_id is not None:
        return ledger.read_snapshot(args.snapshot_id).as_dict()
    return ledger.snapshot(
        args.book_id, as_of=args.as_of or datetime.now(timezone.utc), known_at=args.known_at
    ).as_dict()


def _log(args, data_dir):
    return AccountLedger(data_dir).trade_log(
        args.book_id, as_of=args.as_of or datetime.now(timezone.utc), known_at=args.known_at, plan_id=args.plan_id
    )
