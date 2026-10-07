# 账户原价估值与绩效 · 09

09只发布账户事实版本，不签发动作、技术资格、损失余额或试用额度。资金原授权仍由[10](funding-contract.md)管理，25/27接入真实当前事实与动作后联验。当前真实试用逐事件归属未建立，TRIAL_ACTUAL请求返回422；完整ACCOUNT资产查询仍独立可用，不能用全账户代替试用子集。

## 公开入口与版本

`POST /api/account/valuations` 接收 `baseline_account_version,origin_at,as_of,known_by?` 与 `scope_kind=ACCOUNT,scope_id=account`。时间必须带时区且不在未来。仅从已确认版本/实际事件和07归档QUOTE读取，不接受调用者提供报价、资产或损益金额。`known_by`缺省实际当前时间，实际发生截止与系统知识截止分开。基线前历史不完整，没有期初依据时不填零、不使用券商参考成本推算历史收益。

`GET /api/account/valuation-basis` 提供实际默认起点。已确认ACCOUNT授权对应的请求范围沿其固定基线/首次origin，重设返回409；普通完整账户查询与另一TRIAL授权分开，`loss_binding=false`，`funding_scope`仅披露原授权，不改它。普通ACCOUNT事实不能作为范围不匹配授权的输入，10的严格范围校验保持有效。

期初**数量**取不可改的账户基线版本，期初**价格知识**取 `min(origin_at,known_by)` 前已取得且原报价时点不晚于origin的归档；不误绑账户版本的确认时间。账户先确认、随后取得报价、再确认资金起点仍能建立有依据的期初资产。原origin后才取得的旧报价可用于显式回溯的当前估值，不能补造原origin已知价格。首次完整知识截止下发布的期初报价锚点与估值同事务冻结；后续不能靠新增材料改写它。已知基线不因新增资金授权重置，基线未知仍未知。

`GET /api/account/valuations`、`/current`、`/{valuation_id}` 查询已保存版本；current是最新**发布**的版本，不表示自动更新的账户或报价。`POST /{valuation_id}/replay` 使用版本保存的基线、实际事件、双时间截止及原QUOTE引用计算，核验07原件/Parquet哈希，不联网；结构化不一致或原件损坏返回409。新事件或更正不修改旧版本。后续使用者必须比较当前账户版本、范围、asof与原upstream/available时点，不能把旧发布记录自动当实时事实。

## 财务口径

口径 `account-raw-nav-dietz-v1`，Decimal80与分舍入，React只展示服务端数值。账面资产为现金账面余额＋各证券数量×原始报价。确认未结投资收入加、确认未结税/费减，得到净资产；应收/应付单列状态、依据、已结/未结及关联结算ID，不提前计作现金或券商可用。冻结款已在现金内，不再扣一次。可用、冻结、可取各保留原券商快照时点。未知数量或价格不填0市值；暂估成交费用的投影现金可展示估算，但确定LossFacts净资产及费用保留null。

`Ledger.price_period` 是09具体调用的只读费用前FIFO批次重放，复用同一批次/送转分摊规则，不修改真实含费账本。期初存量用有依据的origin报价建立期间成本，不拿未知取得成本或券商参考成本猜全历史。买入总价和卖出总价用原价；免费送转携带总本金到子批次；已知支付总额的配股本金为总额减最终已确认费用，费用分拆未知时价格损益保留未知。费用后补/更正通过当前实际关系读取最终费用，独立扣一次，不能直接把02含费realized_gain再减fees。

`facts` 是10冻结的LossFacts类型：账户范围、baseline/version/origin/asof/facts_version、baseline_assets/net_assets、external_in/out、费用前realized_pnl/unrealized_pnl、实际income/fees、pending_income_delta/pending_expense_delta、valuation_status。所有分项是同起点期间累计变化；分红、利息与关联收入结算属于投资收入，CASH_IN/OUT只属于外部投入/撤出。待结算余额变化和实际结算共同计一次。

必须满足 `P = realized + unrealized + income - fees + pending_income_delta - pending_expense_delta = NAV - baseline_NAV - external_in + external_out`。不能守恒的对账现金差额标记RECONCILE_REQUIRED，不猜它为利润；必需未知则P未知。百分比采用**修正Dietz实际时间法**：`P / (baseline_NAV + Σ signed_external_flow × (asof-flow_effective_time)/(asof-origin)) ×100`，费用/收入不增加外部资本；零时长、非正分母或未守恒则比例未知。金额分项不含“剩余额度”。

## 现金更正的实际调用方修复

09公开组合暴露了04/05“税应付10→支付10→支付更正8→应付更正8”合法终态被旧10元中间态隔离的问题。当前重放先按所选知识截止收束最终CASH_CORRECTION金额，再校验关联结算；原事件/原金额、旧版本和旧知识截止仍原样保留。派生cash_records可含 `applied_amount_at_knowledge` / `applied_corrected_amount_at_knowledge`，cash_resolutions分开最终amount与原更正raw_amount。它们表示当前知识下的重述，历史实际确认的cash_delta和原材料由不可改事件/回执查回。

最终应付8、支付8→现金只扣8、未结0；没有对应支付更正的应付8/支付10仍拒绝。CSV3四行可单版本确认；没有新增事件/列，不改已冻结CSV1/2/3含义。此次只修实际关联金额物化，不引入事件框架或删除超额保护。

## 原报价与用途边界

只用07原QUOTE，研究复权日线不能作为实际持仓价格。保留每只证券upstream_at/available_at、source/raw_hash/run/snapshot/evidence_kind。同上海日期价格是SAME_DAY_INDICATIVE；跨日期、实际已证停牌或证券报价不同步为STALE，缺价为MISSING。旧价可展示显式估算，来源更新时间不替换报价原时间；该参考估值口径不授盘中交易资格，也不替代08/25按用途查询原时点与实际可行性。

方法案例经过真实FastAPI/SQLite/原件/Parquet路径，但仍标METHOD_CASE，输出input_authority明确ACTUAL_ACCOUNT_WITH_METHOD_MARKS；不能据此声称实际市场状态或资金授予。07实际原件验收使用其保全的原真实报价与合成账户，明确不代表用户真实财富。[09证据](../.scratch/roll-p0/evidence/09/acceptance.md)分开方法、原件、Chrome与真实OS恢复。

16/31可整合启动迁移；当前只幂等创建valuation_versions/valuation_baselines与组件09-valuation-v1标记，不重置全局schema版本。25/27正式损失预算/暂停、26实际试用归属和08用途新鲜度消费联验仍待实际调用方，未伪造这些结果。
