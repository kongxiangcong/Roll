# 实际成交与费用追加 · 02

成交复用 [账户接口](account-contract.md) 的 `POST /api/account/drafts` / `confirm`、同一 SQLite 事务、版本、事件、审计和回执。事件命名空间 ACTUAL；当前没有正式动作可关联，`action_association.status=UNKNOWN`。逆建议/超量标记是用户报告的行为事实，不是系统对尚不存在的动作的判断。实际成交不检查交易权限或资金授权来拒收已发生事实，也不签发正式资格；权限原确认时点和版本保持不变。

## 命令与身份

`FILL.payload` 必须含 `effective_at,source,instrument,direction,quantity,price,record_id,fill_id,order_id,behavior_context,fee,broker_available_after`。方向 BUY/SELL；证券、时间、来源沿用账户校验。数量和原价格为正十进制字符串，最多18位整数/8位小数；保存原精度。金额只接受最多18位整数/2位小数的字符串，未知用 null。总价先以 Decimal 80位乘法计算，再按 ROUND_HALF_UP 舍入到分；不使用浮点财务运算。

`record_id` 是本次手工材料的唯一记录标识。券商可靠分笔 `fill_id`、委托 `order_id` 可为 null；一委托多笔及同价同量不同分笔分别保留。已有 record_id 或可靠 fill_id 的相同经济内容返回409 `FILL_ALREADY_RECORDED` 和原回执；变更内容隔离，不覆盖。没有可靠分笔标识时保留来源与歧义，绝不按价量自动合并；用户核对每次手工记录是否为独立成交。

`behavior_context` 可为 NO_RECOMMENDATION、CONTRARY、EXCESS_QUANTITY、OFFLINE、UNSPECIFIED。草稿原输入保留；方向/金额/数量等矛盾或格式错误返回已保存的 QUARANTINED 草稿，issues说明原因，不能确认。`GET /api/account/quarantined-drafts` 查询原材料；当前账户/今天显示 RECONCILE_REQUIRED，正式现金/持仓/版本不变。03/05处理后续核对和更正，本票不自动消除隔离记录。

## 费用、成本和现金

`fee={status,amount,reserve_amount,basis}`。KNOWN需要 amount（允许明确0）及依据，reserve_amount=null；PROVISIONAL需要 amount=null、正数 reserve_amount及保守估计依据。未知费用不会变成0。买入现金减少总价＋费用/预留，卖出现金增加总价－费用/预留。未结费用列表 `fees_pending` 和 `cash_balance_basis=PROVISIONAL_FEES` / `net_result_state=FEE_PENDING` 保持待核。

新买入生成成本批次；卖出按事实时间 FIFO 分配，使用累计售出数量对应成本的分舍入和末笔余数，数量与成本守恒。基线参考成本不是实际取得成本；基线批次成本依据 REFERENCE/UNKNOWN，不推定历史费用或收益。包含未知历史成本的卖出可以记录，取得成本/已实现收益返回 null / COST_UNKNOWN。

`FEE_ADJUSTMENT.payload={effective_at,source,target_record_id,actual_fee_amount,basis}` 指向已确认手工记录，追加费用事件。现金扣除实际费用相对上次费用/预留的差额；买入批次原成本/余成本及已售出成本按同一累计方法重算，卖出费用调整实现收益。原 BUY_FILL/SELL_FILL 的费用字段永久保留；`fee_resolutions` 指向最新实际费用和依据。所有调整同样受版本与幂等约束。

100000.00买300股×10.00、费用5.00 →现金96995.00、取得成本3005.00；卖100股×12.00、费用5.00 →现金98190.00、余200股成本2003.33、实现收益193.33；卖余200股同价同费 →现金100585.00、收益585.00。先预留10.00再部分卖出，随后追加实际5.00得到同样现金/余成本/收益；历史原预留仍可查询。

取得成本包含买入费用，`realized_gain` 使用该费用后成本，不能直接充当 [资金损失公式](funding-contract.md) 的费用前 realized_pnl/unrealized_pnl 后再重复扣 fees。09/25必须从实际总价、数量、费用事件和授权基线构造费用前事实；当前资金状态仍 PENDING_FACTS、技术资格 UNGRANTED。

## 时点、重放与迁移

`broker_available_after` 只表示用户核对的该次成交时点券商可用快照。缺少它时当前 broker_available=null；保守可用只从最近确认金额推算买入占用，卖出不猜当前券商可用。冻结/可取字段保留原快照并公开其截至时点。费用调整同样使当前券商可用未知；推算余额不能冒充券商快照。

`GET /api/account/replay` 通过已确认事件及同一财务投影只读重建账户，验证现金、批次、费用和收益与不可变快照一致；按实际确认记录顺序重放，05继续负责更正链与完整历史语义。effective_at来自用户事实，recorded_at/confirmed_at来自系统真实记录；确认成交不会重确认账户权限。

全局 schema 从1升为2，仅给 account_drafts 添加 status/ issues；在 BEGIN IMMEDIATE 中检查版本并迁移，bootstrap不会把2重置成1。见 [迁移2](../backend/migrations/002-draft-status.md)。验收启动真实17ca07d旧服务保存基线/回执/未确认草稿，再由新服务升级；旧回执、历史快照和可确认草稿完整保留。

## 验收与后续组合入口

[02证据](../.scratch/roll-p0/evidence/02/acceptance.md) 区分应用、真实进程恢复、浏览器与性能。`scripts/account_confirmation_performance.py` 的 `measure_confirmations(client,samples=100,warmup=10)` 是08/13的集成入口；仅可对 `ROLL_ENV=test` 的隔离服务使用。对应票应在真实外部获取/模型等待或超时同时调用，保存任务生命周期和同一确认采样，验证P95≤2秒。当前没有这些实际任务，组合验收 pending，不据此声称外部超时已不阻塞。
