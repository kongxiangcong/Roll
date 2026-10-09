# 日线执行与成熟标签（18）

`POST /api/research/protocols/{protocol_id}/executions` 消费17已登记数据的宿主过滤 DEVELOPMENT/CALIBRATION 分片。输入为 `partition`、`observation_date`、`basis`；可选 `label_as_of`（带时区、不得晚于实际现在）、`quantity`、预登记 `delay`、`fill_fraction`，及17登记的佣金/滑点邻域。SEALED 返回403并保存拒绝审计；校准前置20行仅特征上下文，不能登记标签。不是未来预测发布入口，不产生前向起点、账户事实、正式能力或G7。

延迟限定 NEXT_OPEN、NEXT_CLOSE、ONE_MORE_SESSION_OPEN、OUTSIDE_ALLOWED_PRICE_NO_FILL；成交压力0/0.50/1。数量在观察日原价价窗及合成预算上冻结，不用未来实际成交价挑选规模；未指定时按冻结上界、手续费和股票整数增量取整。显式数量不能越过现金/50%暴露限制。归档和归一化价格用十进制字符串，费用按人民币分 ROUND_HALF_UP；佣金已含规费，额外规费不重复计。实际券商佣金仍UNKNOWN，费用是17研究情景，绝非官方账面支出或免费成交。

宿主先可靠归档输入，再用短SQLite事务保存不可变ExecutionRun及 EXECUTION_REGISTERED 审计，网络与计算均不占账户写事务。记录冻结协议/数据指纹、原价及原raw引用、分片SHA、事件、20个交易日、成熟规则、订单窗口/计划数量/时点、退出/成本及执行代码指纹；再追加独立结果。重启未结束运行会追加INTERRUPTED，不能补造成功标签。全局Ledger schema版本保持原有值，本票仅创建自己两张表。

20日期限从观察日后的第一个已确认交易日起计，延迟交易不延长退出期限。交易日由06归档沪深2026日历计算，不把缺日线当休市、不按工作日外推未知年度/交易所。`label_matures_at` 在有确证时段时保存完整时刻；历史时段规则不足时保存 `maturity_date` 和明确规则 `TWENTY_CONFIRMED_TRADING_SESSIONS_AND_COMPLETE_EXIT_BAR_AVAILABLE`，不将日期补午夜。METHOD显式归档时段只是方法证据，不把其15:00/交易状态外推为真实历史规则。

IMMATURE 返回空标签/净损益，拒绝评分和学习；次日上涨不算20日成功。UNSCORABLE 保留状态/公司行为/规则未知、当前未完成、非法价格、缺行、消费截止不可得、跨分片期限等原因。未执行/真实报告零成交量/停牌买入/超价窗口保留 NO_EXECUTION，经济现金影响0但预测标签为空；停牌无法退出保持 BLOCKED_EXIT/空损益，不能当亏损或已平仓。部分成交按整数增量取整，小于最小买入量不成交。T+1保存最早可卖日期。

只有归档确定性 `CONFIRMED_ALL_SHARES_CASH_SETTLED`、明确带时区生效/可得时点、现金每股值和最终无需再扣费口径才允许按17预登记终止结算规则提前成熟；未确认结算不提前成熟。确定性现金无需补造不存在的日线退出价格，原证据指纹随定义保留。本轮只验证METHOD终止结算，不声称真实该股票已终止。

日线触价不证明真实成交或同日顺序。额外 stop/profit 原价边界仅允许明确METHOD_CASE压力，实际M0固定HORIZON_CLOSE不能被客户端改成新事件。买入日触价不能绕T+1。后续日线触价将止损、止盈及错过触价的期限退出共同保留为路径集合；CONSERVATIVE取费用后下界、INTERVAL保存净损益区间但不评分、UNDETERMINABLE保留不可评分。保守情景仍非观测的券商成交。下一可观察报价未形成适用于该历史观察的真实后继输入，因此本票不提供该额外成交路径，也不接受客户端execution_price注入。

`GET /api/research/executions/{id}` 查询原记录。`POST .../{id}/assessments` 仅接收新 `label_as_of` 和 `basis`，追加子记录、根/父ID与父输入SHA，不更新原未成熟结果、不换价窗/事件/输入。每次消费者以自己的 `consumer_knowledge_cutoff` 核验原事实available_at，原取数request的flag不永久否定当前事实，也不伪装过去可得。标签 `label_available_at` 是实际结果生成时点，不回填到历史成熟日。今天名单、当前修订、未知历史PIT和未知真实照做分布的限制始终保留。

`POST .../{id}/replay` 校验归档SHA并用原定义/评估时点结构化重算，联网0，返回matches_original。计算源的指纹为SHA256 canonical-LF文本，跨Windows Git换行仍一致；供应商raw/Parquet/输入JSON的SHA始终按原字节，绝不规范化。计算源版本改变返回409并保留旧结果，不冒充旧算法重算。新完整协议/模型不得偷换原输入。

`GET /api/research/protocols/{id}/execution-support?partition=DEVELOPMENT|CALIBRATION` 供19读取同一18产物：所有记录数量、唯一对象日期机会数、每个冻结执行族最新复评的成熟/未成熟/未知/未执行数量、逐原因支持缺口、数据/输入/代码及成本指纹和完整结果。旧记录依ID仍可查。重复日期、压力方向和复评均不算独立统计支持，`independent_sample_count=null`。METHOD可机械评分但 `eligible_for_training=false`；实际历史PIT/状态未证也不授真实训练资格。该接口不是拟合、模型冻结、完整协议冻结或准入接口。

历史研究子页查看与保存模拟、复评、下载冻结输入和离线重放；主导航仍为五个入口。默认显示最近12个方向并明确数量，可展开全部；数据库/API不截断机会或隐藏未知。UI与支持量分列REAL_ACQUISITION和METHOD_CASE。真实18验收120个允许窗口机会全UNSCORABLE/真实训练0（其中40期限跨界）；不能用METHOD结果解锁真实19训练、20完整协议或21准入。

完成退出bar的归档可得时点也必须不晚于label_as_of；仅交易日期相同或consumer_knowledge_cutoff=now不足以成熟。实际适配规则日期使用06已核15:00收盘依据，未知时段留MATURITY_TIME_UNKNOWN。METHOD压力原件显式声明method_completion_available_at / method_settlement_available_at等合成完成时钟，和真正归档available_at分列；它只支持方法历史评估，不证明当时现实可得信息。中间停牌/报告零量bar的触价从候选退出路径排除并保留日期；期限日停牌或退出量未知/零仍是无法退出，不选择非法保守价格。

日线执行/复评登记记录当前宿主PID、进程创建时钟及实例nonce。启动恢复只结束无法验证仍存活宿主的未完成执行；活peer保持RUNNING及原输入/定义，完成记录与审计在短事务中只追加一次。执行源码指纹随本次宿主边界修复更新；旧结果不可变，旧引擎记录的重放/复评仍接受现有代码版本门禁。

## 真实历史执行税费版本（19，2026-10-09）

非 METHOD 执行定义保存 `historical_costs.BUY/SELL`，分别按订单入场日与固定退出/终结日解析，绑定 `historical-cost-sources.json` 所列官方原件SHA、来源、实际收到时间和披露精度。2008-09-19起证券交易印花税仅卖方1‰；2023-08-28起卖方0.5‰，买方0。跨生效日交易不以观察日或一个统一现行率替两边计费。

2015-08-01起过户费按成交金额0.02‰双向计算，适用至2022-04-28；2022-04-29起为成交金额0.01‰双向。2022中国结算通知来自官方URL的2022-05-16历史捕获，原件SHA、实际收到时间、原URL/捕获URL及捕获时钟单独保存；正文明确披露DATE和生效日，不声称精确首次发布时间。2015前官方材料只报告旧沪市按成交面值0.3‰，未证明全期起始/最低额，因此返回 `HISTORICAL_TRANSFER_FACE_VALUE_START_AND_MINIMUM_UNPROVEN`，不按金额替代、不猜最低1元，执行为UNSCORABLE/空损益。税费准入不解除原历史rule、PIT、状态、权益或分窗限制。

已有2026收费页面仅为 MONTH/current display，在既有规则适配范围2026-07-06—2026-12-31作为 `CURRENT_DISPLAY_SCENARIO` 保持当前研究场景兼容；它不认证中间历史费率区间，也不编造2026某个具体月初生效日。实际收到时间与现行费率场景依据随档案保存；经手/监管费包含在冻结研究佣金，不另收一次。实际券商佣金保持UNKNOWN，按分取整为预登记研究计算口径。

自动计划数量使用入场日已解析过户费；费用未知不以现行假设补齐。计费使用已冻结每边税费，METHOD仍完全使用其明确合成 `costs`，不将METHOD定价认定为真实法规材料。本次不新增真实训练资格或正式动作。

新的 `engine_sha256` 联合绑定执行源码、历史费用模块、来源清单及所有原件内容指纹。费用政策或依赖改变不能以新算法重放/复评旧运行；旧输入/结果仍可查询，0联网重放只消费原归档定义。新执行输入另有其本次源原件归档引用，备份纳入原件而不读取源站。
