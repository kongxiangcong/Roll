# 19: QuantStats绩效图与导出

**What to build:** 用户能从既有研究结果查看清晰绩效图表与可追溯离线报告。

**Blocked by:** [01 · 交接基线与既有能力继承](01-handoff-baseline.md)

**Status:** ready-for-agent

**Completion:** complete

**Execution:** COMPLETE — 保存三基准适配遗漏已修复；完整窗口/错位/API/Chrome/旧工件重放已验。

**Scope / inheritance:** 复用原报告、净值和归档；Apache-2.0组件版本待实施锁定。

**User stories:** US-37、US-38；共同遵循US-53—58。

**References:** [规格](../spec.md)、[执行顺序与依赖](../ticket-plan.md)、[验收追踪](../acceptance-map.md)。

## Acceptance criteria

- [x] 以只读适配调用QuantStats，输入Roll已有收益及基准序列，不使用库自动下载或另算交易账本。
- [x] 保持ACTUAL/HISTORICAL/SHADOW/ACCOUNT_CONDITIONAL分列；外部转入、费用及真实成交差异不混成策略收益。
- [x] 固定窗口、年化和无风险口径；核验dropna、首非零匹配、填零等预处理，未知区段单列，不缩短窗口伪装完整。
- [x] 在既有报告页提供曲线/回撤/月度收益及导出，报告包含数据/方法版本、覆盖和资格限制。
- [x] 公共接口与浏览器/导出验全零、短窗口、漏日、现金流、基准错位和旧报告重放；不足支持不显示误导指标。
- [x] 附本票适用的代码/依赖版本、公开行为验收、真实与METHOD边界、原失败及剩余条件；若继承另一会话成果，引用精确验收并核对当前版本。不得以仅写计划或仅实现拒绝路径替代所要求的正向能力。

## Implementation boundary

优先复用原服务和指定成熟组件；新增表、接口、页面与测试围绕本票用户路径增量实现，不横向重写整个模块。01交接票只做交接核对；08及23—25是真实运行操作。其他票的API/持久化/界面与测试应作为同一可演示切片交付。新组件不可写真实账本或自签资格；没有必要不新增测试入口或插件框架。

## Comments

2026-10-14：依据用户授权发布，尚未实施。完成状态与真实启动条件独立于分诊标签；先读01交接和任务计划，保留另一会话成果及原P0验收。


2026-10-15：QuantStats0.0.86只读切片、公开/API/数值/浏览器/离线排版已验，双轴审查0开放发现。未制造缺失基准，保持partial。见[19 acceptance](../evidence/19-performance/acceptance.md)。

2026-10-15 完成修复：三条保存基准原已存在，此前适配遗漏判断已更正。实际库/API/错位拒比/Chrome/离线导出/修复前旧报告重放通过，见[最终验收](../evidence/19-baselines/acceptance.md)。没有重算交易轨迹或授予资格。
