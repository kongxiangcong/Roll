# Roll V3 双流水线开发工单

本轮交付主方案 §13 的单股 M0。研究按证据变化或实验需要发起，盘后决策按交易日和账户运行。下表按一次业务流程组织；各票的直接开发前置见票内。[V3 主方案](../../docs/design/architecture/roll_v3_trading_pipeline_spec.md) · [M0 开发规格](spec.md)

| 流程 | 用户从哪里开始 | 交付与验收 |
| --- | --- | --- |
| 研究流水线 · §4.1、§6、§7 | 指定一只股票，取公开证据和量价，提出可证伪的投资假设 | [04 交付多年量价与行业对照](issues/04-market-industry-research.md) 提供量化输入；[03 发布第一份个股研究档案](issues/03-research-dossier.md) 管理假设、证据和档案发布；[07 冻结趋势实验并重放信号](issues/07-freeze-trend-experiment.md) 登记实验和策略版本；[09 完成多年趋势回测与双基准](issues/09-trend-backtest.md) 交付可回引的结果和双基准。研究者可依据新证据或实验结果再发布档案。 |
| 研究 → 决策 · §4.3 | 在指定时点查询已发布档案和策略注册状态 | [03 发布第一份个股研究档案](issues/03-research-dossier.md) 拥有 ResearchDossier，[07 冻结趋势实验并重放信号](issues/07-freeze-trend-experiment.md) 拥有 StrategyRegistry；[08 生成账户唯一生效计划](issues/08-after-close-plan.md) 按生效时间与适用条件消费两者。M0 的冻结趋势候选供模拟使用，正式计划允许观察。 |
| 决策流水线 · §4.2、§9 | 盘后冻结输入，读取账户与风险预算，识别市场、行业及个股状态 | [02 建立真实账户镜像](issues/02-account-mirror.md) 提供本地账户，[08 生成账户唯一生效计划](issues/08-after-close-plan.md) 按 P0–P4 比较候选并冻结唯一计划，[10 结清计划资金预留](issues/10-release-commitments.md) 结清预留，[11 对照前向影子与真实执行](issues/11-forward-review.md) 记录次日真实与影子结果。 |
| 复盘 → 重新研究 · §10 | 回查某份计划，从偏差或证伪条件定位原假设 | [11 对照前向影子与真实执行](issues/11-forward-review.md) 把证据及计划引用交回 [03 发布第一份个股研究档案](issues/03-research-dossier.md)。研究者发布新版本后，后续盘后计划才读取新约束。 |
| 共用数据及执行规则 · §5、§11 | 重读同一时点数据，按相同的交易与权益口径解释结果 | [01 冻结并重读一段真实行情](issues/01-market-snapshot.md) 冻结数据，[05 跨除权日结算在途权益](issues/05-settle-entitlements.md) 核算现金与在途权益，[06 次一交易时点模拟成交](issues/06-next-session-fill.md) 在下一合法时点撮合。回测与前向影子使用同一组规则。 |

**M0a 工程准出**由 [12 切换 v3 工作台并签收 M0a](issues/12-m0a-workbench.md) 验收两条流水线的交接和反馈。通过后可投入日常使用并启动 M1。**M0b 运行签收**由 [13 签收连续 20 个真实交易日](issues/13-m0b-forward-window.md) 验收独立的真实运行窗口。M1–M4 按主方案另行安排。
