# Spec 修复复查

固定原产品 `80fbcc23c8440e7210221144c020d315b9784773` → 修复产品 `bbb84a57f624dec9351b32373fd9d10e1447eed3`（代码 e75c14e）。仅受影响 hunk 的只读静态复查，未运行测试、HTTP、Provider 或数据库；不把 owner 测试视为独立验收，不产生 actual ReviewRecord。

1. **原 P2 当前资格呈现：静态 closed。** PRD:477“当前能力状态及原因”、503“当前允许什么”。`capabilities.py:25–61,427–430`从已检查的 grant_statuses 派生当前能力，实际风险/利润/双资格与 METHOD 分列；恢复锁剔除能力。`app.py:1232–1235`及今天/设置采用宿主投影，恒定未启用已移除。该投影不授予资格或保证有可执行卡。

2. **原 P2 风险成交报告：静态 closed。** spec:257“数量、费用与未执行原因”。`reports.py:92–96`用可选费用、`UNKNOWN`与`PROPOSAL_FEE_UNKNOWN`保存缺口，REDUCE/EXIT 的已关联 SELL 不再索引不存在字段，不填零或借 BUY 费用。

3. **原 P2 prepare 幂等：held，一项并发残差。** spec:349“同幂等键同内容返回原业务结果”；26 AC:17“幂等重试返回原结果”。新表与事务内同时写入的不可变回执、内容冲突、新键当前检查及真正 legacy 缺回执拒绝均正确；旧回执不覆盖 pending/partial 当前事实。但 `intents.py:78–79`在 autocommit 连接调用两次查询:65、69（`Ledger.connection`为`isolation_level=None`）。A首次查回执为空；B同键提交新意向和回执；A第二查询看见新意向，:72误报`LEGACY_PREPARE_RECEIPT_UNAVAILABLE`。尚未闭合同键并发重试。让两次查询共享显式读快照或单语句，或仅在 writer 事务判 legacy；保留不同内容409与真正 legacy拒绝。此为静态时序推导，待独立受控红绿验收。

4. **原 P2 日常设置负担：静态 closed。** PRD:475“模型诊断和维护功能默认折叠”、491“设置只保留…”。`settings.tsx:32`将维护/核验置于无 open 的 details；`capability-panel.tsx:30–33`由已保存材料及关联 Codex 审阅选择替代 UUID 输入，受控资格检查保留。

结论：3 项静态 closed，1 项 held；第5政策/生产 producer要求仍partial，不补金融规则。实际资格、自然时钟、来源权威与延期外发边界均未升级。
