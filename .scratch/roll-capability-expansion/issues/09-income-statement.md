# 09: AKShare利润表首个完整切片

**What to build:** 用户在单股查看带原件、单位和报告期的利润表，取数失败不影响原功能。

**Blocked by:** [01 · 交接基线与既有能力继承](01-handoff-baseline.md)

**Status:** ready-for-agent

**Completion:** complete

**Execution:** COMPLETE — 用户批准的一次生产SDK→API→SQLite→只读Chrome整链已验收；3HTTP/5期/原件SHA/账户不变，预算已封口。

**Scope / inheritance:** 新增财务观察；复用来源配置/归档/子进程，优先AKShare。

**User stories:** US-17、US-18；共同遵循US-53—58。

**References:** [规格](../spec.md)、[执行顺序与依赖](../ticket-plan.md)、[验收追踪](../acceptance-map.md)。

## Acceptance criteria

- [ ] 锁定AKShare版本与许可、Windows/Python兼容及最小依赖，在既有隔离执行边界使用实际库API；不手写替代财务爬虫。
- [ ] 通过单证券有限采集→原响应归档→利润表版本→公开查询→单股页面完成端到端链，保留原字段与规范字段。
- [ ] 记录报告期、披露/接收时点、币种/单位、合并/母公司和来源；披露时间未知不推定报告期末。
- [ ] 若库接口不能保存原响应，使用可核验限定适配或标记不可用于原件要求用途，不冒充原件；Tushare仅在已有权限配置下作为替代。
- [ ] 真实一次有限查询与固定异常响应分别验，失败/取消/损坏/重复运行可解释，原行情、账户与旧研究工件不变。
- [ ] 附本票适用的代码/依赖版本、公开行为验收、真实与METHOD边界、原失败及剩余条件；若继承另一会话成果，引用精确验收并核对当前版本。不得以仅写计划或仅实现拒绝路径替代所要求的正向能力。

## Implementation boundary

优先复用原服务和指定成熟组件；新增表、接口、页面与测试围绕本票用户路径增量实现，不横向重写整个模块。01交接票只做交接核对；08及23—25是真实运行操作。其他票的API/持久化/界面与测试应作为同一可演示切片交付。新组件不可写真实账本或自签资格；没有必要不新增测试入口或插件框架。

## Comments

2026-10-14：依据用户授权发布，尚未实施。完成状态与真实启动条件独立于分诊标签；先读01交接和任务计划，保留另一会话成果及原P0验收。


2026-10-15：AKShare1.19.1真实来源一次有限查询成功；METHOD API/SDK/Chrome链和原件、版本、取消、金额修订审查修复通过。完整验收与真实运行剩余条件见[09 acceptance](../evidence/09-financial/acceptance.md)。原预算封口，不重复联网冒充验收。

2026-10-15 用户批准独立生产整链，实际3HTTP/11.623秒成功，5期3原响应，Chrome只读1 PASS/21.0s；见[integration acceptance](../evidence/09-financial/integration-acceptance.md)。此前待确认事项已解除，09工程complete，10/12/14依赖可进入；不授PIT、模型或资金资格。
