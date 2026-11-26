"""After-close plan generation and immutable plan lookup."""
from roll.v3.plan import PlanLedger, generate_plans


def register_plan_commands(commands):
    plan = commands.add_parser("plan", help="冻结盘后输入、生成下一交易日计划或查询历史版本")
    plan.add_argument("--book-id", default="real")
    plan.add_argument("--symbol", action="append", help="指定候选标的，可重复使用，默认 600362.SH 和持仓")
    plan.add_argument("--as-of", help="裁决截止时点，例如 2026-11-26T16:00:00+08:00")
    plan.add_argument("--snapshot-id", help="复用指定的冻结行情快照")
    plan.add_argument("--simulate", action="store_true", help="使用独立模拟账本")
    plan.add_argument("--strategy-version", action="append", help="指定策略版本，可重复使用")
    plan.add_argument("--price-only", action="store_true", help="用指定冻结策略在模拟账本运行独立量价口径")
    plan.add_argument("--preview", action="store_true", help="预览裁决，不发布计划")
    lookup = plan.add_mutually_exclusive_group()
    lookup.add_argument("--plan-id", help="读取任意已发布版本")
    lookup.add_argument("--session", help="读取指定交易日的当前计划")
    plan.set_defaults(handler=_plan)


def _plan(args, data_dir):
    if args.plan_id:
        plan = PlanLedger(data_dir).read(args.plan_id)
        if plan is None:
            raise ValueError(f"计划版本 {args.plan_id} 不存在")
        return plan
    if args.session:
        return PlanLedger(data_dir).active(args.book_id, args.session)
    return generate_plans(
        data_dir, book_id=args.book_id, as_of=args.as_of, symbols=args.symbol,
        snapshot_id=args.snapshot_id, simulated=args.simulate, strategy_versions=args.strategy_version or (),
        publish=not args.preview, allow_price_only=args.price_only,
    )
