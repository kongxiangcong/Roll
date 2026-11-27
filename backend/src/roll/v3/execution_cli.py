"""Read frozen opening and account snapshots for a local simulated settlement."""
import json
import sys
from dataclasses import asdict
from decimal import Decimal

from roll.v3.account import AccountLedger
from roll.v3.execution import (
    EXECUTION_RULES_VERSION, ExecutionIntent, ExecutionRules, execute, execution_session, read_opening_quote,
)


def register_execution_commands(commands):
    execution = commands.add_parser("execution", help="次一交易日开盘模拟成交")
    operations = execution.add_subparsers(required=True)
    simulate = operations.add_parser(
        "simulate", help="基于冻结数据模拟成交并返回账户投影",
        description="从标准输入读取 JSON 意图。字段 intent_id、symbol、side（BUY 或 SELL）、"
                    "quantity、decision_at，可选 limit_price、cash_limit。",
    )
    simulate.add_argument("--market-snapshot", required=True, help="包含次日 daily_open 的数据快照")
    simulate.add_argument("--account-snapshot", required=True, help="开盘时可用的账户快照")
    simulate.add_argument("--commission-rate", type=Decimal, default=Decimal("0.0003"))
    simulate.add_argument("--minimum-commission", type=Decimal, default=Decimal("5"))
    simulate.add_argument("--slippage-rate", type=Decimal, default=Decimal("0.0005"))
    simulate.add_argument("--lot-size", type=int, default=1, help="券商另设的申报数量单位")
    simulate.set_defaults(handler=_simulate)


def _simulate(args, data_dir):
    intent = ExecutionIntent(**json.load(sys.stdin, parse_float=Decimal))
    account = AccountLedger(data_dir).read_snapshot(args.account_snapshot)
    opening = read_opening_quote(data_dir, args.market_snapshot, intent.symbol, execution_session(intent))
    rules = ExecutionRules(args.commission_rate, args.minimum_commission, args.slippage_rate, args.lot_size)
    return {
        "market_snapshot_id": args.market_snapshot, "account_snapshot_id": args.account_snapshot,
        "execution_rules_version": EXECUTION_RULES_VERSION, "rules": asdict(rules),
        **execute(intent, opening, account, rules).as_dict(),
    }
