# Final internal two-axis code review

Fixed baseline: ca912b8194a56d9a3c32cc07695d5e714f7f99f5. Product snapshot: 80fbcc23c8440e7210221144c020d315b9784773. Subsequent182de124/fbc8bd5 are receipts/status only. Complete commit list: commits.txt. This is internal development review; no new actual provider research ReviewRecord, model call, qualification, source request or external notification.

## Standards


范围：`ca912b8194a56d9a3c32cc07695d5e714f7f99f5...80fbcc23c8440e7210221144c020d315b9784773`。固定产品快照；已审阅全部变更的 Python 生产代码、React 页面/组件与公共接口，并定向核对来源契约与归档指纹。

**文档标准：0 项可操作违例。** 对照 AGENTS.md、docs/agents/{issue-tracker,triage-labels,domain}.md、GLOSSARY.md、ADR 0001/0003/0004、spec.md 的 Testing Decisions 和 project-layout.md：Host 保持账户、资金、资格写入责任；账户确认与动作失效共用受控事务；API/单 worker 共用具体用例，外部发送在短写事务之外；METHOD 与真实证据分列，冻结归档与生产授权没有混为一体。React 展示服务端判定，没有第二套账本或资格引擎。

**启发式 smells：0 项可操作问题。** 按完整 12 项 baseline 检查。不同来源的有限采集/回放形状及关键节点的重复门禁有当前契约、不同失败语义和并发失效依据；依 project-layout.md“不过度抽象”“不过度防御”的规则，不要求泛化 Adapter、事务框架或删除必要复核。未发现值得新增抽象解决的重复复杂性、无调用扩展点或职责散落。

这是只读静态 Standards 审查；未运行测试、服务、HTTP、provider 或真实前向，也未读取运行数据库、凭据或 SEALED。没有把本结论作为统计资格、真实渠道送达或票据全部完成的证明。后续纯证据文档提交不在此产品快照内。

## Spec


只读静态审阅：`ca912b8194a56d9a3c32cc07695d5e714f7f99f5...80fbcc23c8440e7210221144c020d315b9784773`。未执行测试、HTTP、Provider、模型或数据库操作；以下触发为源码推导。

1. **P2｜当前资格呈现错误。** PRD:477：“当前能力状态及原因”；503：“当前允许什么”。`capabilities.py:359,381–391` 可返回 GRANTED/METHOD_GRANTED 与非空动作，却始终保留 `formal_judgment=DISABLED`；`app.py:1228`、`today.tsx:18`、`settings.tsx:30`继续固定“未启用”。有效独立风险/利润资格与页面结论矛盾。由当前资格事实派生说明，分别表达正式利润、独立风险、METHOD、暂停/恢复锁；不得将 METHOD 写成正式启用。

2. **P2｜风险成交报告失败。** spec:257：“分别报告平台策略结果、实际用户结果及执行偏差…数量、费用”。`actions.py:246–254`的 REDUCE/EXIT 没有 `fees_yuan`；`reports.py:88–94`对关联成交直接索引该键。风险意向关联 SELL 后，报告及 JSON/文字导出会 KeyError。公共风险成交链补红绿验收；无冻结费用须保留未知，不能填零或借 BUY 费用政策。

3. **P2｜准备操作幂等合同不成立。** spec:349：“同幂等键同内容返回原业务结果”；26 AC:17：“幂等重试返回原结果”。`intents.py:69–88`先检查当前动作/账户，才查询幂等键；成功后权限变化、成交或到期，原请求重试返回409。且回读可变意向值，声明后不是原回执。`test_intents.py:32`错误地期待409。先校验不可变命令回执；旧回执查询不创建/恢复资格或覆盖当前待结果/部分成交事实；不同内容409，新键旧动作仍409。

4. **P2｜日常设置增加技术配置负担。** PRD:491：“设置只保留事实、资金授权、通知时间、关注名单、数据连接与恢复备份”；475：“模型诊断和维护功能默认折叠”。`settings.tsx:30`直接展开 `CapabilityPanel`，其:22要求用户填写材料与审阅编号。将维护核验折叠并从已有材料选择，保留受控服务检查。

5. **已披露 partial｜政策和生产输入尚未闭合。** PRD:445：“评估持有/退出与新增机会”；469：“已有持仓如何迁移需有版本化说明和事件”。`actions.py:283–355`仅支持冻结 BUY，ADD/HOLD/判断 WAIT/反转/冷却/迁移未注册；:155,162无条件缺费用，:170,175把有效期置为已到的 required 截止，:83阻止发布。安全拒绝正确，不能将 METHOD 通过称为这些工程要求完成；后续须冻结政策和真实 producer 契约，不创造金融规则。

真实 G7/自然时钟/源权威、正向 LOSS 恢复及32–34不足仍为披露边界；28实际外发由用户延期，30/31仍partial，不据此认定新代码缺陷或授予资格。

Standards: 0 findings; no actionable issue. Spec: 4 P2 behavior issues and 1 disclosed partial; worst severity within Spec is P2. Axes remain separate. One implementer owns all concrete fixes; policy/production-source limitations remain explicit rather than fabricated.