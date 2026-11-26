"""CLI adapters for the decision ledger."""
from argparse import BooleanOptionalAction
from decimal import Decimal
import json
import sys

from roll.market.calendar import LAST_NOTICE_DAY
from roll.v3.review import DecisionLedger, FINDING_CATEGORIES, MODES, OUTCOMES
from roll.v3.storage import instant, sessions


def register_review_commands(commands):
    review = commands.add_parser("review", help="登记盘后计划、结算连续影子并对照真实执行")
    actions = review.add_subparsers(required=True)

    register = actions.add_parser("register", help="冻结真实计划与独立影子计划并登记")
    register.add_argument("--book-id", default="real")
    register.add_argument("--as-of", help="交易日盘后裁决截止时点")
    register.add_argument("--symbol", action="append")
    register.add_argument("--strategy-version", action="append")
    register.add_argument("--price-only", action=BooleanOptionalAction, help="影子策略使用已冻结的独立量价口径")
    register.add_argument("--snapshot-id", help="使用已有行情快照，重建模式下用于影子计划")
    register.add_argument("--mode", choices=MODES, default="live")
    register.add_argument("--now", help="指定演练或重建的时钟")
    register.set_defaults(handler=_register)

    settle = actions.add_parser("settle", help="结算已到下一交易时段的影子计划")
    settle.add_argument("registration_id")
    settle.add_argument("--now", help="指定演练或重建的时钟")
    settle.set_defaults(handler=_settle)

    show = actions.add_parser("show", help="并列阅读原计划、影子及实际执行")
    show.add_argument("registration_id")
    show.add_argument("--as-of", help="只显示该时点已登记的事实")
    show.set_defaults(handler=_show)

    timeline = actions.add_parser("list", help="查询登记与缺少真实前向记录的交易日")
    timeline.add_argument("--book-id", default="real")
    timeline.add_argument("--start")
    timeline.add_argument("--end")
    timeline.add_argument("--as-of")
    timeline.set_defaults(handler=_list)

    outcome = actions.add_parser(
        "outcome", help="记录用户确认、拒绝、未执行或已确认的券商成交",
        description="成交请从标准输入提供 JSON，字段包含 event_id、effective_at、side、quantity、price 及实际费用 fee。"
                    "其他状态可提供 reason。可使用 reported_at 保留券商回报时间。",
    )
    outcome.add_argument("registration_id")
    outcome.add_argument("symbol")
    outcome.add_argument("status", choices=OUTCOMES)
    outcome.add_argument("--reason")
    outcome.add_argument("--plan-id", help="关联特定的已发布真实计划版本")
    outcome.add_argument("--reported-at")
    outcome.add_argument("--now", help="指定演练时钟")
    outcome.set_defaults(handler=_outcome)

    finding = actions.add_parser("finding", help="记录归因或依据原证伪条件提出重新研究")
    finding.add_argument("registration_id")
    finding.add_argument("symbol")
    finding.add_argument("category", choices=FINDING_CATEGORIES)
    finding.add_argument("--reason", required=True)
    finding.add_argument("--evidence", action="append", default=[])
    finding.add_argument("--trigger-id", help="原冻结计划引用的证伪条件标识")
    finding.add_argument("--now", help="指定演练或重建时钟")
    finding.set_defaults(handler=_finding)


def _register(args, data_dir):
    return DecisionLedger(data_dir).register(
        book_id=args.book_id, as_of=args.as_of, symbols=args.symbol or (), strategy_versions=args.strategy_version or (),
        price_only=args.price_only, snapshot_id=args.snapshot_id, mode=args.mode, now=args.now,
    )


def _settle(args, data_dir):
    return DecisionLedger(data_dir).settle(args.registration_id, now=args.now)


def _show(args, data_dir):
    return DecisionLedger(data_dir).read(args.registration_id, as_of=args.as_of)


def _list(args, data_dir):
    if (args.start is None) != (args.end is None):
        raise ValueError("核对交易日缺口须同时提供开始和结束日期")
    clock = instant(args.as_of)
    records = DecisionLedger(data_dir).registrations(
        book_id=args.book_id, start=args.start, end=args.end, as_of=clock,
    )
    live = {record["decision_date"] for record in records if record["mode"] == "live"}
    today = clock.date().isoformat()
    requested_end = min(args.end, today) if args.end else today
    calendar_end = LAST_NOTICE_DAY.isoformat()
    gaps = [
        day for day in sessions(args.start, min(requested_end, calendar_end))
        if day not in live and (day < today or clock.hour >= 15)
    ] if args.start else []
    return {
        "registrations": records, "missing_live_dates": gaps,
        "calendar_known_through": calendar_end,
        "calendar_coverage_complete": requested_end <= calendar_end if args.end else None,
    }


def _outcome(args, data_dir):
    payload = json.load(sys.stdin, parse_float=Decimal) if args.status == "filled" else {}
    return DecisionLedger(data_dir).record_outcome(
        args.registration_id, args.symbol, args.status, reason=args.reason or payload.pop("reason", None),
        reported_at=args.reported_at or payload.pop("reported_at", None),
        fill=payload if args.status == "filled" else None, plan_id=args.plan_id, now=args.now,
    )


def _finding(args, data_dir):
    return DecisionLedger(data_dir).record_finding(
        args.registration_id, args.symbol, category=args.category, reason=args.reason,
        evidence_refs=args.evidence, trigger_id=args.trigger_id, now=args.now,
    )
