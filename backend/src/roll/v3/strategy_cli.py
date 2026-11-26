"""Local commands for freezing and inspecting candidate strategies."""

from roll.v3.strategy import StrategyRegistry, replay_signals


def _freeze(args, data_dir):
    return StrategyRegistry(data_dir).freeze_default(
        fast=args.fast, slow=args.slow, frozen_at=args.at,
        acceptance_start=args.acceptance_start, acceptance_end=args.acceptance_end,
    )


def _show(args, data_dir):
    return StrategyRegistry(data_dir).get(args.version, args.as_of)


def _registry(args, data_dir):
    return StrategyRegistry(data_dir).for_symbol(
        args.symbol, args.as_of, simulated=args.simulated, versions=args.version,
    )


def _replay(args, data_dir):
    sessions = replay_signals(
        data_dir, args.version, args.snapshot_id, symbol=args.symbol, start=args.start, end=args.end,
    )
    exposure = StrategyRegistry(data_dir).record_replay(
        args.version, args.snapshot_id, start=args.start, end=args.end,
    )
    return {
        "strategy_version": args.version,
        "data_snapshot_id": args.snapshot_id,
        "exposure": exposure,
        "sessions": sessions,
    }


def _open_acceptance(args, data_dir):
    return StrategyRegistry(data_dir).begin_acceptance(
        args.version, args.snapshot_id, run_id=args.run_id, evaluated_at=args.at,
    )


def _admit(args, data_dir):
    return StrategyRegistry(data_dir).admit(args.version, effective_at=args.at)


def _change_availability(args, data_dir):
    return StrategyRegistry(data_dir).change_availability(
        args.version, args.status, reason=args.reason, effective_at=args.at,
    )


def register(subparsers):
    strategy = subparsers.add_parser("strategy", help="策略登记、准入和信号回放")
    actions = strategy.add_subparsers(required=True)

    freeze = actions.add_parser("freeze", help="冻结趋势实验协议及策略规格")
    freeze.add_argument("--fast", type=int, default=20)
    freeze.add_argument("--slow", type=int, default=60)
    freeze.add_argument("--at")
    freeze.add_argument("--acceptance-start")
    freeze.add_argument("--acceptance-end")
    freeze.set_defaults(handler=_freeze)

    show = actions.add_parser("show", help="按版本和时点查看协议及状态")
    show.add_argument("version")
    show.add_argument("--as-of")
    show.set_defaults(handler=_show)

    registry = actions.add_parser("registry", help="查看指定标的在该时点可运行的策略版本")
    registry.add_argument("symbol")
    registry.add_argument("--as-of")
    registry.add_argument("--simulated", action="store_true")
    registry.add_argument("--version", action="append", default=[])
    registry.set_defaults(handler=_registry)

    replay = actions.add_parser("replay", help="按交易日读取冻结行情并计算趋势信号")
    replay.add_argument("version")
    replay.add_argument("snapshot_id")
    replay.add_argument("--symbol", default="600362.SH")
    replay.add_argument("--start", required=True)
    replay.add_argument("--end", required=True)
    replay.set_defaults(handler=_replay)


    acceptance = actions.add_parser("open-acceptance", help="冻结验收运行并登记窗口揭示")
    acceptance.add_argument("version")
    acceptance.add_argument("snapshot_id")
    acceptance.add_argument("run_id")
    acceptance.add_argument("--at")
    acceptance.set_defaults(handler=_open_acceptance)

    admit = actions.add_parser("admit", help="发布通过独立验收及前向观察的策略")
    admit.add_argument("version")
    admit.add_argument("--at")
    admit.set_defaults(handler=_admit)

    availability = actions.add_parser("availability", help="暂停或退役已准入的策略")
    availability.add_argument("version")
    availability.add_argument("status", choices=("suspended", "retired"))
    availability.add_argument("--reason", required=True)
    availability.add_argument("--at")
    availability.set_defaults(handler=_change_availability)
