"""CLI commands for the frozen development experiment."""

from roll.v3.development_experiment import PRESET_ID, development_preset, freeze_development_inputs, public_manifest


def register_development_commands(commands):
    preset = commands.add_parser("development-preset", help="查看有版本的江西铜业 E0/E1 开发预设")
    preset.set_defaults(handler=lambda args, data_dir: development_preset())
    run = commands.add_parser("development", help="用冻结快照发起江西铜业 E0/E1 开发实验任务")
    run.add_argument("--preset", choices=(PRESET_ID,), required=True)
    run.add_argument("--snapshot", required=True, help="本地冻结数据快照 ID")
    run.set_defaults(handler=_run)


def _run(args, data_dir):
    from roll.v3.research_tasks import record_task_result

    inputs = freeze_development_inputs(data_dir, args.snapshot, preset_id=args.preset)
    manifest = public_manifest(inputs)
    result = {"status": "frozen", "preset_id": args.preset,
              "snapshot_id": args.snapshot, "input_ref": inputs.input_ref}
    if inputs.sample["effective_window"] is None:
        result.update(status="blocked", failure_stage="common_sample", gaps=[{
            "reason": "开发窗口没有两组特征同时就绪的交易日",
            "required_evidence": "连续且可用的江西铜业量价与权益观测及沪深 300 收盘观测",
            "blocking": True, "coverage_ref": inputs.input_ref + "#sample",
            "candidate_day_count": inputs.sample["candidate_day_count"],
            "loss_reason_counts": inputs.sample["loss_reason_counts"],
        }])
    return record_task_result(data_dir, manifest, result)
