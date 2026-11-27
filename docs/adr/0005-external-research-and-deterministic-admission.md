---
status: accepted
---

# 研究助手外置，并以确定性实验准入与本地裁决隔离研究和生产决策

Roll v3 采用“人或外部研究助手 → 本地 Roll CLI”单向研究交互，取代 [ADR 0001](0001-default-engineering-route.md) 在应用内集成 Agents SDK 的路线，并拒绝在盘后决策阶段调用大语言模型给出动作倾向。外部助手仅可通过 CLI 读取指定标的的公开行情、归因指标与公告材料并起草 `ResearchDossier`；经研究者确认发布后，档案中的结构化约束（`fundamental_gate`、`thesis_status`、`strategy_whitelist`、`invalidation_triggers`）与有效期才进入生产读取范围。`AccountSnapshot`、`TradeLog` 与 `RiskBudget` 严格留在本地账户与决策模块，确保盘后 `decide` 全程零模型调用、断网可重放，且不会出现规则计划与模型倾向并存的双重口径。

在策略准入上，v3 取代 [ADR 0003](0003-automated-validation-review.md) 的模型技术审阅门禁及 v2.1 无策略准入的状态，建立确定性的实验与注册表隔离：主动策略须先冻结 `StrategySpec`、数据快照与实验协议，在限制正式检验次数的锁定区间独立评估，并通过连续演化的前向 `ShadowAccount` 观察后，方可在 `StrategyRegistry` 中进入 `admitted` 状态参与生产主动决策；已揭示的验收集不得用于调参后重复验收。未准入候选仅允许在模拟命名空间运行，生产裁决统一按 P0（交易可执行性）至 P4（策略信号）优先级纯函数生成唯一生效的 `TradingPlan` 或观察状态。对应契约见 [v3 需求与架构设计](../design/architecture/roll_v3_trading_pipeline_spec.md) §4.4、§7.2、§9.3 与 §11.1。
