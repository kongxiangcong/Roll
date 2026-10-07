# 账户应用接口 · 切片 01/02

HTTP 入口调用 `roll.accounts.ledger.Ledger` 的同一草稿/确认用例。后续成交和资金事件扩展 `prepare(command, account)` 的事件类型/投影，复用 `confirm` 的事务、幂等、版本、事件、审计和回执；不添加第二套写入。当前无正式动作，因此未预造动作表或失效逻辑。26/27 须把实际动作失效接到同一 SQLite 事务。

## 字段与精度

所有金额和数量在 HTTP JSON 与 SQLite JSON 中均为十进制**字符串**；未知用 `null`。浮点 JSON 数值、负数、非有限值、空串均拒绝，不能把缺失转成零。草稿保留原始输入字符串。

| 字段 | 输入/输出约定 |
| --- | --- |
| `cash_balance` | 必填非负元金额，整数部分最多 18 位、小数最多 2 位；输出固定两位 |
| `broker_available` / `broker_frozen` / `withdrawable` | 相互独立，同样金额精度，允许未知，不从账面现金推定 |
| `instrument` | `SSE:600000`、`SZSE:000001`、`BSE:六位代码`；不因存在持仓推定规则已适配 |
| `quantity` | 必填正数，整数部分最多 18 位、小数最多 8 位，保留精确数量；证券执行规则由 06 负责 |
| `sellable_quantity` | 同数量精度，0 是已知不可卖，null 是未知；不能超过总量 |
| `reference_cost` | 元/股，最多 8 位小数，允许未知，不伪造税费或取得历史 |
| `effective_at` | 用户确认的事实截至时点，带时区 ISO 8601，不接受未来时点 |
| `source` | 用户确认的来源/依据，必填 |
| `permission_profile` | `market` + `board` 唯一范围；状态 `OPEN`、`NOT_OPEN`、`UNKNOWN`；必填 `basis`；未列范围仍未知 |

基线金额已在元的分边界，因此多余精度拒绝而非隐式舍入。价格/数量原精度最多八位保留；当前基线无计费或分摊计算，后续事件负责其明确计算边界。Python Decimal 解析与字符串持久化不使用二进制浮点累计。

初始持仓事件类型 `INITIAL_POSITION`；`buy_time`、`historical_fees`、`historical_return` 保持 null。事件保留 `effective_at` 和系统实际 `recorded_at`、`source`、`account_version`、`namespace=ACTUAL`。确认时点和权限版本由系统填入，草稿不生效。首个基线确认后不能重新覆盖账户；权限变化使用独立草稿，旧快照永久可查。

## HTTP

| 路径 | 行为 |
| --- | --- |
| `GET /api/health` | 本机启动检查 |
| `GET /api/account` | 当前正式投影；未建立时 version 0 与未知资金 |
| `GET /api/account/versions/{version}` | 不可变已确认快照，包括该版本权限 |
| `POST /api/account/drafts` | `{kind,expected_account_version,payload}`；201 返回草稿 ID、字段 before/after、原命令、创建时点 |
| `GET /api/account/drafts/{id}` | 找回原草稿，未确认草稿仍不入账 |
| `POST /api/account/confirm` | `{draft_id,idempotency_key}`；返回可靠回执 |
| `GET /api/account/receipts/{id}` | 查询相同回执 |
| `GET /api/account/events` | 查询已确认账户事实，非模型成交 |
| `GET /api/account/audit` | 版本/回执/来源和实际记录时点 |
| `GET /api/today` | 账户、客观待核项、`formal_judgment=DISABLED` |

`BASELINE.payload` 必须含 `effective_at,source,cash_balance,broker_available,broker_frozen,withdrawable,positions,permission_profile`。`positions` 每项必须含 `instrument,quantity,sellable_quantity,reference_cost`。`PERMISSIONS.payload` 必须含 `effective_at,source,permission_profile`。权限项输入必须含 `market,board,status,basis`，输出补 `effective_at,confirmed_at,account_version`。未知字段拒绝以防误拼字段被丢弃。

## 确认与恢复

SQLite 为唯一正式状态；每次确认使用 `BEGIN IMMEDIATE`，事件、快照、版本、审计和幂等回执同一事务，`synchronous=FULL` + WAL，提交完成才返回成功。草稿不是正式事实。

确认先检查幂等记录：同键且命令内容一致返回原回执，即使随后账户版本已变化。同键内容不同返回 409 `IDEMPOTENCY_CONTENT_CONFLICT`。其他旧版本返回 409 `ACCOUNT_VERSION_CONFLICT`，包含 expected/current 版本及自旧版本以来的 before/after；全部写入回滚，不覆盖或部分入账。并发同键只生成一次结果。浏览器保留待确认草稿与键到 sessionStorage，丢失响应或刷新后继续查询/重试同一命令；审计历史也能找回回执。

已知输入错误为 422，不存在的版本/草稿/回执为 404。`ROLL_ENV=test` 且设置 `ROLL_TEST_CRASH_POINT=before_commit|after_commit` 时允许验收子进程在事务边界 `os._exit(86)`；该控制不是 HTTP 参数，生产默认关闭。回执后崩溃由测试父进程执行操作系统 kill。恢复后通过公开查询及同键重试证明未提交内容不残留、已提交内容不丢失不重复。

首版 schema 由当前实际表 bootstrap 并记录 `user_version=1`；02 的兼容迁移升到2，后续新增 schema 由对应票带迁移，不在 01 预建全部对象表。实际成交/费用命令、隔离草稿、只读重放、快照时点与迁移证据见 [成交接口](fill-contract.md)。
