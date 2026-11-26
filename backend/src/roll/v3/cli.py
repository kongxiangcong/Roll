"""Local Roll workbench. Command handlers are shared with the application."""
import argparse
import json
import sys
from pathlib import Path

from roll.config import data_directory, load_runtime_environment


def parser():
    from roll.v3.account_cli import register_account_commands
    from roll.v3.entitlements import register_entitlement_commands
    from roll.v3.market_cli import register as register_market
    from roll.v3.market_research import register_market_research
    from roll.v3.research import register_research_commands
    from roll.v3.strategy_cli import register as register_strategy

    root = argparse.ArgumentParser(prog="roll", description="Roll v3 个股研究与盘后工作台")
    root.add_argument("--data-dir", type=Path, help="本地 v3 数据目录")
    commands = root.add_subparsers(dest="command", required=True)
    register_market(commands)
    register_account_commands(commands)
    register_entitlement_commands(commands)
    register_market_research(register_research_commands(commands))
    register_strategy(commands)
    serve = commands.add_parser("serve", help="打开本地工作台")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8765)
    serve.set_defaults(handler=_serve)
    return root


def run(argv=None, *, data_dir=None):
    args = parser().parse_args(argv)
    return args.handler(args, args.data_dir or data_dir or data_directory())


def main(argv=None):
    load_runtime_environment()
    try:
        result = run(argv)
    except (FileNotFoundError, KeyError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 2
    if result is not None:
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0


def _serve(args, data_dir):
    import uvicorn

    from roll.v3.web import create_app

    uvicorn.run(create_app(data_dir), host=args.host, port=args.port)


if __name__ == "__main__":
    raise SystemExit(main())
