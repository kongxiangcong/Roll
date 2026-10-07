# 有限名单、规则与交易日契约（06）

06 使用现有 FastAPI 与唯一 SQLite。新增 `roll.market.directory.MarketDirectory`、`roll.market.rules.RuleCalendar`；没有新依赖、网络抓取框架或第二个账户写入者。市场表幂等创建，不更改 SQLite 全局 `user_version`。`Ledger.versions(after, db)` 是只读的确认历史接口。

## 名单与身份

`GET /api/market/list` 返回当前全部真实持仓与显式关注的并集、`version`、`account_version`、`recorded_at`、`as_of_date`、`over_limit` 与两只固定背景指数。达到20只后拒绝新成员；账户已有资产可超额，全部保留。移除关注不能移除持仓。指数仅用于 BACKGROUND，不能加入股票研究/关注或取得交易能力。

`POST /api/market/watch` 接受 `operation: ADD|REMOVE`、明确的 `instrument: SSE|SZSE|BSE:六位代码`、`expected_list_version`。旧版本返回409 `LIST_VERSION_CONFLICT`，达到上限返回409 `WATCH_LIMIT`。增删事件及实际变化的快照持久化。`GET /api/market/list/versions/{version}` 查询原快照，未来身份和账户权限不回写旧快照。

`POST /api/market/identities` 接受 instrument、exchange、board、instrument_type（STOCK/OTHER）、name、basis、带时区且非未来的 effective_at。身份是用户根据明确资料核对的事实，来源为 USER_CONFIRMED，保存确认时点、依据、输入指纹、revision；它不是在线交易所身份核验。未核对时板块/类型未知，不从代码前缀、名称或“ST”推断。范围外身份请求403，背景指数不得改为普通股票。

每个成员分别返回 `rule.implementation_status`、来自确认账户版本的 `account_permission`、`current_status`、`model_qualification`、`new_trade_use` 和 limitations。06尚未取得每只证券的当前停牌、风险警示、上市阶段、除权状态；当前状态为UNKNOWN并明确无来源/时点，不伪装实时查询。07负责取得可追溯事实，相关后续票执行资格门禁。规则已适配、已有持仓、加入关注、模型技术资格或资金授权都不能证明账户权限已开通。

`POST /api/market/scope/check`（同一应用接口 `MarketDirectory.check_scope(ScopeCommand)`）接受非空 instruments 和 purpose OBSERVATION/RESEARCH/BACKGROUND，当前名单外返回403 `OUTSIDE_FINITE_LIST`。BACKGROUND只允许固定上证指数与深证成指。成功只证明本次名单范围允许，返回名单/账户版本、技术资格NOT_GRANTED、交易能力NONE；07必须在真实单证券获取前调用该接口，不能把它解释为模型用途已合格。

`GET /api/market/history` 返回观察名单快照、关注事件、每次账户确认的成员历史。持久化 `market_account_memberships` 的最大账户版本是追赶标记；每次名单查询只通过索引读取未处理的确认版本。确认时的关注与身份按 recorded_at/confirmed_at 截断，因此未曾打开页面的持仓变化仍保留，事后确认的身份不会伪造为历史已知。每条同时保留原账户 confirmed_at/effective_at、实际整理 materialized_at 和依据 CONFIRMED_ACCOUNT_VERSION。成员版本不代表历史市场观察、StageSnapshot、行情/预测或真实前向覆盖。

## 实际来源、规则和范围

2026-10-07实际GET取得原件，原 URL、实际取得时间、字节数、SHA256见 `backend/src/roll/market/reference/sources.json`。正文原件和发布页保留；TXT是从原件提取的人工查证辅助文本，不替代原件。启动时验证原件SHA、将同字节内容持久化到 `ROLL_DATA_DIR/raw/<sha>.<ext>` 并登记 market_sources；损坏原件或归档会明确报错。`GET /api/market/sources` 查询元数据，`GET /api/market/sources/{id}/raw` 只允许已登记原件。没有用户私人材料或密钥。

- [上交所2026年休市安排](https://www.sse.com.cn/disclosure/dealinstruc/closed/)、[深交所2026年休市安排](https://www.szse.cn/disclosure/notice/general/t20251222_618087.html)：全年周末与逐项休市区间；政府调休工作日不自动成为交易日。
- [上交所2026规则发布及附件](https://www.sse.com.cn/lawandrules/sselawsrules2025/stocks/exchange/c/c_20260424_10816482.shtml)、[深交所2026规则发布及附件](https://www.szse.cn/lawrules/rule/trade/t20260424_620190.html)：2026-07-06生效。SSE暂缓实施附件仅列其他条款，不能将2023年主板风险警示5%继续冒用为当前规则。
- [深交所A股次交易日可卖说明](https://investor.szse.cn/warning/activities/fundIntroduction/t20210108_584159.html) 是补充说明；当前规则3.1.4/3.1.5也限制交收前回转（例外不含普通A股）。最早日期不是已核实的实际可卖数量。
- 北交所官网本次访问返回403/抓取策略重定向，未取得可验证的2026原件；BSE规则、阶段和交易日均UNKNOWN/UNSUPPORTED。其持仓继续展示。2027、2026-07-06之前的规则及ETF/B股等其他类型未适配。

`GET /api/market/rules?exchange=&board=&instrument_type=&date=` / `RuleCalendar.rule(...)` 只适配普通STOCK的 SSE MAIN/STAR、SZSE MAIN/CHINEXT、日期2026-07-06至2026-12-31。提供买入最小量/增量、限价/市价竞价单笔上限、零股卖出、0.01元tick、普通状态涨跌幅、ROUND_HALF_UP、下一交易日可卖、原件与条款。MAIN为100/100/100万/100万/10%，STAR为200/1/10万/5万/20%，CHINEXT为100/100/30万/15万/20%。STAR特别条款6.6/6.7覆盖通用数量和涨跌幅条款。日期适配边界不宣称交易所规则在2026年底失效，仅限定实际验证范围。

特殊股票执行、精细竞价回放、费用估计未适配；停牌、风险警示、上市阶段与除权事实必须另行取得，不从基本规则推出当天可买。实际券商佣金、最低收费、税费依据未确认，费用保持UNKNOWN并限制费用估计，不当作零费。这些缺口在API及页面明示。

`GET /api/market/calendar?exchange=&date=&at=` / `RuleCalendar.calendar(...)` 使用2026 SSE/SZSE年历；返回年度安排下是否交易日及原件，而非宣称已核对盘中临时停市。at必须带时区并与转换后的上海日期一致；2026上海为UTC+08:00，历史夏令时年份不在适配范围。2026-07-06起支持开盘集合竞价、连续竞价、午休、收盘集合竞价及15:05—15:30盘后固定价格阶段，半开区间。此前时段UNKNOWN。BSE/其他年份未知，不回退工作日算法。

`GET /api/market/resale-date?exchange=&board=&buy_date=` 返回已知交易日且适配规则下的最早下一个已知交易日；年底跨到未知年历返回null。休市日不生成买入可卖日期。对证券临时停牌、实际交收、订单类型的执行判断由后续用例核对。

实际覆盖和验证结果见 [06验收记录](../.scratch/roll-p0/evidence/06/acceptance.md)。25/26仍需在各自交付时联验新动作及执行意向的账户权限门禁；06不签发资格或动作。
