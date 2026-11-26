"""CLI commands for the frozen development experiment."""

from roll.v3.development_archive import CONCLUSIONS, DECISIONS, archive_development
from roll.v3.development_experiment import PRESET_ID, development_preset
from roll.v3.development_replay import (
    prepare_development, read_development_receipt, verify_development,
)


def register_development_commands(commands):
    preset = commands.add_parser("development-preset", help="查看有版本的江西铜业 E0/E1 开发预设")
    preset.set_defaults(handler=lambda args, data_dir: development_preset())
    run = commands.add_parser("development", help="用冻结快照发起江西铜业 E0/E1 开发实验任务")
    run.add_argument("--preset", choices=(PRESET_ID,), required=True)
    run.add_argument("--snapshot", required=True, help="本地冻结数据快照 ID")
    from roll.v3.research_tasks import add_executor_options

    add_executor_options(run)
    run.set_defaults(handler=_run)
    receipt = commands.add_parser("development-receipt", help="读取任务的冻结开发回执及逐日轨迹")
    receipt.add_argument("task_id")
    receipt.set_defaults(handler=lambda args, data_dir: read_development_receipt(data_dir, args.task_id))
    verify = commands.add_parser("development-verify", help="用原快照离线复算冻结开发回执")
    verify.add_argument("task_id")
    verify.set_defaults(handler=lambda args, data_dir: verify_development(data_dir, args.task_id))
    archive = commands.add_parser("development-archive", help="在任务内归档指定开发实验报告")
    archive.add_argument("task_id")
    archive.add_argument("--attempt", required=True, help="归档的研究尝试 ID")
    archive.add_argument("--report-version", required=True, help="审阅的报告版本")
    archive.add_argument("--conclusion", choices=CONCLUSIONS, required=True,
                         help="动作一致、差异集中于单段、证据不足或多段保留待解释差异")
    archive.add_argument("--reviewer", required=True, help="审阅人")
    archive.add_argument("--decision", choices=DECISIONS, required=True)
    archive.add_argument("--reason", required=True, help="停止或继续的审阅理由")
    archive.add_argument("--segment-ref", action="append", default=[], help="多段结论引用的冻结区段，可重复")
    archive.add_argument("--sizing-rule", help="继续时预定的仓位规则")
    archive.add_argument("--measurement", help="继续时预定的计量口径")
    archive.set_defaults(handler=_archive)


def _run(args, data_dir):
    from roll.v3.research_tasks import start_task

    manifest, receipt = prepare_development(data_dir, args.snapshot, preset_id=args.preset)
    return start_task(data_dir, manifest, executor_name=args.executor, timeout=args.timeout,
                      development_receipt=receipt)


def _archive(args, data_dir):
    return archive_development(data_dir, args.task_id, args.attempt, args.report_version,
                               conclusion=args.conclusion, reviewer=args.reviewer,
                               decision=args.decision, reason=args.reason, segment_refs=args.segment_ref,
                               sizing_rule=args.sizing_rule, measurement=args.measurement)
