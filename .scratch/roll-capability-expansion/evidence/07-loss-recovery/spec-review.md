# 07 LOSS recovery — Spec review

基线 `33d2a9c`，仅检查本次 LOSS 后继规则、服务、funding 增量和公开测试；未测试、联网或修改业务代码。依据 [ticket 07](../../issues/07-loss-recovery.md) 及 spec US-13/14，最终定向复核开放 0 项。

1. **P2 已关闭：REAL 正向恢复路径。** REAL 分支现独立读取 `capabilities.valuations.get(replay=True)`，验证原来源重放、权威口径、当前账户、required_as_of 与上海当日，不再依赖恒过期的动作包。此为代码路径复核，未宣称现有真实资格足以正向恢复；不要求伪造 REAL 凭证。

2. **P2 已关闭：提交前完整当前事实核对。** writer 锁内重读 `action_loss_state`、数据身份及 pending drafts，重新执行 `use_check`，变化即拒绝。新增同步屏障保留真实 capture 返回值，随后经公开 API 创建不改变账户版本的待处理草稿，确认激活 409 且没有 receipt/ACTIVE。

递归原件校验覆盖 receipt→check→rule 与 snapshot 绑定；损坏原件时 funding/receipts/幂等重试均拒绝。`api-final.log` 保存 2 PASS / 22.25s，包含保留峰值/旧终态、旧动作重放，以及新越界后反弹/扩资不解除 latch 的字面契约检查。UI/浏览器与其余最终验收据实另列；本回归属于隔离 METHOD 工程证据，真实资格及真实资金恢复均未完成。

## 最终收口复核

**P2 已关闭：确定失败后的 UI 永久锁定。** `loss-recovery-panel.tsx` 对确定的 `409 / LOSS_RECOVERY_CURRENT_CONDITIONS_CHANGED` 清除 pending/sessionStorage 与旧 check，reload 后允许重新核验；网络异常和其他未知结果保留原键，遇已使用 check 先读取受校验回执，找到相同 check 后才结束待确认。浏览器增量测试注入第一次确定409、验证按钮重新可用、刷新后重新检查并真正完成 METHOD 恢复。复核时 `browser-refusal-final.log` 尚在运行，故不预称新增浏览器用例已通过。

历史 marker 修复已确认：峰值6000→7000仍低于新阈值时，明确继承 `historical_triggered` 与 recovery_id；真实越界继续 latch。保存日志记录主回归42通过/1个旧失败，基线同案复现并补齐监测来源后 `successor-final.log` 单项1 PASS/9.22s，不能称原批次全绿。真实进程退出 before/after commit 为2 PASS/29.62s；Chrome1 PASS/25.5s。终态 predecessor UI消费原命令，未扩资格。

上述 UI 修复及最终验收据实归档后可称工程交付；ticket 明文要求真实启用条件不足保持 partial，因此当前真实资格与实际资金恢复仍未启用，不能合并写 complete。
