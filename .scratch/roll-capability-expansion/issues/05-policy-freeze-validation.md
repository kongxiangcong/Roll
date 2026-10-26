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

2026-10-20 实际家族预算核查：reconstructed19-v1保留同根3fit/1CAL，拟合最多余2/CAL余0，宿主早期副本不得重置余额。05缺四非中心工件，不能假定现有限额足够新增四次拟合；既有工件/REAL authority/独立支持/完整冻结门槛保持。只读元数据证据见[家族预算核查](../evidence/23-readiness/metadata-20261020/findings.md)，未读标签/封存或训练，05仍partial。

2026-10-15：按旧v2差量新增同家族设计参数绑定、统计算术例证、不可变工件、G1—G7缺口和METHOD净值/回撤前缀诊断。参数冻结不冒充完整冻结，complete_experiment_frozen=false。最终API1 PASS/21.16s，Chrome1 PASS/24.0s；旧完整冻结/账户不变、硬FAIL与INCONCLUSIVE/重放/唯一性/零基线边界已验证。见[逐阶段验收与确切剩余工程](../evidence/05-protocol/acceptance.md)。新真实消费者、成熟概率/同窗口风险匹配基准、v2G5绑定尚未接入，保持partial，未拟合新真实模型、消费SEALED、授资格或启计时。

2026-10-14：依据用户授权发布，尚未实施。完成状态与真实启动条件独立于分诊标签；先读01交接和任务计划，保留另一会话成果及原P0验收。


2026-10-15 审查修复：前缀查询 SQL 限定 revision<=目标，只校验目标历史；第4帧损坏后第3帧仍可重放。新增回归先失败后1 PASS/20.87s，复审开放发现0。保留旧successor_shadow源文件及冻结指纹。

2026-10-15 增量：已接入冻结佣金/滑点六场景的保存前缀费用消费者，公开运行/保存/重放与Chrome通过；已知硬风险失败保留，未知不补。其余G5/真实输入/完整冻结仍未完成。见[费用压力验收](../evidence/05-cost-stress/acceptance.md)。

2026-10-15 增量：已接入同前驱冻结/模型/截止的20/21保存CAL概率与区块参照绑定；公开保存/父错配拒绝/嵌套原件损坏拒绝/重启重放/Chrome通过。CAL不是独立成熟验证，G3仍INCONCLUSIVE，05仍partial。见[概率绑定验收](../evidence/05-probability-binding/acceptance.md)。

2026-10-15 增量：已接入同一METHOD轨迹的时间三段，承接原现金/各lot/净值；漏会话和未知边界不填补，超大跨度不压缩，API/Chrome/保存重放通过。见[时间三段验收](../evidence/05-time-segments/acceptance.md)。其余真实输入/共同风险基准/延迟/邻域/迁移与独立支持仍缺，05保持partial。

2026-10-15 增量：已接入空初始持仓的同窗口CASH控制，非空lot拒绝假定清仓；完整METHOD跨度/候选未知/已观察风险硬FAIL保留，API/Chrome/重放通过。见[CASH控制验收](../evidence/05-cash-control/acceptance.md)。risk_matched=false，完整基准与真实/独立支持仍缺，05保持partial。

2026-10-15 增量：已接入原登记CASH/START_HOLD/MA5_MA20描述轨迹，原引擎和不同持有时点保留；MA前置上下文缺失、未知会话与风险不可比明确，不裁窗。API1 PASS/37.54s、Chrome1 PASS/37.4s、构建及两路审查通过。见[原登记基准验收](../evidence/05-registered-controls/acceptance.md)。真实/共同风险匹配与余下G5仍缺，05保持partial。

2026-10-15 增量：六个原网格BUY/ADD入场压力已接入，默认逐前缀完整状态等于旧引擎，close/+2/0与50%/lot期限/预留释放可追踪；最终API2 PASS/49.73s、Chrome1 PASS/45.7s与构建通过。见[入场压力验收](../evidence/05-entry-stress/acceptance.md)。早退/到期及基准联合压力、真实/独立支持和完整冻结仍缺，05保持partial。

2026-10-15 增量：同费用前缀保存证据汇总已接入，五/六类工件正向绑定、混前缀拒绝、嵌套原件/硬FAIL/保存重放通过，CAL不拼日历。G6/G7移至启运后资格缺口，避免循环冻结前置。最终API2 PASS/69.96s、Chrome1 PASS/46.3s。见[证据汇总验收](../evidence/05-evidence-review/acceptance.md)。联合压力仍是下一可离线前沿，05保持partial。

2026-10-15 增量：十二固定配对费用/入场场景已同时消费保存候选与三原基准，默认曲线相等、原时点/未知/基准不可比保留；最终API1 PASS/63.63s、Chrome1 PASS/54.5s、构建与双审查通过。见[联合压力验收](../evidence/05-joint-stress/acceptance.md)。下一离线前沿为联合结果版本化接入汇总，不改变旧汇总重放；05仍partial。

2026-10-15 增量：联合压力已按独立新版本绑定至证据汇总，旧汇总GET/重放前后及重启相等；错源/嵌套损坏/硬FAIL保持，API1 PASS/46.21s、Chrome1 PASS/56.0s和构建通过。见[版本化汇总验收](../evidence/05-joint-review/acceptance.md)。真实/独立支持及其余完整G5仍缺，05保持partial。

2026-10-15 增量：原登记entry-only三档阈值已消费，support固定、base全state同原、逐档METHOD审计与训练清单分开，失败/中断/并发恢复/幂等留证。两项生命周期P2已修，API1 PASS/33.38s、修复后Chrome1 PASS/63.94s与构建通过。见[阈值邻域验收](../evidence/05-threshold-stress/acceptance.md)。未新增fit/CAL/SEALED额度；迁移审计及完整checker仍是离线前沿，05保持partial。

2026-10-15 增量：原迁移lot/登记scope审计已接入，原截止与新入场期限独立、到期阻塞不延长、空原持仓边界明确；位置身份P2已补，API1 PASS/22.88s、修复后Chrome1 PASS/61.85s与构建通过。见[迁移审计验收](../evidence/05-migration-audit/acceptance.md)。一致性不是真实迁移或G5资格；下一离线前沿为版本化工程完成检查，05仍partial。

2026-10-15 增量：版本化工程检查已正向绑定九类同源METHOD诊断，live尝试快照/终态父/错源/源完整性/保存重放通过；诊断包一致不等工程全完成或完整冻结，real-input/拟合邻域与资格缺口分列，G6/G7不作freeze前置。API1 PASS/60.79s、Chrome1 PASS/67.12s与构建/双审查通过。见[工程检查验收](../evidence/05-completion-check/acceptance.md)。中心槽位只读工件映射仍可继续，05保持partial。

### 原冻结主模型中心绑定（2026-10-15）

补齐 penalty1/lookback20 的精确冻结身份映射，绑定工程检查且不改旧记录；核验模型、特征、校准前后原件，21收盘价/20收益区间及DEV/CAL快照。非中心四工件、执行预测对齐、真实消费者及独立支持仍缺，不授邻域压力结论，整票保持partial。验收见 evidence/05-primary-center/acceptance.md。下一离线前沿是原CAL预测的独立完整日历METHOD执行回放，不再新增单纯聚合包装。

2026-10-15 增量：原CAL冻结模型20条校准后概率已按40会话完整日历驱动独立METHOD v2执行，非手填信号，原价格/概率精度和人工前缀保留。API1 PASS/66.32s实际BUY14/SELL34，Chrome/构建/双审查通过，见[模型执行回放验收](../evidence/05-model-replay/acceptance.md)。CAL拟合内重用不构成独立资格；真实消费者与02—04权威契约仍待实现/具备，四个非中心拟合工件未供，05保持partial。

2026-10-15 增量：来源输入到冻结features/predict与独立v2状态的管线已接通，生产入口严格消费旧PostClose包/宿主截止和原来源缺口；METHOD正向、CAS/漏日未知/模式隔离/原件/重启重放通过。两项P2（版本边界、预测前准入）已修，最终API1 PASS/93.32s与Chrome/构建通过，见[输入消费者验收](../evidence/05-input-consumer/acceptance.md)。现有producer仍强制状态/行动UNKNOWN，REAL正向未验收，不能宣称整05工程完成；四非中心产物、独立支持及真实来源契约仍缺。无新增拟合、SEALED访问或真实启运。
