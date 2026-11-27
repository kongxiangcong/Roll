"""CLI for viewing trading plan commitments and available cash."""
from decimal import Decimal
import json
import sys

from roll.v3.plan import PlanLedger


def register_commitment_commands(commands):
    commitments = commands.add_parser("commitments", help="查询计划资金预留与可分配金额")
    operations = commitments.add_subparsers(required=True)
    show = operations.add_parser("show", help="按生效和获知截止时点核对剩余承诺")
    show.add_argument("--book-id", default="real")
    show.add_argument("--as-of", help="生效截止时点（带时区）")
    show.add_argument("--known-at", help="获知截止时点（默认同生效截止）")
    show.add_argument("--plan-id", help="指定计划的余额明细，包括已释放的预留")
    show.set_defaults(handler=_show)

    for name, help_text, description in (
        ("condition", "登记或撤销跨日条件",
         "输入 plan_id、event_id、status (active/revoked)、effective_at，生效时填写 expires_at。"
         "可填写 known_at 和 description。"),
        ("order", "登记券商委托或结果",
         "输入 plan_id、order_id、event_id、status (pending/cancelled/expired/filled)、effective_at。"
         "max_amount（含费上限）与 order_quantity 默认沿用计划。可填写 known_at、券商可用现金中"
         "已扣除的同笔冻结款 broker_frozen，以及券商确认的余额 broker_available_cash。"
         "成交通过 account fill 登记，使用 broker_order_id 关联委托，并用 broker_available_after"
         "记录券商当时的可用余额。"),
    ):
        operation = operations.add_parser(name, help=help_text, description=f"从标准输入读取 JSON。{description}")
        operation.add_argument("--book-id", default="real")
        operation.set_defaults(handler=_record, commitment_operation=name)


def _show(args, data_dir):
    return PlanLedger(data_dir).commitment_summary(args.book_id, as_of=args.as_of, known_at=args.known_at,
                                                   plan_id=args.plan_id)


def _record(args, data_dir):
    ledger = PlanLedger(data_dir)
    record = {"condition": ledger.record_condition, "order": ledger.record_order}
    event_id = record[args.commitment_operation](args.book_id, **json.load(sys.stdin, parse_float=Decimal))
    return {"book_id": args.book_id, "event_id": event_id}
