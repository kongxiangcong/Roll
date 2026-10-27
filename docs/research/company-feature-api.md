# 公司研究候选特征与增量验证协议

11仅从固定共享分析快照读取候选信息，并保存可重放的不可变导出。它不产生上涨概率，不写ForecastBundle、旧模型、实验预算、账户或能力授权，也没有拟合/执行/SEALED入口。旧 `/api/research/feature-*` 财务情绪合同保持原样；以下新增入口均在 `/api/company-research`。

|接口|行为|
|---|---|
|GET `/feature-schema`|定义版本、字段语义及缺失政策|
|POST `/feature-snapshots`|固定snapshot_id、observation_at、purpose、可选scenario及idempotency_key导出|
|GET `/feature-snapshots/{feature_snapshot_id}`|只读原版本、来源、缺失、年龄、归档hash|
|POST `/feature-protocols`|保存关联原实验的不可变预注册补充；不登记新family或预留预算|
|GET `/feature-protocols/{protocol_id}`|读取原补充协议|
|POST `/feature-coverage`|对明确feature_snapshot_ids及可选protocol_id返回有据覆盖诊断|

## 导出合同

```json
{"snapshot_id":"fixed-analysis-id","observation_at":"2026-10-28T00:30:00+08:00","purpose":"CURRENT_RESEARCH","scenario":"baseline","idempotency_key":"my-export-1"}
```

purpose可为CURRENT_RESEARCH或HISTORICAL_PIT，时间须有时区且不在未来。调用者不能提供数值、情景权重或概率字段；extra字段拒绝。scenario必须显式选择，不能默选最有利情景。并发同key/同请求返回同不可变结果，不同请求409。读取固定快照，不默认latest；后续新材料或修订不能改旧导出。

四个候选字段：当前假设中带前版引用的数量、已陈述失效条件数量、最早有源未来验证事件的本地日历天数、当前市场权益相对所选研究情景权益的比例差 `market_equity/equity_value-1`。最后一项在原当前用途经济审核conditional/reviewed且可用、固定报价为RAW_NOMINAL、A/H份额与币种均通过原报价/估值合同且明确scenario时才可计算；blocked/unreviewed/无报价/方法不兼容均为null及原因，不导出诊断价格。比例差不是反推唯一市场原因或上涨概率。

count只表达固定hypothesis集合中已陈述项目的范围，不表示已经完成风险核查。完全没有hypothesis时两个count为null；有完整固定集合且其中没有带parent的假设，修订count可以为真实0，不代表经营未变。无有源日期保持null。日期差使用Asia/Shanghai，避免UTC与公司本地日期跨午夜差一天。

actual available_at取所依赖实际材料/事实received/consumable、输入建立、假设/快照生成、经济审核、固定报价context形成等时间的最大值；不是公告日期或报告期。迟于observation则所有候选降为null。HISTORICAL_PIT另要求原packet有严格历史时点证明，当前重建的旧资料即使今天可读也不能作为当时可用特征。信息年龄分别保留原材料可消费时间/年龄、披露时间/年龄及未知披露时间数量，不以页面读取或快照重述刷新原件年龄。

## 覆盖及预注册

```json
{"company_ids":["company-id"],"baseline_protocol_id":null,"baseline_model_id":null,"basis":"明确尚未绑定原量价模型；不申请拟合","idempotency_key":"supplement-1"}
```

原protocol/model ID需成对提供，并只读取既有元数据、固定hash与scope；不调用旧feature-plan注册器（其会预留预算）。未绑定真实冻结原量价baseline返回DRAFT_UNBOUND；有效绑定才可标FROZEN_SUPPLEMENT_NOT_FIT_AUTHORIZED，两者均real_fit_admitted=false。协议保存事件与20-session期限、原量价模型/事件/窗口/费用/停止规则继承关系、固定候选集、同样本对照、时间外窗口与purge/embargo、Brier/log-loss/校准、风险/行业暴露对照、成熟支持和停止规则。实际有绑定时继承原事件期限，不用补充入口重新计时或重置family预算。

协议的200独立成熟事件及每已占用校准bin20例是补充协议的预注册最低支持，不能取代原实验更严格门槛；完整事件匹配、原冻结baseline预测/标签与窗口尚未绑定时保持INCONCLUSIVE。未来若另行授权实验，执行器仍须检查原family剩余预算、先前失败/中止/预留、原截止日期与完整冻结协议；本入口不授予执行权限。

coverage以公司、原始来源根及报告期去重。保留原件SHA和引用版本，转载/季度多日报/A-H重复使用不能增独立经营证据。同源原件即使多次导出也不增加支持。它明确区分观察数、可用独立原件单位和独立成熟结果样本；当前没有事件匹配标签与固定baseline预测绑定，独立成熟样本为0并返回INCONCLUSIVE，不能用原件数替代成熟样本。全缺失、无报告期或不满足可得用途的观察不计有效原件支持，不填0伪装有效特征。

导出、协议及其规范JSON档案进入既有EvidenceStore/Backups；恢复同时核原快照/公司/core、字段引用、缺失mask、档案与协议design hash。重算JSON/hash但换快照的损坏仍拒绝。离线恢复读原文，不重调模型。
