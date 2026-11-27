"""CLI adapters for the M0b forward window."""
from roll.v3 import forward_window


def register_forward_window_commands(commands):
    forward = commands.add_parser("forward-window", help="核查连续真实交易日并签收 M0b")
    actions = forward.add_subparsers(required=True)
    audit = actions.add_parser("audit", help="按交易所日历核查登记和到期结果")
    signoff = actions.add_parser("signoff", help="冻结符合要求的 20 日签收证据")
    for command in (audit, signoff):
        command.add_argument("--book-id", default="real")
        command.add_argument("--start", help="核查范围的开始日期")
        command.add_argument("--end", help="核查范围的结束日期，默认核查至最近已收盘日")
    audit.set_defaults(handler=_audit)
    signoff.set_defaults(handler=_signoff)
    show = actions.add_parser("show", help="读取原始签收证据")
    show.add_argument("signoff_id")
    show.set_defaults(handler=_show)


def _audit(args, data_dir):
    return forward_window.audit(data_dir, book_id=args.book_id, start=args.start, end=args.end)


def _signoff(args, data_dir):
    return forward_window.signoff(data_dir, book_id=args.book_id, start=args.start, end=args.end)


def _show(args, data_dir):
    return forward_window.show(data_dir, args.signoff_id)
