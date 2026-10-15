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
| [05 · 后继政策完整冻结与验证消费者](issues/05-policy-freeze-validation.md) | partial | 同源九类诊断、联合压力、阈值/迁移、工程检查、两主模型中心及原CAL预测完整日历执行已验收；来源包→模型→独立推进METHOD管线已补；REAL准入/authority、共同风险匹配/四非中心工件/独立支持和完整冻结仍缺 |
| [06 · 当前动作有效期与政策派发](issues/06-current-action-validity.md) | pending | 已发布，未实施 |
| [07 · LOSS原因绑定恢复闭环](issues/07-loss-recovery.md) | partial | 继承latch保护；原规则未登记，资金恢复语义已询问，未改真实状态 |
| [08 · 现有候选真实前向启运](issues/08-existing-forward-start.md) | pending | 已发布，未实施；含真实外部/时间条件 |
| [09 · AKShare利润表首个完整切片](issues/09-income-statement.md) | complete | 独立生产SDK/API/SQLite/Chrome已验收：3HTTP/5期/原件SHA/账户不变，预算封口 |
| [10 · 资产负债表与现金流三表联读](issues/10-balance-cashflow.md) | pending | 已发布，未实施 |
| [11 · 财务口径、修订与确定性指标](issues/11-financial-metrics.md) | pending | 已发布，未实施 |
| [12 · Docling表格与页码证据](issues/12-document-tables.md) | pending | 已发布，未实施 |
| [13 · 财务分析进入单股与复盘](issues/13-financial-observation.md) | pending | 已发布，未实施 |
| [14 · 单股新闻与正文归档](issues/14-news-ingestion.md) | pending | 已发布，未实施 |
| [15 · 新闻证券关联与转载去重](issues/15-news-entity-dedup.md) | pending | 已发布，未实施 |
| [16 · 中文情绪组件与有限评测](issues/16-sentiment-evaluation.md) | pending | 已发布，未实施 |
| [17 · 事件级情绪序列与覆盖说明](issues/17-sentiment-series.md) | pending | 已发布，未实施 |
| [18 · 财报新闻接入现有日常运行](issues/18-observation-worker.md) | pending | 已发布，未实施 |
| [19 · QuantStats绩效图与导出](issues/19-performance-report.md) | complete | 三条保存基准读取遗漏已修复；固定窗口/错位/API/Chrome/旧报告重放通过，未授资格 |
| [20 · scikit-learn概率计算核验](issues/20-probability-reference.md) | complete | 固定口径实际库/API/边界/Chrome/源绑定/重放已验；非独立统计资格 |
| [21 · arch区块统计核验](issues/21-block-stat-reference.md) | complete | 实际arch成对统计/API/边界/Chrome/保存重放通过；来源区间不足，独立有效性未授予 |
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


### 2026-10-15 当前收口与需确认事项

本地集成HEAD将在05-input-consumer提交后记录；01/19/20/21 complete，其余保留表中partial/pending。05补齐原主模型两中心身份、原CAL40会话20概率独立执行，以及来源输入→冻结特征/预测→独立v2状态的METHOD正向管线；不覆盖真实来源权威缺口或实际模型/独立资格。消费者最终API1 PASS/93.32s、Chrome/构建和双审查通过，原15脏文件与12旧模型依赖保留。

当前无已确认契约且工件齐备的新增独立消费者可正向验收。02—04需源证据才能接通REAL；05四非中心拟合工件/独立支持不从手填概率补造；08/23—25另需真实窗口/登记与授权。07仍需选择LOSS恢复语义。09已备独立一次性生产整链脚本及integration-plan.json（600362/8调用/18秒/8MiB/零重试重定向/隔离profile），等待用户确认，不重开已关闭的源评估；09未complete故10—18及22/26依赖仍未解除。没有推送、PR、真实前向起点、资格或真实资金状态变化。

2026-10-15 用户确认07恢复语义与09一次预算；09独立生产整链成功并关闭，票09 complete。07已解除needs-info并进入实施；10/12/14的09依赖已解除，按编号在07之后继续。前文待确认状态为历史快照，不再要求重复授权。

2026-10-15：07原因绑定LOSS恢复工程交付；API总计42通过及已修复旧基线fixture单项通过、子进程2通过、Chrome/构建及双审查证据见07-loss-recovery/acceptance.md。原峰值及历史保留，再次越界重新锁定；未启用真实资金，07保留partial。下一依赖就绪工程票10，复用09采集/原件约定；09已封口预算不重开。
