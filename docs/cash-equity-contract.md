# 现金、待结算与股份变动 · 04

04扩展 [账户唯一确认入口](account-contract.md) 的 prepare/confirm，不建立第二套账户写入。草稿不改变事实；确认在同一 SQLite 事务保存事件、现金、持仓/成本、版本、审计和可靠回执。金额只接受十进制字符串（18位整数、2位小数），数量8位小数；未知值不转成0，矛盾/未知个人金额、数量、实际时间的原命令保留为 QUARANTINED，可通过原草稿及公开待核查询找回。旧版本/幂等/真实崩溃语义沿用01/02。

## 命令字段

所有以下 payload都必须包含 `effective_at,source,record_id,basis`，实际时间是带时区非未来ISO8601，basis由用户填实际账户依据。record_id标识个人材料/流水，重复标识隔离且不再入账；同一原确认命令/幂等键返回原回执。

| kind | 额外必需字段 | 语义 |
|---|---|---|
| CASH_IN / CASH_OUT | amount,instrument,broker_available_after | 已发生外部转入/转出；instrument可null |
| DIVIDEND / INTEREST | amount,instrument,broker_available_after | 已实际到账投资收入；利息不算外部投入 |
| TAX / FEE | amount,instrument,broker_available_after | 独立实际现金税费；不是02成交费用的重复输入 |
| PENDING_ITEM | item_type,amount,instrument | item_type为DIVIDEND/INTEREST/TAX/FEE；确认已知个人应收/应付，现金/可用/持仓不变 |
| SETTLEMENT | target_record_id,amount,broker_available_after | 关联原待结算实际部分/全部到账或扣款；金额不能超过剩余 |
| CASH_CORRECTION | target_record_id,corrected_amount,broker_available_after | 仅更正04已确认现金、待结算或结算金额；填写更正后的原总额（可明确0），追加差额，不能更正更正记录自身 |
| SHARE_CHANGE | instrument,new_quantity | 用户核对免费送转/拆并后正数总量，不根据公告猜个人数量 |
| RIGHTS_SUBSCRIPTION | instrument,quantity,amount,fee_amount,broker_available_after | 实际配股新增股份与实际总支付；fee_amount可null，未知分拆不转0 |

实际现金流水/结算金额须正数；broker_available_after可null。PENDING_ITEM与SHARE_CHANGE不确认新的券商可用快照；冻结/可取/可用保留原字段时点。实际现金变化无新券商快照时broker_available=null，保守可用也不冒充当前券商余额。更正PENDING_ITEM时broker_available_after必须null，不改变现金/可用。

## 查询与不重计

`GET /api/account` 和不可变版本返回 `cash_records`、`cash_resolutions`、`pending_items`、`share_records`；事件/审计/回执仍由现有查询返回。原cash_records金额永久保留，CASH_CORRECTION记录 target、previous_amount、previous_correction_id、现金差额，cash_resolutions引用最新有效金额。待结算项保留原amount、resolved_amount、settled_amount、outstanding_amount、settlement_ids、状态OPEN/PARTIAL/SETTLED/CANCELLED、依据与原confirmed_at。不同确认时点可查对应历史快照；全部事件有系统recorded_at和用户effective_at。

分类字段 `flow_category=EXTERNAL_IN/EXTERNAL_OUT/INVESTMENT_INCOME/INVESTMENT_EXPENSE`。`external_cash_in/out` 是基线后已确认外部转入/出累计，不是收益。`investment_income/expenses` 是本票现金收入/税费累计（不含02成交费）。`pending_income/expenses` 只合计有效未结余额；实际到账/扣款增加实际累计且等额减少未结余额。09用“实际收入变化＋应收余额变化”与“实际费用变化＋应付余额变化”避免两次记收入/费用；金额未知的隔离草稿不能进NAV。09提供具体估值/绩效，05用这些原事实对账，本票无百分比收益或正式动作。

独立样例：100000.00＋利息20.00＋存款5000.00→现金105020.00、收入20.00、外入5000.00；存款不会提升收入。确认分红应收100.00→现金100000.00/应收100.00/实际收入0.00；到账40.00→现金100040.00/应收60.00/实际收入40.00；剩余60.00到账后现金100100.00/应收0.00/收入100.00。确认税应付30.00后扣10.00→现金99990.00/实际费10.00/应付20.00；追加总额更正25.00→应付15.00/现金不变；将原扣款更正8.00→现金99992.00/实际费8.00/应付17.00；余17.00扣款→现金99975.00/实际费25.00/应付0.00。原30.00/10.00仍可查。

## 股份与成本

送转/拆并等数量变动以明确个人新总量确认。Decimal80位计算先于乘法/分摊；按现存活跃批次数量比例分配新数量，前批舍入8位，最后一批承接余数，总数量精确等于用户输入。每个剩余成本按分原样转入子批次，不计现金或收益，不改写原买入/已卖批次；保留parent_lot_id/transfer_child_id及转移数量/成本。未知/参考历史成本继续UNKNOWN，不能通过送转变成已知取得成本。可卖数量及当前券商单位参考成本变为未知；原单位参考成本保留在此前版本/事件及股份变动reference_cost_before中，不能冒充变动后的新券商参考价。

后补原买入费沿实际转移关系递归分配已售成本和剩余成本，各代使用原数量的累计分舍入/余数；不会把移交到子批次的成本当作已经卖出。样例：买300×10预留费10→现金96990/成本3010；卖100×12费5→98185/余200成本2006.67；送转后余300股成本2006.67；再卖100×8费5；后补买费实际5→现金98985/余200股成本1335.55/已实现收益320.55。原买入数量300及费用暂估记录保持原值。多批八位数量/成本、最高输入精度及事件重放另有公开API验证。

实际配股使用RIGHTS_SUBSCRIPTION。quantity是实际新增数量，amount是已实际支付总额（包含已付费用），新PAID_RIGHTS批次的取得总成本与现金扣款都等于amount，flow_category=INVESTMENT_ACQUISITION；不是外部提现或投资收入。已有买入/已售成本不覆盖；初始未知成本继续未知。ACTUAL事件类型SHARE_CHANGE的payload.kind区分RIGHTS_SUBSCRIPTION与免费数量调整，重放按payload.kind恢复。

fee_amount是总支付内费用分拆，明确已知零必须填0；未知时null，gross_subscription_amount=null、rights_fee_breakdown_pending及FEE_BREAKDOWN_PENDING公开显示费用前损益未知，但实际总支付及取得总成本仍可确认。后补复用FEE_ADJUSTMENT指向配股record_id，actual_fee_amount不得超过总支付，追加fee_resolutions的gross_subscription_amount=amount-fee，不再次扣款、增成本或重复投资支出；原null保留在原记录/版本。09/10应通过该分拆及PAID_RIGHTS批次数量/转移关系取得费用前本金与费用；不能将fee-inclusive总成本再扣一次该费用，未知分拆不能冒充gross已知。04 investment_expenses不含成交和配股取得总成本内费用，后续绩效统一消费其原费用字段。

实测：买300股总成本3005元后实际配股新增100股、总支付500、分拆未知→现金96495、400股、总成本3505；补分拆费用5→现金/数量/总成本不变，本金495，原费用null保留。ROLL-CSV-2同批实际新增100.00000001股、总支付500.01＋费用分拆5.01→只扣500.01，本金495；v1原头与允许kind冻结。

## 外部线索与时间

`POST /api/account/equity-hints` 只接受 `{source,declared_at,instrument,content}`（后两时点/证券可null），保存 hint_id、原宣告内容/日期精度、系统真实learned_at、actual_effective_at=null、PENDING_USER_CONFIRMATION；`GET`同路径查询。材料进入今天待核，不改变账户版本、现金、数量或可用。宣告日期不会被补成开盘前时分；用户之后仍须独立确认实际个人事实。本票不抓真实网页、不自动匹配/消除线索；07/14接实际网页证据后复验同一边界，05负责后续核对。

组件初始迁移只幂等创建 `account_equity_hints`，不改变全局user_version2或旧账户事实，见 [迁移说明](../backend/migrations/004-equity-hints.md)。CSV版本扩展与实际整批原子确认由03/04联合验收，保持已发布v1解析；不把外部CSV或网页作为确认授权。[04证据](../.scratch/roll-p0/evidence/04/acceptance.md) 明确实际覆盖与后续边界。
