# 给 WorkBuddy 的 Ticket 19 历史数据取证提示词

版本：2026-10-09。以下全文可直接复制给 WorkBuddy；请按指定文件格式交付。

## 任务目标

请为 Roll 项目收集、核验并整理江西铜业 A 股 `SSE:600362` 的历史研究数据，形成可以交给开发代理复核和接入的证据包。目标是支持 ticket 19 的真实透明模型训练、时间外预测、独立时间区间校准和模型冻结。

你负责**寻找和交付真实数据及证据**。不负责拟合模型、计算盈利标签、调参数、推荐交易、替宿主批准来源，或宣布 ticket 19 验收通过。真实准入、分窗、特征标签、训练、校准、冻结仍由开发代理实现。交付格式是本次外部证据交换约定，不是现有 Roll API 已经支持的直接导入格式。

已知背景：候选固定四个量价特征，使用 RAW 原价收盘 5/20 日回报、20 日逐日回报波动、当日成交股数与之前 20 日平均成交股数的对数比值；需要截至每个观察日连续完整的 21 行日线。预测事件是预定下一交易日开盘入场、至第 20 个交易日收盘的费用后正收益，最终还要处理状态、权益和执行限制。21 行只够一个特征观察，不能当作整个训练／校准的数据量。

我们已有当前接口返回的数千条历史行、官方日历、部分规则、14 次已知现金分派原件；但现有历史归档报价只覆盖 43 个业务日、最长连续 2 日。最关键缺口是**连续数据的历史当时可得版本，以及完整状态／权益覆盖证明**。单纯再次拉取今天的历史接口、增加更多最新修订行，不能解决这一缺口。你如找到有力来源，请取得原件和完整交付，不要只给产品介绍或链接列表。

最终研究仍保留既定支持要求：CAL 正／负类各至少20、每个占用概率箱至少20、入选子集40、有效20日期限依赖块30等条件；不同条件各有对应评价口径，不能把它们当同一个简单行数指标。此处只说明为何需要长时间连续覆盖，不授权你计算标签、分箱或选择窗口；这些检查由宿主在合法分窗后执行。多年度数据也不保证这些条件一定满足，不足时不能降标准或借用封存数据。

## 采集范围与执行边界

1. 只收集江西铜业 A 股，股票身份、市场、币种必须一致，不能混入港股、指数或其他股票。
2. 本次默认候选采集范围：`2016-01-01` 至 `2023-12-31`；另收集 `2015-10-01` 至 `2015-12-31` 的必要日线／日历／状态／版本证据作为前置特征上下文。长范围用于避免只够少量机械计算样本。若仅能取得部分范围，原样交付并说明，不缩短范围后宣称已经足够。
3. 上述日期是**本次外部采集候选范围，不是已经登记的 DEV/CAL 窗口**，不修改项目现有协议，不替开发代理确定分割日。正式窗口在核验来源和覆盖元数据后、计算结果标签及拟合前登记。不要按涨跌、收益、类别比例或模型效果挑选年份／日期。
4. 不索取 `2024-01-01` 以后的市场观测，不读取任何已有标为 `SEALED` 的文件、分片、最终测试结果。若已有获准范围／封存边界与本请求冲突，以已登记边界为准，停止冲突部分并记录缺口。官方文件可以今天取得，但只提取与获准历史范围有关的依据，不把后来披露内容当作早年预测输入。
5. 优先真实交易所、发行人、中国结算、财政／税务机关、可提供历史版本和修订链的数据机构，其次是能够取得正文的历史归档／WARC。搜索引擎摘要、网页缓存时间、接口批次时间或第三方口头“PIT”标签都不能独立充当证明。
6. 可自主公开搜索、下载、核验和解析；不购买、付费订阅、签约、代为联系外部人员或提交申请。如需这些动作，列出具体供应方、产品、字段、历史版本能力、授权条件和价格／未知项，交付一个可审批的采购或申请方案。不要把方案当作已获得的数据。
7. 不访问账户、密钥或训练服务，不创建拟合／校准尝试。研究家族最后核验仍余 3 次主拟合／邻域与 1 次 CAL；这些是实验额度，与你的搜索次数无关，也不是交付期间可保证不变的预约。

## 必须取得的数据

### A. 完整原价日线及历史版本（最高优先级）

取得交易日期、开高低收、报告成交股数；成交金额如可得也交付。必须说明币种、价格单位、成交量原单位、转换依据及精度，明确 `RAW` 不复权。

需要每个用于特征的输入版本在当时何时已完整公布的证据，及修订政策／版本链。可以是历史抓取正文及可信捕获索引、供应方历史版本档案，或有明确覆盖范围的发布／修订档案和对应正文。证据必须能绑定到具体行或明确的行区间。

不要因为交易日期在过去，就声称当前查询的正文当时已可得。不要把后来捕获时间回填为当天发布时间。日后捕获只能证明在捕获时刻已经存在那个版本，不能独自证明当天预测截止前存在。只知道公开日期时保留 DATE，不补 15:00、15:05 或午夜。供应方发布时刻、归档捕获时刻、这次实际取得时刻分别保存。

原价跳变不自动修正；当前前复权／后复权不能替代 RAW。提供商 `preclose` 可能是除权参考价，不一定是上一日 RAW 收盘，必须说明口径。真实零成交、停牌占位、缺失、抓取失败、盘中未完成分别保留。

### B. 交易日历、证券状态与执行事实

取得覆盖范围内 SSE 的逐自然日交易日历及其修订，保留例外安排；再取得 600362 每个交易日的交易状态、停复牌、特殊处理状态及适用交易限制。异常交易日的交易时段或中断安排需有对应历史依据。

缺行情不推断休市，零量不单独证明停牌；没有 ST 字段不推断普通状态。涨跌停价如有，必须区分来源报告值与推导值；不要自行用统一百分比补全年份。数量、最小申报量、价格档位、T+1 等由当期规则提供依据。日线高低价不能证明券商成交或盘中先后顺序。

### C. 全部公司行为与权益覆盖

查清相关区间的现金分红、送股、转增、配股、拆并股、回购相关分红资格变化、终止上市／终结结算等适用事件。没有某类事件也要说明如何核查以及目录覆盖范围。

现金事件要分列公告、登记、除权除息、支付日期，每有权股份现金、每上市股份除权参考扣减、资格股数口径、扣缴及补税规则。现金实际支付日期与经济应收不同；日期级支付不能证明该日开盘前到账。不存在用户个人到账证明时，明确不是实际账户现金事实。

对于送转／配股等，交付比例、资格、股数变动生效、可交易日期、认购价格与期限、放弃／未认购的适用处理依据；不知道就留 null。不能由“总股本没变”推断全部权益没变。

14 次已知现金分派不是全事件覆盖证明。仅搜索未命中，只能记 `SEARCHED_NO_HIT`；只有范围明确、类别完整且可核验的权威目录／说明才可能支持 `EXPLICIT_NO_EVENT`。公告正文、实施公告、修订和撤销都要保留版本。

### D. 当期规则、交易费用与分红税制

收集候选区间适用的交易规则、佣金研究情景可引用的限制、印花税、过户费、分红税政策及官方解释。分列发布日期与生效区间，保存计费基数、单／双边、比例、最低额、舍入和例外；不以今天规则覆盖过去。

特别核对 2022 过户费、2023 印花税变更，买卖两边分别按各自实际研究日期适用规则。财政／税务政策需支持登记日期选择税制、自然月／自然年持股边界、初扣与补缴。未知券商实际佣金不能记零，研究情景不能当成用户真实费率。

## 统一数据与证据格式

交付 UTF-8 JSON／JSONL 与真实原件，不只交付 Word、截图、摘要或 PDF 总结。JSONL 每行一个完整 JSON 对象，不跨行；日期升序，重复／修订版本保留。所有规定字段都要出现，未知用 `null`，同时在 `unknown_fields`／缺口中说明；不使用 NaN、Infinity、空字符串冒充已知值。

日期用 `YYYY-MM-DD`；精确时间用带时区 ISO 8601（如 `+08:00`／`Z`），没有精确时钟只交日期。金额、价格、数量、比例均用十进制字符串，避免浮点损失；字节长度、行数为整数；布尔或枚举字段未知仍为 null。SHA256 为实际文件字节计算的 64 位小写十六进制值，禁止编造。

任何事实都必须能沿 `evidence_refs → evidence_index → raw文件` 找到原始依据。URL 不能替代原件，原件哈希不能替代历史可得性证明。

### 交付目录

```text
ticket19-data-delivery/
  manifest.json
  README.md
  data/
    daily_bars.jsonl
    trading_calendar.jsonl
    security_status.jsonl
    corporate_actions.jsonl
    historical_rules.jsonl
    revisions.jsonl
  evidence/
    sources.jsonl
    evidence_index.jsonl
    search_log.jsonl
    raw/                 # 实际取得的HTML/JSON/CSV/PDF/WARC片段等原件
  reports/
    coverage.json
    gaps.json
    conflicts.json
```

所有文件必须存在；没有记录时 JSONL 文件为空，并在报告中说明 `NOT_FOUND`、`NOT_SEARCHED` 或其他真实原因。不得填模拟行让文件看起来完整。路径使用包内相对路径，不包含账户、token、Cookie 或密钥。

### 通用事实字段：六个 data/*.jsonl 文件每条记录都包含

| 字段 | 类型／含义 |
| --- | --- |
| record_id | 包内稳定且唯一字符串；修订生成新ID，不覆盖旧ID |
| instrument | `SSE:600362`；交易所日历／通用规则适用时 null |
| source_id | 对应 sources.jsonl 的来源ID |
| evidence_refs | 非空数组；元素 `{ "evidence_id": "真实ID", "locator": "PDF页码／表格行／JSON路径等实际定位" }` |
| historical_publication | TimeEvidence 对象；原版本公开时点，未知不补造 |
| historical_availability | TimeEvidence 对象；该版本当时可用证据，与publication不自动等同 |
| captured_at | TimeEvidence 对象；历史归档捕获时间，没有则UNKNOWN |
| received_at | 这次实际收到该正文的带时区时刻；不是历史交易日 |
| revision_id | 来源原版本ID或该原件哈希；不是虚构版本号 |
| evidence_class | `CAPTURED_HISTORICAL_VERSION / PROVIDER_VERSION_ARCHIVE / DOCUMENTED_PUBLICATION_AND_REVISION_HISTORY / CURRENT_QUERY_ONLY / UNKNOWN` |
| unknown_fields | 字符串数组，明确哪些字段／口径未证实 |

TimeEvidence 格式如下。这里只定义空模板，不能把模板当作取得的证据：

```json
{
  "value": null,
  "precision": "UNKNOWN",
  "not_later_than": null,
  "basis": "NOT_ESTABLISHED",
  "evidence_refs": []
}
```

`precision` 为 `DATE / MINUTE / SECOND / MILLISECOND / UNKNOWN`；`value` 按真实精度填写，DATE只填日期。`not_later_than` 表示有原件支持的可得性上界，不是首次发布时间；只知道某次归档存在时填写这个上界，不填虚构的首次公开value。`basis` 用文字说明证据链。已知时点必须有具体evidence_refs；不知道时保留上述null和UNKNOWN。

### daily_bars.jsonl 额外字段

| 字段 | 类型／含义 |
| --- | --- |
| trade_date | 交易日期 |
| open / high / low / close | 十进制字符串或null，币种CNY、价格单位元／股 |
| currency / price_unit / adjustment | `CNY` / `CNY_PER_SHARE` / `RAW`；不能证实RAW就null并报缺口 |
| volume_shares / amount_yuan | 十进制字符串或null；股／人民币元 |
| original_units | 对象 `{price, volume, amount}`，来源原单位及precision说明 |
| unit_conversion | 对象 `{volume_factor_to_share, amount_factor_to_yuan, basis_evidence_refs}`；未知因子null，不能猜 |
| reported_preclose / preclose_basis | 提供商报告的值／口径；未知null，不覆盖上个RAW收盘 |
| completion_state | `COMPLETE_REPORTED_HISTORICAL / INTRADAY / UNKNOWN`；完整不等于已证明历史PIT |
| row_kind | `OBSERVED_BAR / REPORTED_ZERO_VOLUME / SUSPENSION_PLACEHOLDER / UNKNOWN` |
| errors | 来源或一致性问题字符串数组，异常不删除 |

缺日线不补零行；在coverage/gaps列出具体缺失日期。多个版本同日保留，通过revisions关联。量价校验矛盾也保留原值并报告，不擅自“修复”。

### trading_calendar.jsonl 额外字段

`exchange`固定SSE；`calendar_date`；`is_trading_day`布尔或null；`sessions`数组（每段含当地开始／结束时间及依据，不明留空）；`exception`文字或null。覆盖逐自然日，节假日变更及异常安排保留新旧版本与生效依据。不要从周一到周五推算。

### security_status.jsonl 额外字段

`trade_date`；`trading_state`=`TRADING / SUSPENDED / PARTIAL_SESSION / UNKNOWN`；`special_treatment`=`NORMAL / ST / STAR_ST / OTHER / UNKNOWN`；`limit_up_yuan`、`limit_down_yuan`；`limit_price_basis`=`PROVIDER_REPORTED / UNKNOWN`；`suspension_start`、`resumption_time`（TimeEvidence）；`status_rule_refs`（historical_rules的record_id数组）。没有状态证据不能填NORMAL/TRADING。来源报告状态与历史时点资格分别保存。

### corporate_actions.jsonl 额外字段

`event_id`；`event_type`=`CASH_DIVIDEND / BONUS_SHARES / CAPITALIZATION / RIGHTS_ISSUE / SPLIT / REVERSE_SPLIT / BUYBACK_ELIGIBILITY_CHANGE / TERMINAL_SETTLEMENT / OTHER`；`event_status`=`ANNOUNCED / IMPLEMENTED / REVISED / CANCELLED / UNKNOWN`；`announcement_date`、`record_date`、`ex_date`、`payment_date`；`gross_cash_yuan_per_eligible_share`、`ex_reference_deduction_yuan_per_listed_share`；`eligible_share_basis`；`share_change_ratio`；`rights_subscription_price_yuan`；`subscription_start_date`、`subscription_end_date`、`new_shares_tradable_date`；`tax_rule_refs`；`settlement_basis`。

不适用字段null并区分“不适用”与“不知道”。比例口径明确如“每1原股份增加多少股”，不要混用每10股和每股。此文件记录发行人／市场事件，不记录推定用户个人到账，不计算示例持仓权益金额或收益标签。

### historical_rules.jsonl 额外字段

`rule_id`；`rule_type`=`TRADING_SESSION / T_PLUS_ONE / ORDER_LOT / PRICE_TICK / PRICE_LIMIT / COMMISSION_CONSTRAINT / STAMP_TAX / TRANSFER_FEE / DIVIDEND_TAX / OTHER`；`applicable_scope`；`effective_from`、`effective_to`（明确含端点规则，未知不外推）；`charged_side`=`BUY / SELL / BOTH / NOT_APPLICABLE / UNKNOWN`；`calculation_base`文字；`rate`、`minimum_yuan`、`maximum_yuan`、`rounding_rule`；`holding_period_definition`；`exceptions`数组；`rule_text_excerpt`（简短原文，定位到原件）。

复杂税档放在 `tiers` 数组，每项包含条件原文、边界是否包含、税率、初扣／补缴说明与证据引用。数值全部十进制字符串或null。最低额未证实不能填0；today仍有效不证明早期整段都有效。

### revisions.jsonl 额外字段

`revised_record_id`、`prior_record_id`、`revision_publication`（TimeEvidence）、`changed_fields`数组、`revision_reason`、`supersession_basis`。没有发现修订不等于证明从未修订；是否具有完整版本链写入coverage。旧行／旧原件不删除。

### sources.jsonl 字段

每条包含 `source_id`、`publisher`、`source_type`、`official_or_provider_url`、`upstream_source`、`retrieval_method`、`historical_version_capability`、`revision_policy`、`release_schedule`、`coverage_scope`、`license_and_reuse_terms`、`evidence_refs`、`limitations`。

同一上游的多个转载不算独立来源。PIT能力、发布周期、授权条款都必须有依据，不能照广告填写。未知用null或具体limitations。

### evidence_index.jsonl 字段

每条包含 `evidence_id`、`source_id`、`original_url`、`capture_url`、`retrieved_at`、`http_status`、`content_type`、`relative_path`、`sha256`、`bytes`、`historical_publication`、`captured_at`、`scope`、`used_for`、`limitations`。

`relative_path`指实际包内原件；哈希与长度按交付字节计算。正文不做换行、编码、数字替换后再称原件。解压／解码／OCR产物单列为派生文件，保留原体及转换关系；WARC定位需保留collection、文件、offset、length及对应索引原件。403／503等失败原体可以保存，但used_for只能是请求失败证据，不是行情正文。避免保存敏感响应头。

### search_log.jsonl 字段

每条包含 `attempt_id`、`attempted_at`、`source_or_query`、`requested_scope`、`http_status`、`outcome`、`error`、`evidence_id`、`retry_of`、`next_possible_method`。outcome使用 `BODY_ACQUIRED / INDEX_ONLY / NO_MATCH_IN_THIS_QUERY / ACCESS_DENIED / NETWORK_ERROR / NOT_ATTEMPTED` 等实际结果，不把索引命中当正文到手，不把一个查询无命中当全部历史不存在。

## 覆盖、缺口与交付清单

### coverage.json

必须是JSON对象，包含下列键：

- `requested_scope`、`delivered_scope`、`context_only_scope`；
- `daily_row_count`、`unique_business_dates`、`version_count`；
- `calendar_coverage`、`status_coverage`、`corporate_action_coverage_by_type`、`historical_rule_coverage`；
- `missing_bar_dates`、`unknown_status_dates`、`unit_conflict_dates`、`incomplete_bar_dates`；
- `longest_consecutive_exchange_session_run`，以及使用的日历证据ID；
- `historical_version_evidence_counts`，按evidence_class计数；
- `metadata_candidate_21_row_windows`：仅基于已核验日历／完整RAW行／单位的候选数量，**不是合格训练行**；
- `historical_availability_coverage`：各日期／区间的已证实界限、UNKNOWN和证据引用，不自行填写ready_to_fit；
- `revision_chain_completeness`、`provenance_missing_records`；
- `hash_length_validation`、`cross_source_conflicts`；
- `mature_labels_calculated`固定false，`model_training_performed`固定false，`sealed_payloads_read`固定false。如违背过边界，必须真实报告并单列暴露，不能继续填写false；
- `formal_dev_cal_windows_registered`固定false，`qualification_decision`固定`HOST_REVIEW_REQUIRED`。

公司行为覆盖分别用 `SUPPORTED_COMPLETE_SCOPE / KNOWN_EVENTS_ONLY / SEARCHED_NO_HIT / NOT_SEARCHED / UNKNOWN`，每个状态给出依据。不是找到了几个事件就填全覆盖。候选21行窗口数量不证明后续20日结果可评分，不计算正负类比例、模型分数或训练／校准标签。来源若自带相关标签不读取／纳入。

### gaps.json 与 conflicts.json

两者均为数组；没有问题可以为空，但必须经过实际核验。每项包含 `id`、`category`、`severity`、`affected_dates_or_scope`、`affected_fields`、`description`、`evidence_refs`、`methods_attempted`、`why_unresolved`、`next_step`、`requires_external_authorization`。

severity分 `BLOCKS_HISTORICAL_INPUT / BLOCKS_EXECUTION_OR_RIGHTS / LIMITS_COVERAGE / INFORMATION_ONLY`。冲突另加各来源值，不自动按多数表决或选择有利值。未知精度、修订链、完整状态／权益范围都要列具体缺口，不能只写“数据不足”。

### manifest.json

以下仅为空模板。实际交付时填写真实值；files枚举包内除manifest自身之外的所有交付文件，不能编造哈希或把null模板当完成品。manifest不包含自身哈希，避免自引用；可另外提供整个zip的SHA256。

```json
{
  "schema_version": "ticket19-external-evidence-v1",
  "delivery_id": null,
  "generated_at": null,
  "instrument": "SSE:600362",
  "collection_scope": {"from": "2016-01-01", "to": "2023-12-31"},
  "context_only_scope": {"from": "2015-10-01", "to": "2015-12-31"},
  "window_status": "COLLECTION_CANDIDATE_NOT_PREREGISTERED_DEV_CAL",
  "delivery_status": "UNASSESSED",
  "source_ids": [],
  "files": [],
  "unresolved_gap_ids": [],
  "training_performed": false,
  "labels_calculated": false,
  "sealed_payloads_read": false,
  "qualification_decision": "HOST_REVIEW_REQUIRED"
}
```

`files`元素字段为 `path`、`sha256`、`bytes`、`format`、`record_count`（JSONL实际行数；其他格式null）。`delivery_status`仅用 `EVIDENCE_DELIVERED / PARTIAL_DELIVERY / NO_QUALIFYING_BODY_FOUND` 描述交付事实；EVIDENCE_DELIVERED不代表已满足训练准入。普通正文全部到手但PIT等未知时，使用PARTIAL_DELIVERY并列gap，不写READY/PASS。

### README.md 与最终回复

README须包含：实际范围与来源、取得方法、历史时点证据的强弱、计量与版本口径、覆盖数量、主要缺口、冲突、失败请求、文件索引、许可限制、需要购买／申请的具体方案（如有）。不要宣称当前查询是历史快照，不宣称训练验收通过。

最终回复按以下结构：

1. 交付包下载链接或附件、字节大小、实际SHA256。
2. 用表格列出日线PIT／日历／状态／公司行为／规则各项：已交付内容、范围、缺口、证据文件。
3. 说明下一步是否有充分来源供开发代理复核，未解决什么；不代替宿主资格判断。
4. 需要外部授权的事项单列；无需授权的下一种搜索／获取方法单列。

若工具无法生成附件，明确报告限制，逐文件返回完整机器可读内容；大文件需可下载的真实原件或分块文件及校验清单，不能截断／省略行后声称完整。可以展示少量真实行帮助说明，但展示样本不能替代完整包。只有链接或产品介绍而无正文时，交付真实失败／索引证据及具体取数方案，不伪造文件。

## 交付前自行核验

- 所有JSON／JSONL可解析；ID唯一，外键、相对路径和locator可追踪。
- manifest文件长度、SHA与实际原体一致，JSONL行数准确，没有隐藏截断。
- 价格／股数／金额单位有依据；RAW口径与版本不混用；异常和未知不被补齐。
- 交易日期连续性依据官方日历；“连续21行”仅为特征上下文检查。
- 原公开、捕获、实际接收时钟分列；没有日期补时分或当前修订冒充过去版本。
- 公司行为、状态和规则的覆盖与已知事件分开；日级支付不证明开盘前到账。
- 未计算标签、未训练／校准、未选优窗口、未查看SEALED；如发生暴露如实报告。
- 原件／证明不足的地方明确交付缺口，避免把资料数量、可信来源名称或“PIT”营销词当作资格证明。

请持续执行所有无需额外授权的实际取证工作，优先解决连续RAW版本证据。最后交付能被逐字段复核的真实材料和明确缺口，不用模拟数据、当前查询结果或文字承诺替代缺失历史证据。
