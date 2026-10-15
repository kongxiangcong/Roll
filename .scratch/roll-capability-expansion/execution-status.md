# 能力补齐执行记录

**Status:** ready-for-agent
**Completion:** pending
**Execution:** IN_PROGRESS — 2026-10-15 用户显式启动，集成分支 codex/roll-capability-expansion。

2026-10-14：按用户要求使用to-spec/to-tickets发布计划；另一个会话仍在执行。仅生成本feature文档，不安装、不修改产品、不取数、不训练、不发送消息、不创建定时任务、不提交或推送。

## 启动门槛

用户在另一会话结束后明确要求开始，才运行01交接。旧调研状态可能已经变化，必须按最终交付重核。尚无本计划实施验收，不能将ready-for-agent解释为运行条件已满足。

## 当前票状态

| 票 | Completion | 备注 |
| --- | --- | --- |
| [01 · 交接基线与既有能力继承](issues/01-handoff-baseline.md) | complete | 交接映射与当前有限兼容检查3 PASS/35.84s；真实服务当前不可访问 |
| [02 · 完整日线用途与来源缺口补齐](issues/02-daily-evidence.md) | partial | 已继承采集/重放，页面查询和Chrome/手机/构建通过；完整session/RAW修订依据不足 |
| [03 · 有效交易状态与未知覆盖](issues/03-status-evidence.md) | partial | 截止查询/单股来源区/API2 PASS及Chrome通过；全状态与否定覆盖依据不足 |
| [04 · 公司行动版本与义务证据](issues/04-action-lifecycle.md) | partial | 截止版本/旧义务查询和单股原件链已验收，生命周期和完整覆盖待证 |
| [05 · 后继政策完整冻结与验证消费者](issues/05-policy-freeze-validation.md) | partial | 参数绑定和METHOD前缀诊断/API/Chrome通过；完整实验与真实/概率/基准/G5消费者仍缺 |
| [06 · 当前动作有效期与政策派发](issues/06-current-action-validity.md) | pending | 已发布，未实施 |
| [07 · LOSS原因绑定恢复闭环](issues/07-loss-recovery.md) | partial | 继承latch保护；原规则未登记，资金恢复语义已询问，未改真实状态 |
| [08 · 现有候选真实前向启运](issues/08-existing-forward-start.md) | pending | 已发布，未实施；含真实外部/时间条件 |
| [09 · AKShare利润表首个完整切片](issues/09-income-statement.md) | pending | 已开始发行/许可与隔离环境核对，尚无业务验收 |
| [10 · 资产负债表与现金流三表联读](issues/10-balance-cashflow.md) | pending | 已发布，未实施 |
| [11 · 财务口径、修订与确定性指标](issues/11-financial-metrics.md) | pending | 已发布，未实施 |
| [12 · Docling表格与页码证据](issues/12-document-tables.md) | pending | 已发布，未实施 |
| [13 · 财务分析进入单股与复盘](issues/13-financial-observation.md) | pending | 已发布，未实施 |
| [14 · 单股新闻与正文归档](issues/14-news-ingestion.md) | pending | 已发布，未实施 |
| [15 · 新闻证券关联与转载去重](issues/15-news-entity-dedup.md) | pending | 已发布，未实施 |
| [16 · 中文情绪组件与有限评测](issues/16-sentiment-evaluation.md) | pending | 已发布，未实施 |
| [17 · 事件级情绪序列与覆盖说明](issues/17-sentiment-series.md) | pending | 已发布，未实施 |
| [18 · 财报新闻接入现有日常运行](issues/18-observation-worker.md) | pending | 已发布，未实施 |
| [19 · QuantStats绩效图与导出](issues/19-performance-report.md) | pending | 已发布，未实施 |
| [20 · scikit-learn概率计算核验](issues/20-probability-reference.md) | pending | 已发布，未实施 |
| [21 · arch区块统计核验](issues/21-block-stat-reference.md) | pending | 已发布，未实施 |
| [22 · 新增特征快照与消融协议](issues/22-feature-asof-protocol.md) | pending | 已发布，未实施 |
| [23 · 后继候选真实训练与完整冻结](issues/23-successor-fit.md) | pending | 已发布，未实施；含真实外部/时间条件 |
| [24 · 后继候选真实前向启运](issues/24-successor-forward.md) | pending | 已发布，未实施；含真实外部/时间条件 |
| [25 · 后继实验终点验证交付](issues/25-successor-verdict.md) | pending | 已发布，未实施；含真实外部/时间条件 |
| [26 · 增量工程交付与兼容验收](issues/26-integration-delivery.md) | pending | 已发布，未实施 |

## 规划文档检查

2026-10-14：只读结构检查通过：30个Markdown文件、26张连续编号任务、58条连续编号用户故事；本地引用全部可解析，依赖均指向先前票且无环，每票保留pending/NOT_STARTED及验收条件。另检查08没有错误依赖正式动作/LOSS恢复、26没有依赖真实自然时间票。此结果仅说明计划结构通过，不代表产品测试或任何能力已经实施。

## 后续记录约定

### 2026-10-15 启动与交接接受

本轮用户已明确启动，前述 NOT_STARTED 为2026-10-14发布历史。按编号单票推进。详见[交接](handoff.md)：HEAD fe5d01c7…及9份tracked旧修改、6份旧新源码受保护；另一实施会话completed/idle。既有47项日线验收与政策/费用/行动验收按原边界继承；当前3项公开API/隔离SQLite检查通过。默认沙箱socket拒绝和首次测试无输出中止分别保留。只读服务复核8010连接拒绝、8010/5173无监听，不将历史运行状态当当前。02开始补页面查询；完整session/状态/行动覆盖仍不足，原资格NOT_GRANTED，未建立真实前向起点。原P0任务不改写。

每票追加实际基线、继承范围、实现与独立验收、失败/阻塞、剩余条件和下一可执行票。当前没有假定真实起点、资格或资金启用；这份状态不覆盖原P0执行账本。

