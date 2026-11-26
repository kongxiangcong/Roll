"""Run and retrieve local frozen trend experiments."""
import json
from pathlib import Path

from roll.v3.experiment import read_experiment, run_experiment, verify_experiment


def register_experiment_commands(commands):
    experiment = commands.add_parser("experiment", help="运行、查看和复现冻结趋势实验")
    actions = experiment.add_subparsers(required=True)

    run = actions.add_parser("run", help="从冻结数据和趋势协议运行三账本实验")
    run.add_argument("version")
    run.add_argument("snapshot_id")
    run.add_argument("--run-id")
    run.add_argument("--at")
    run.add_argument("--initial", type=Path, help="共同初始现金、持仓批次和预算 JSON")
    run.add_argument("--research-ref", help="关联研究档案引用，供回引实验结果")
    run.add_argument("--replay", action="store_true", help="登记为用于比较的回放")
    run.set_defaults(handler=_run)

    show = actions.add_parser("show", help="读取已保存的实验结果")
    show.add_argument("run_id", metavar="RUN_OR_REPORT_ID")
    show.add_argument("--trace", action="store_true", help="同时输出逐日账本轨迹")
    show.set_defaults(handler=_show)

    verify = actions.add_parser("verify", help="离线重建并核对实验结果标识")
    verify.add_argument("run_id", metavar="RUN_OR_REPORT_ID")
    verify.set_defaults(handler=_verify)


def _run(args, data_dir):
    initial = json.loads(args.initial.read_text(encoding="utf-8"), parse_float=str) if args.initial else None
    return run_experiment(
        data_dir, args.version, args.snapshot_id, run_id=args.run_id, at=args.at, initial=initial, replay=args.replay,
        research_ref=args.research_ref,
    )


def _show(args, data_dir):
    return read_experiment(data_dir, args.run_id, trace=args.trace)


def _verify(args, data_dir):
    return verify_experiment(data_dir, args.run_id)
