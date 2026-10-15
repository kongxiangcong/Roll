# 05: 后继政策完整冻结与验证消费者

**What to build:** 固定后继政策能够保存完整实验并输出有依据的验证结论。

**Blocked by:** [01 · 交接基线与既有能力继承](01-handoff-baseline.md)

**Status:** ready-for-agent

**Completion:** partial

**Execution:** PARTIAL — 同家族参数冻结/METHOD前缀验证已交付；完整实验及真实/概率/基准/G5消费者待补。

**Scope / inheritance:** 旧P020/21差量；复用既有政策后继、连续影子和G1—G7。

**User stories:** US-9、US-10；共同遵循US-53—58。

**References:** [规格](../spec.md)、[执行顺序与依赖](../ticket-plan.md)、[验收追踪](../acceptance-map.md)。

## Acceptance criteria

- [ ] 沿用交接时已登记的经济目标、期限、费用和动作规则，补完整经济/统计协议必填与验证消费者；不新增策略搜索。
- [ ] ADD/HOLD/WAIT/EXIT、反向冷却、迁移和各lot期限按所属版本消费；沿用已有通过案例，仅新增未覆盖差量。
- [ ] 冻结依赖、方法、支持要求、停止规则齐全才允许完整冻结；缺失返回结构化原因和页面提示。
- [ ] 参数未登记时先保存后继设计及依据，禁止先看确认性结果再选阈值；实际拟合/封存访问沿既有额度和授权。
- [ ] 用公开接口检验冻结→影子推进→验证→查询/重放，PASS/FAIL/INCONCLUSIVE与METHOD/REAL分列；未知不得补成通过。
- [ ] 旧冻结工件及预算不变；真实证据不足保持partial，完整工程验收不授予正式资格。
- [ ] 附本票适用的代码/依赖版本、公开行为验收、真实与METHOD边界、原失败及剩余条件；若继承另一会话成果，引用精确验收并核对当前版本。不得以仅写计划或仅实现拒绝路径替代所要求的正向能力。

## Implementation boundary

优先复用原服务和指定成熟组件；新增表、接口、页面与测试围绕本票用户路径增量实现，不横向重写整个模块。01交接票只做交接核对；08及23—25是真实运行操作。其他票的API/持久化/界面与测试应作为同一可演示切片交付。新组件不可写真实账本或自签资格；没有必要不新增测试入口或插件框架。

## Comments

2026-10-15：按旧v2差量新增同家族设计参数绑定、统计算术例证、不可变工件、G1—G7缺口和METHOD净值/回撤前缀诊断。参数冻结不冒充完整冻结，complete_experiment_frozen=false。最终API1 PASS/21.16s，Chrome1 PASS/24.0s；旧完整冻结/账户不变、硬FAIL与INCONCLUSIVE/重放/唯一性/零基线边界已验证。见[逐阶段验收与确切剩余工程](../evidence/05-protocol/acceptance.md)。新真实消费者、成熟概率/同窗口风险匹配基准、v2G5绑定尚未接入，保持partial，未拟合新真实模型、消费SEALED、授资格或启计时。

2026-10-14：依据用户授权发布，尚未实施。完成状态与真实启动条件独立于分诊标签；先读01交接和任务计划，保留另一会话成果及原P0验收。


2026-10-15 审查修复：前缀查询 SQL 限定 revision<=目标，只校验目标历史；第4帧损坏后第3帧仍可重放。新增回归先失败后1 PASS/20.87s，复审开放发现0。保留旧successor_shadow源文件及冻结指纹。

2026-10-15 增量：已接入冻结佣金/滑点六场景的保存前缀费用消费者，公开运行/保存/重放与Chrome通过；已知硬风险失败保留，未知不补。其余G5/真实输入/完整冻结仍未完成。见[费用压力验收](../evidence/05-cost-stress/acceptance.md)。

2026-10-15 增量：已接入同前驱冻结/模型/截止的20/21保存CAL概率与区块参照绑定；公开保存/父错配拒绝/嵌套原件损坏拒绝/重启重放/Chrome通过。CAL不是独立成熟验证，G3仍INCONCLUSIVE，05仍partial。见[概率绑定验收](../evidence/05-probability-binding/acceptance.md)。

2026-10-15 增量：已接入同一METHOD轨迹的时间三段，承接原现金/各lot/净值；漏会话和未知边界不填补，超大跨度不压缩，API/Chrome/保存重放通过。见[时间三段验收](../evidence/05-time-segments/acceptance.md)。其余真实输入/共同风险基准/延迟/邻域/迁移与独立支持仍缺，05保持partial。

2026-10-15 增量：已接入空初始持仓的同窗口CASH控制，非空lot拒绝假定清仓；完整METHOD跨度/候选未知/已观察风险硬FAIL保留，API/Chrome/重放通过。见[CASH控制验收](../evidence/05-cash-control/acceptance.md)。risk_matched=false，完整基准与真实/独立支持仍缺，05保持partial。

2026-10-15 增量：已接入原登记CASH/START_HOLD/MA5_MA20描述轨迹，原引擎和不同持有时点保留；MA前置上下文缺失、未知会话与风险不可比明确，不裁窗。API1 PASS/37.54s、Chrome1 PASS/37.4s、构建及两路审查通过。见[原登记基准验收](../evidence/05-registered-controls/acceptance.md)。真实/共同风险匹配与余下G5仍缺，05保持partial。
