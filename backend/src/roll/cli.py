"""On-demand command line for the single-process Roll workbench."""
import argparse
import json
from pathlib import Path
import sys

from fastapi import HTTPException
from pydantic import ValidationError
from roll.accounts.ledger import ConfirmCommand, DraftCommand, Ledger
from roll.config import data_directory


def account_command(args):
    ledger = Ledger(args.data_dir)
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
    operations.add_parser("show", help="显示最近确认的余额和持仓")
    operations.add_parser("draft", help="从标准输入读取 JSON 记账草稿")
    confirm = operations.add_parser("confirm", help="确认草稿并取得回执")
    confirm.add_argument("draft_id")
    confirm.add_argument("key", help="该次确认的幂等键，重试时使用同一个键")
    args = parser.parse_args(argv)
    try:
        result = args.run(args)
    except HTTPException as error:
        parser.exit(1, json.dumps(error.detail, ensure_ascii=False) + "\n")
    except ValidationError as error:
        parser.exit(1, str(error) + "\n")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
