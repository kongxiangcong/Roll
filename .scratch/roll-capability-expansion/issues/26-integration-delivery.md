# 26: 增量工程交付与兼容验收

**What to build:** 用户得到可安装、可禁用、可恢复的新观察与研究功能，原功能继续可用。

**Blocked by:** [02 · 完整日线用途与来源缺口补齐](02-daily-evidence.md)；[03 · 有效交易状态与未知覆盖](03-status-evidence.md)；[04 · 公司行动版本与义务证据](04-action-lifecycle.md)；[05 · 后继政策完整冻结与验证消费者](05-policy-freeze-validation.md)；[06 · 当前动作有效期与政策派发](06-current-action-validity.md)；[07 · LOSS原因绑定恢复闭环](07-loss-recovery.md)；[13 · 财务分析进入单股与复盘](13-financial-observation.md)；[18 · 财报新闻接入现有日常运行](18-observation-worker.md)；[19 · QuantStats绩效图与导出](19-performance-report.md)；[20 · scikit-learn概率计算核验](20-probability-reference.md)；[21 · arch区块统计核验](21-block-stat-reference.md)；[22 · 新增特征快照与消融协议](22-feature-asof-protocol.md)

**Status:** ready-for-agent

**Completion:** pending

**Execution:** WAITING_FOR_DEPENDENCIES — 已核对02/03/04/05/06/07仍未complete；18/22工程依赖已交付，但不得跳过其余前置开始集成验收。

**Scope / inheritance:** 本票工程收口不等待08/23—25自然时间，但不能替代它们的真实验收。

**User stories:** US-51、US-52；共同遵循US-53—58。

**References:** [规格](../spec.md)、[执行顺序与依赖](../ticket-plan.md)、[验收追踪](../acceptance-map.md)。

## Acceptance criteria

- [ ] 固定集成版本、组件及权重清单、许可/NOTICE、锁文件和运行说明；在干净隔离环境完成安装与必要构建。
- [ ] 验证兼容迁移、旧工件读取/重放、备份恢复和禁用新增组件；原账户/资金/旧资格与原件不受改变。
- [ ] 按影响范围回归既有账户、来源、连续影子、执行意向、通知和恢复主路径；不重复无关长测试以凑通过数。
- [ ] 真实浏览器串联单股财务→原文、新闻→转载/情绪、报告→导出、设置→暂停；现有五入口与移动阅读保持。
- [ ] 交付逐项矩阵：工程、真实来源、文本模型评测、收益验证、正式启用分别记录；必需工程缺口存在则partial，不写全功能完成。
- [ ] 08/23—25若仍等待窗口/样本，列出实际条件与后续调用方式；不新建自动化，不在本票假启用或自动外发。
- [ ] 附本票适用的代码/依赖版本、公开行为验收、真实与METHOD边界、原失败及剩余条件；若继承另一会话成果，引用精确验收并核对当前版本。不得以仅写计划或仅实现拒绝路径替代所要求的正向能力。

## Implementation boundary

优先复用原服务和指定成熟组件；新增表、接口、页面与测试围绕本票用户路径增量实现，不横向重写整个模块。01交接票只做交接核对；08及23—25是真实运行操作。其他票的API/持久化/界面与测试应作为同一可演示切片交付。新组件不可写真实账本或自签资格；没有必要不新增测试入口或插件框架。

## Comments

2026-10-14：依据用户授权发布，尚未实施。完成状态与真实启动条件独立于分诊标签；先读01交接和任务计划，保留另一会话成果及原P0验收。


2026-10-20：现场逐票核对见[evidence/26-readiness/dependency-audit.json](../evidence/26-readiness/dependency-audit.json)。Completion仍pending，未勾选验收、未执行安装/迁移/正式收口。下一就绪工作需先补02—04权威契约、05指定真实工件/authority等、07真实资金；06仍依赖05。08/23—25真实条件另外保留。
