# Spec review · Roll continuation

Reviewed `d1b867e...14568b1582f9500ee091dabe2b741224e95e5322` in `D:/dsh-proj/Roll/.scratch/worktrees/13-switch`. Read-only scope: delivered 12/13, Fuyao adapter, five fixed background indices and METHOD clock fixes.

## Finding

**[P2] 两后端取证子请求丢失显式除权事项来源** — `backend/src/roll/agents/codex_process.py:361–363`（共用工具；DeepSeek 在 `deepseek_process.py:74` 调用）。新增 `DataRequest.adjustment_source` 默认 `EASTMONEY`（`market/evidence.py:42`），页面允许选择 `FUYAO`。但工具创建子请求时只继承 `daily_source` 和 `quote_source`，没有继承 `adjustment_source`。因此用户明确选择扶摇除权事项并启动任一模型后端，实际取数会静默改用东方财富；来源可能返回不同覆盖或失败，父请求配置与实际工具依据不一致。

规格 `spec.md:193`：“来源切换先检查对象、日期、单位、复权和字段定义，保存转换或阻断理由，不静默拼接。” 票12 `issues/12-deepseek-evidence.md:18`：“使用 07 的 DataRequest/RetrievalRun 契约”。此路径未主动请求换源，也没有换源理由。

在根 Python、工作树 PYTHONPATH、`ROLL_ENV=test`、凭据移除的只读工具捕获复现中，父 `adjustment_source=FUYAO`，生成的子 `DataRequest.adjustment_source=EASTMONEY`；在创建子请求即停止，联网0。应继承该字段，并增加共用工具通过两后端保持显式除权来源的回归验证。

## Remaining scope

未发现其他有充分证据的规格缺失、越界扩展或实现错误。12/13验收区分真实模型、METHOD材料、30+3/30+5与全部/重叠性能样本；Fuyao/PIT、CAL40及19的partial边界明确，未宣称实际模型资格或前向起点。METHOD时钟仅用于固定材料时序，没有修改生产时点门禁。未运行长套、浏览器或提供方任务。

Spec: 1 finding; highest severity P2.
