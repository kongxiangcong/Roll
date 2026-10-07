# 决定性事实独立核验

本票核验已经归档的决定性字段，保存原值、原始依据和口径比较。入口是历史记录的关键复盘，以及某条已发布观察的“重点复盘当前观察”。普通观察与日审计不会自动创建核验；结果不授模型资格、不确认成交或到账、不写账户。

## 公共接口

`POST /api/data/verifications` 接受以下命令，返回201。`trigger` 只接受 `USER_SELECTED`、`MATERIAL_DOUBT`、`CRITICAL_CONFLICT`；理由非空；最多10个唯一事实键，每项最多6个归档引用。

```json
{"trigger":"USER_SELECTED","reason":"收盘价影响重大盈亏归因","facts":[{"fact_id":"decisive-close","field":"close","references":[{"snapshot_id":"已有快照UUID","fact_index":0}]}],"knowledge_cutoff":"2026-10-08T05:00:00+08:00"}
```

字段限于已登记的价格、日期、金额、股数和公司事项具体标量；身份、资格或账户元数据不能成为核验字段。调用方不能提交 `origin_id`、独立性结论或任意原文。引用的原件及公告文件均核SHA。`GET /api/data/verifications` 返回最近100项；`GET /api/data/verifications/{id}` 返回当前依赖状态；`POST /api/data/verifications/{id}/replay` 用原07 run的SQLite/原件/Parquet校核原输入，网络调用0。

14不新增联网采集器；需补查的事实继续走07/08的有限取数契约。每次核验冻结实际证据版本、字段原字符串、源URL/ID、可得时点、单位、语义上下文、独立性依据、逐对比較、缺口、适配器源码SHA及Python/SQLite版本。

## 独立性与比较

来源域名、接口、工具、Agent或模型名字不证明独立原始生产。当前真实供应商报价没有可核的独立原始数据链，因此记录 `INDEPENDENCE_UNPROVEN`。带公告原文文件和 `art_code` 的同一发行人公告按“发行人＋公告”记录单一原始依据，转载页面或元数据不增加依据。单一权威原文可以作单源事实，不能签多源一致。

只有明确隔离的 `METHOD_CASE` 归档允许从注入外部原件的 `_roll14_original_provenance` 读取固定原始记录、生产者及生成依据，以验证一致/重复/冲突机制。记录、页面、重启和归档都保持METHOD标记；生产真实材料不能由该JSON声明晋升独立。有效数量同时受原始记录数与生产者数限制，同源额外重复不计票，也不妨碍已有两条真正独立的固定依据。未建设来源认证平台；现实正向独立生产证据尚没有样例。

逐对比较对象、组、交易日/报告期/权益事件、上游时点及精度、币种、适用成交单位、RAW/复权和复权版本。带时区时间按同一瞬间比较；数字按Decimal精确比较，原字符串保留。单位依据不明、字段缺失或源自身 `errors` 基本校验失败都构成不足。不同口径的数值不同不直接判冲突。可比字段的原值不一致保留各方原值，标 `CONFLICT`；其余缺口标 `INSUFFICIENT`；至少两条独立可比一致依据且无缺口才标 `VERIFIED`。不平均、不投票、不挑值；归因暂缓按字段，其他已核字段仍可继续。

知识截止须带时区、不晚于现在；留空按当前实际取得材料。原 `available_at` 晚于该截止构成不足，后取证据不能成为过去已知输入。时点未知或现修历史价格不因此成为PIT事实。

## 版本、复用与修订

记录不可变，稳定输入指纹含适配器源码SHA、字段/单位/上下文、原件/公告SHA、独立性依据与知识约束。同证据版本及有效依赖复用原结果，保存新的关联UUID和 `reuse_of`，不重新联网、不刷新原可得时点。

08来源修订在已有短SQLite发布事务中新增 `VERIFY_REVIEW_EVIDENCE` 失效记录；14同时依赖原字节，所以仅原始链/字节变化而规范数值相同也使原核验失效。已知被替代原件重新提交为新核验UUID仍显示失效；旧08修订按已存前后resolution重建依赖，不回写历史。查询返回原 `result` 与动态 `current_result`，失效后当前为不足；原值/原结果和零联网复放保留。损坏原件查询/复放409，列表标 `UNREADABLE`，不阻断无关决定性字段。

## 15观察与审计关联

先用15的 `POST /api/reviews/tasks/{task_id}/verification-request` 保存明确疑点。15要求原观察的数据版本、对象、事件截止和知识截止；不能混入后知材料。再显式 `POST /api/reviews/verification-requests/{request_id}/verify` 消费已冻命令，返回实际14核验，不接受替代字段/截止。

一个短 `BEGIN IMMEDIATE` 事务同时保存核验、请求 `CONSUMED/verification_id` 及原审计 `verification_links`。并发、重试、崩溃恢复只得到同一核验ID；请求再次提交保留关联。原观察result不变。`GET /api/reviews/verification-requests/{id}` 附当前核验依赖视图，来源修订不把旧结果伪装当前有效。生产页面从原观察显式进入，只有原版本可选；普通查看不会创建请求或核验。

独立核验四条事实返回路由和新消费/请求查询路由均经17 `research.market_input_exposed` 在实际payload交付边界审计封存日线输入；这是输入暴露，不是确认性结果检验，不改变协议资格。

提交前、提交后与回执后原生进程退出边界均已验证；联合请求/审计还验证提交前后全部原子恢复。具体真实材料、METHOD和Chrome证据见[14验收](../.scratch/roll-p0/evidence/14/acceptance.md)。
