# 资金授权与损失口径 · 10

本契约由 Roll 提供计算方法；用户只填写用途、范围和金额，不选择统计参数。资金、技术资格和运行健康独立记录，资金确认不签发能力。当前技术资格 UNGRANTED，正式判断与正式概率写入均返回 403。

## 确认与历史

`GET /api/funding` 返回当前资金版本；`GET /api/funding/versions/{version}` 查询不可变历史。`POST /api/funding/confirm` 需要 `expected_version,idempotency_key,authorization`。授权含 `scope_kind,scope_id,purpose,capital_amount,total_exposure,single_exposure,cash_reserve,loss_threshold,effective_at,basis,enabled,pause`。所有金额是非负十进制字符串，最多 18 位整数与两位小数，固定两位输出，拒绝隐式舍入；金额及阈值为正，单票不大于总暴露，总暴露加保留不大于金额，阈值不大于金额。`enabled=false` 撤回当前资金用途，`pause=true` 锁存资金暂停；扩大金额或再次 enabled 不解除暂停。

首个授权绑定当前已确认账户版本作为基线引用和首次生效时点为损失起点，后续版本不能更换 `scope_kind,scope_id` 或改写起点/基线。ACCOUNT 代表整个真实账户；TRIAL_ACTUAL 代表用户明确界定、由未来实际事实提供方独立归属的真实试验资金范围，不是 SHADOW。金额本身不证明账户具备该金额或可用现金；25 将取当前券商可用、授权及技术范围的交集。收窄/撤回后新查询立即看到新限制，旧版本仍可查；真实动作原子失效由 25/27 接入。

SQLite `BEGIN IMMEDIATE`/FULL/WAL 将版本、确认依据和带 receipt_id 的可靠确认结果一起保存。幂等先于版本检查；同键同内容返回原结果，同键不同内容和旧版本均 409，无部分确认。确认内容含版本、依据、confirmed_at 和 effective_at，即为不可变资金确认审计。组件迁移标记 `schema_migrations:10-funding-v1`；不改变账户全局 user_version。浏览器在 sessionStorage 保存原命令与原时点/幂等键，网络或服务端不明失败可重试相同命令；确定的输入/版本失败可更正后再确认。

## 冻结公式与事实接口

版本：`cashflow-adjusted-loss-v1`。共同纯函数 `roll.decisions.funding.evaluate_loss(authorization, LossFacts, previous_result)` 返回损失、历史峰值损失、触发状态、剩余额度、输入/授权版本和限制原因。09 提供受控的实际估值与现金流；25/27 在同一受控写入链保存 ACTUAL 损失历史、暂停与动作失效。20 的影子结果保存在独立范围，不能向真实授权注入；这个函数不签发资格、不写账户或动作。

所有分项是从同一首次授权起点、同一基线净资产开始的累计变化，限定同一 scope_kind/scope_id、baseline_account_version 和 origin_at。`facts_version` 引用提供方已确认版本，`as_of` 不早于 origin，不倒退；时点统一为 UTC，原账户版本永久可查询。资金扩大不是现金流，不是新计算基线。

- `baseline_assets`/`net_assets` 为范围内现金＋按规定估值的持仓＋已确认待结算应收－应付；冻结款已经在现金内，不能再扣。未到账应收不进入券商可用。基线前收益不参与此损失口径，缺基线估值不能补成零。
- `external_in`/`external_out` 是期间外部投入/取出，非负；利息、分红、费用或内部资产买卖都不在这两个字段。
- `realized_pnl` 和 `unrealized_pnl` 必须是**费用前**价格损益的期间变化。不能直接传入以含买入费成本计算出的费用后持仓损益后又扣 fees。基线持仓从起点已估值市值开始计算变化，不推定其未知取得历史。
- `income` 为期间已结算投资收入（包括利息/分红），`fees` 为期间净确认费用/税费；未知费用用 null 而不是零。更正可以有符号净变化。
- `pending_income_delta`/`pending_expense_delta` 是起点以来已确认待结算投资收入/费用的余额变化，可正可负；不是全部本金应收应付。收入实际结算时 income 上升且 pending_income_delta 等额下降，只算一次。费用同理。净资产同时含应收/应付，偿付转换为现金也不再减一次净资产。

```text
P = realized_pnl + unrealized_pnl + income - fees
    + pending_income_delta - pending_expense_delta
P 必须等于 net_assets - baseline_assets - external_in + external_out
L = max(0, -P)
历史峰值损失 H = max(之前有效 H, L)
剩余损失额度 = max(0, 当前授权阈值 - H)
触发 = 之前已触发 OR H >= 当前阈值
```

使用 Decimal 50 位运算及元的分边界，无二进制浮点/隐式舍入。所有输入允许 null 表示未知；陈旧/缺失估值、必需分项缺失或两种损益口径不守恒，返回 RESTRICTED，P/L/剩余额度未知，保留之前峰值和触发记录，不做正常通过外观。基线曾已知后不能被换值，后来缺失也不清除已知基线或暂停。

阈值恰好达到即暂停；跨日、重启、价格反弹、金额或阈值扩大均不清除历史 H 或已触发状态。缩小阈值按旧 H 检查。恢复必须由后续 27 根据暂停原因、当前确认事实/估值、资格及授权检查进行显式受控恢复，仍保留旧记录；10 没有通用自动恢复或清零端点。这是使用条件，不能保证实际最大亏损。

## 固定手工样例与证据边界

| 输入（其余未列分项为已知 0） | 独立可核对预期 |
|---|---|
| 起点100000，净资产97000，外入2000/外出1000，费用前实现-2000、未实现-2100、利息收入200、费用100，阈值5000 | P=-4000；损失4000，剩余1000 |
| 同口径未实现-3100/净资产96000 | P=-5000；等于阈值触发，剩余0 |
| 净资产95999.99/未实现-3100.01 | P=-5000.01；超过阈值触发 |
| 净资产96000.01/未实现-3099.99 | P=-4999.99；剩余0.01 |
| 第一例另有待收收入100、待付费用50/净资产97050 | P=-3950，剩余1050 |
| 第一例利息income300且 pending_income_delta=-100/净资产97000 | 结算只计一次，P仍-4000 |
| 起点100000；买300股×10，买费5，随后标价10；现金96995＋股票3000=净资产99995；费用前实现/未实现0，fees5 | P=-5，损失5，剩余4995。02含费用成本3005不能作为这里的费用前价格损益成本 |
| 起点999999999999999999.99，净资产999999999999999999.98，费用前实现-0.01，阈值3000 | P=-0.01，剩余2999.99，分精度准确 |
| 等于5000触发后下一日净资产102000、P=1000，金额扩大200000/阈值10000 | 当前损失0、H仍5000，已触发暂停仍在 |
| 先损失4000后反弹，当前阈值缩为3000 | H仍4000，立即触发、剩余0 |

测试专用 `/api/testing/funding-loss-samples` 只在 `ROLL_ENV=test` 时注册，保存 `funding_method_samples` 的隔离方法样例；输出严格是 ACCOUNT_CONDITIONAL，purpose=METHOD_VALIDATION、input_authority=UNTRUSTED_SAMPLE。生产不注册端点，也不创建该表。样例记录可证明公式/持久化方法，不可作为正式账户事实、收益或资金门禁依据。当前生产资金 loss_status=PENDING_FACTS，剩余额度 null；设置页无样例净资产/P&L输入。09/20/25/27 的实际联验尚待实施。
