# 4.1 来源就绪和有界补采

Status: ready-for-agent
Execution: resolved
Acceptance: core-verified; target-environment-checks-pending
Type: task
Spec: ../spec.md#r1
Blocked by: 前阶段完成；无阶段内依赖

## 需求
每证券类别每日最多3次，至少15分钟间隔；失败/不完整/过期输入允许追加尝试，完整停止；来源暂停不绕过；不补造停机期间记录。

## 验证
针对公共API/真实模块的离线确定性测试、前端类型检查与构建；运行条件不足时明确记录，不能标作通过。

## Answer
完成：每证券/类别/日期持久任务链最多3次，至少15分钟，21:00结束；就绪停止，用户取消不重试，暂停/退避生效。worker自动生成报告，旧版保留；同输入幂等。阶段相关24测试通过，扩展回归90通过；新增财报隔离与最终核心10通过。浏览器/Windows/10交易日见../../acceptance.md，尚未全部实机验收。

## Comments
2026-10-26：按用户授权创建。
