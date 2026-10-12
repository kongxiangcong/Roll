# CNEquity 源码核查：作为 Ticket 19 补充采集层

核查日期：2026-10-10（Asia/Shanghai）。结论：**适合作为候选外部采集层，辅助从今天起积累真实数据；不能凭安装、字段名称或 `pit_mode="strict"` 直接满足 Roll 的资格准入。** 当前用户已决定不再寻找旧 PIT；以下限制用于设计未来持续记录与验收，不要求重开旧历史搜索。

## 范围与证据级别

- GitHub 公共 API `/repos/rootSunc/CNEquity/commits/main` 当次返回固定 commit **`c118038ea82b5bb78783c0c17a1d9251b36de71d`**。下列链接全部固定到该 SHA；API tree 原件及按 blob API 读取的源码保存在本目录 `source/`。
- 只读查看官方源码与测试；未安装包、执行第三方源码、连接真实行情端点、修改 Roll 数据库、读取 SEALED、训练或消耗实验预算。
- “实现存在”指源码实现；“测试覆盖”指已阅读官方测试，**没有在本机运行这些测试**；项目作者在注释中报告的实测结果不代表本次或 Roll 的真实来源验收。
- 网页工具的 `main` 页面可能命中旧缓存，故判断以 API 固定 SHA 的源码为准。整仓 codeload ZIP 下载中断，残留文件不作为有效源码或证据；已使用的文件由 GitHub blob API 单独获取。

## 逐项判断

| Roll 需要 | 已确认的实现 | 尚需 Roll 处理或验收 |
| --- | --- | --- |
| RAW 日线与量额单位 | 日线保存未复权价；EastMoney kline 请求 `fqt=0`；TDX 与 EastMoney 股票日线量都在适配器边界从手乘 100 到股；金额字段不据价格猜造 | 验证真实标的的 `amount/volume` 与高低价合理关系；保留源单位与转换版本；缺金额不能填 0 伪装完整 |
| 从今天起 PIT | 行级有 `source/data_version/fetched_at`；有不可变 generation、revision、依赖 revision_map 与 read receipt | Roll 每次采集必须保存获取时点、实际查询结果/原件、哈希和全部依赖版本，并按当次 cutoff 选择已存在版本 |
| 旧历史 PIT | 5 类 PIT 数据的 strict 查询拒绝被标识为回填/重建的记录，并按公告与观察日期过滤 | 今日下载的旧日期日线或旧财报不自动成为当年的可见版本；本路线无需补找它们 |
| 停牌与 ST | 状态与 risk_warning 分离；当前板块快照与历史回填分级；有已知采集缺口排除与覆盖检查 | `derived_bar_gap` 仍是推导证据；ST 与 *ST 不区分；真实数据范围、未知值、来源和时间要独立验收 |
| 公司行为 | 现金分红、送股、转股、拆合、配股比例/价格、支付日期与来源有字段；选定适配器有原始响应归档 | TDX 送转合并、配股价格可 null；schema 无完整登记/认购/缴款/到账/公告时间链；Roll 仍需完整权益事件与税费/规则依据 |
| 原件与重放 | 选定 feeds 具备内容寻址原始 payload、SHA256、时间、请求参数和 source/request-bound 验证；COW generation 能重放旧版本 | 不覆盖所有数据集；`load_with_receipt` 返回 frame+receipt，不自动保存每次查询的正文；行情原件及自身查询快照要另行保留 |

### 1. 行情的 strict PIT 不能从财报接口外推

`PIT_DATASET_NAMES` 只有 `financial_statement_items`、`announcement_index`、`share_structure`、`shareholder_counts`、`top_holders`，**不包含 `daily_bars`、`trading_status`、`corporate_actions`**。[PIT 注册表](https://github.com/rootSunc/CNEquity/blob/c118038ea82b5bb78783c0c17a1d9251b36de71d/src/cnequity/domain/pit.py#L73)

`load()` 仅在 `dataset in PIT_DATASETS` 分支使用 `as_of` 与 `_apply_pit_filters`；非 PIT 分支按 start/end/证券读取，未把 `as_of` 作为 `fetched_at` 过滤条件。因此给日线传 `as_of`/`pit_mode="strict"` 不会获得财报那套观察截止过滤。[读取分支](https://github.com/rootSunc/CNEquity/blob/c118038ea82b5bb78783c0c17a1d9251b36de71d/src/cnequity/query/reader.py#L1033)、[非 PIT 读取](https://github.com/rootSunc/CNEquity/blob/c118038ea82b5bb78783c0c17a1d9251b36de71d/src/cnequity/query/reader.py#L1080)

项目也明确把非 PIT 日期表的 `pit_quality` 改为 `not_applicable`；read receipt 对这些表报告 `mode="not_applicable"`。这不是严格行情 PIT 声明。[数据集契约默认值](https://github.com/rootSunc/CNEquity/blob/c118038ea82b5bb78783c0c17a1d9251b36de71d/src/cnequity/domain/datasets.py#L623)、[read receipt](https://github.com/rootSunc/CNEquity/blob/c118038ea82b5bb78783c0c17a1d9251b36de71d/src/cnequity/query/receipt.py#L200)

财报等 PIT 表会按 `announce_date`、已知的 `available_at/source_published_at` 和 `max(observed_at,fetched_at)` 日期判断；strict 排除 source 名含 backfill/reconstruct/snapshot 的行。**这是日级 cutoff，且未知发布时间仍可空，不等于所有字段都有精确发布时刻证据。** Roll 不应拿其日级 strict 标签保证任意盘中截止时点。[过滤实现](https://github.com/rootSunc/CNEquity/blob/c118038ea82b5bb78783c0c17a1d9251b36de71d/src/cnequity/domain/pit.py#L228)

官方测试覆盖财报原版本/重述、当前回填不得早于采集日、strict 拒绝重建、同公告日修订保留原始观察。它们属于合成单元测试，不是供应商实际历史证据验收。[测试](https://github.com/rootSunc/CNEquity/blob/c118038ea82b5bb78783c0c17a1d9251b36de71d/tests/unit/test_pit_vintages.py#L79)

### 2. 不可变版本适合未来积累，但需要显式固定全部依赖

`RevisionStore.commit()` 保存完整 copy-on-write generation、文件 SHA/长度、契约指纹、前一 revision ID 与提交时点，再原子发布 `current.json`。历史 generation 有保留/引用保护机制。[版本实现](https://github.com/rootSunc/CNEquity/blob/c118038ea82b5bb78783c0c17a1d9251b36de71d/src/cnequity/storage/revisions.py#L692)

`revision_map` 可固定行情、因子、证券、状态、日历依赖；只给一个 scalar revision 不会固定依赖，未指定依赖取 current；质量报告、配置、软件版本也不由该 map 固定。[参数契约](https://github.com/rootSunc/CNEquity/blob/c118038ea82b5bb78783c0c17a1d9251b36de71d/src/cnequity/query/reader.py#L958)

`load_with_receipt(require_replayable=True)` 可拒绝无固定 generation 的依赖，receipt 记录版本、范围、行数和来源；其覆盖类型明确为 `observed_rows_only`、`completeness="not_assessed"`，不能据 receipt 就宣布完整。[实现](https://github.com/rootSunc/CNEquity/blob/c118038ea82b5bb78783c0c17a1d9251b36de71d/src/cnequity/query/receipt.py#L130)、[旧版重放测试](https://github.com/rootSunc/CNEquity/blob/c118038ea82b5bb78783c0c17a1d9251b36de71d/tests/unit/test_read_receipt.py#L106)

**建议**：每日采集与修订均由 Roll 记录“当时哪个 generation 已取得”，冻结实验时保存所有依赖 revision_map、查询 receipt 和结果正文；禁止后来的 current 隐式替换研究输入。

### 3. RAW 量额：代码口径明确，但真实 EastMoney 单位未在本次验收

EastMoney 日线请求 `fqt="0"`，volume 在边界乘 100，缺 amount 保留空；TDX 股票日K同样按手转股，指数 volume 特别保留自己的单位。[EastMoney adapter](https://github.com/rootSunc/CNEquity/blob/c118038ea82b5bb78783c0c17a1d9251b36de71d/src/cnequity/adapters/eastmoney/bars.py#L46)、[RAW 请求](https://github.com/rootSunc/CNEquity/blob/c118038ea82b5bb78783c0c17a1d9251b36de71d/src/cnequity/adapters/eastmoney/bars.py#L156)、[TDX adapter](https://github.com/rootSunc/CNEquity/blob/c118038ea82b5bb78783c0c17a1d9251b36de71d/src/cnequity/adapters/tdx_protocol/bars.py#L102)

`domain/units.py` 明写作者的 TDX 数百万行统计测量，同时也明写 **EastMoney 手口径没有独立实测**：其测量环境不可达 push2his，仅有零成交占位行；采用端点字段推定并靠质检捕获 100 倍错位。不能把这个推定或合成 adapter tests 当成 Roll 的真实验收。[单位说明与检查](https://github.com/rootSunc/CNEquity/blob/c118038ea82b5bb78783c0c17a1d9251b36de71d/src/cnequity/domain/units.py#L18)、[测试](https://github.com/rootSunc/CNEquity/blob/c118038ea82b5bb78783c0c17a1d9251b36de71d/tests/unit/test_eastmoney_bars_kline.py#L48)

### 4. 状态字段有改善，但推导停牌不是交易所原件

EastMoney ST 板块是**当前**快照，只覆盖沪深；北交所在此适配器中 risk_warning 为 null。停牌与风险警示互相独立。ST 与 *ST 明确没有细分。[适配器](https://github.com/rootSunc/CNEquity/blob/c118038ea82b5bb78783c0c17a1d9251b36de71d/src/cnequity/adapters/eastmoney/trading_status.py#L14)、[语义边界](https://github.com/rootSunc/CNEquity/blob/c118038ea82b5bb78783c0c17a1d9251b36de71d/src/cnequity/domain/trading_status.py#L29)

源码将同交易日 15:00 后取得的当前板块记录排为较强证据；把当前板块盖到较早交易日排为 restated；`derived_bar_gap` 次于明确来源。但 `EVIDENCE_POINT_IN_TIME` 也是冲突排序值，未知来源默认走较强等级，**不能直接映射成 Roll 的已验证严格 PIT**。[排序](https://github.com/rootSunc/CNEquity/blob/c118038ea82b5bb78783c0c17a1d9251b36de71d/src/cnequity/domain/trading_status.py#L149)、[测试](https://github.com/rootSunc/CNEquity/blob/c118038ea82b5bb78783c0c17a1d9251b36de71d/tests/unit/test_trading_status_evidence.py#L141)

停牌历史由证券生命周期内交易日缺失有效成交 bar（包括零量占位）推导；源码排除已登记 `missing_ranges`、`outstanding_keys`，有 unresolved `missing_units` 时拒绝推导，并令 ST 为 unknown。**未登记的源缺口依然可能被误判为停牌**，故 Roll 应保留 DERIVED 等级且用明确状态源补核，不能仅靠价格缺行判定。[推导与防护](https://github.com/rootSunc/CNEquity/blob/c118038ea82b5bb78783c0c17a1d9251b36de71d/src/cnequity/derive/trading_status_history.py#L136)、[状态构造](https://github.com/rootSunc/CNEquity/blob/c118038ea82b5bb78783c0c17a1d9251b36de71d/src/cnequity/derive/trading_status_history.py#L233)

### 5. 公司行为可补数，不能直接替代完整权益事件

schema 按每股规范化 cash_dividend/bonus_ratio/transfer_ratio/allotment_ratio，提供 allotment_price、payment_date/payment_source、ex_date、split_factor 等，现金是税前金额。[schema](https://github.com/rootSunc/CNEquity/blob/c118038ea82b5bb78783c0c17a1d9251b36de71d/src/cnequity/domain/schemas.py#L391)

TDX 送+转合并数全部放入 bonus_ratio，transfer_ratio 为 0；配股价格缺失或无效可为 null。它支持比例/价格，但不能保留送与转的法律/税务差异，且不能保证配股缴款价完整。[TDX 解析](https://github.com/rootSunc/CNEquity/blob/c118038ea82b5bb78783c0c17a1d9251b36de71d/src/cnequity/adapters/tdx_protocol/corporate_actions.py#L163)、[配股](https://github.com/rootSunc/CNEquity/blob/c118038ea82b5bb78783c0c17a1d9251b36de71d/src/cnequity/adapters/tdx_protocol/corporate_actions.py#L177)

该表没有完整的公告/登记/认购开始结束/缴款/股份到账日期链，且不属于 PIT 表。带获取时间和版本仍有用，但 Roll 需补充自身要求的完整生命周期与税费/费用政策，不可据 ex_date 补造所有日期。选定 EastMoney/TDX 公司行为适配器实现了精确响应归档，TDX 缺 wire bytes 可拒绝；官方测试覆盖合成现金/送转/配股与 wire 归档失败。[归档实现](https://github.com/rootSunc/CNEquity/blob/c118038ea82b5bb78783c0c17a1d9251b36de71d/src/cnequity/adapters/tdx_protocol/corporate_actions.py#L203)、[归档测试](https://github.com/rootSunc/CNEquity/blob/c118038ea82b5bb78783c0c17a1d9251b36de71d/tests/unit/test_tdx_corporate_actions.py#L309)

### 6. 原始响应归档确有实现，但覆盖范围不能泛化

`RawArchive` 保存内容寻址的 payload 字节、压缩文件、SHA256/长度、获取时间、请求参数和响应元数据；默认仅选定 PIT敏感/快照 feeds 与公司行为。`daily_bars` 默认不在列表，已查看的 TDX/EastMoney 行情适配器和行情 step 没有同款原始响应归档调用。[归档](https://github.com/rootSunc/CNEquity/blob/c118038ea82b5bb78783c0c17a1d9251b36de71d/src/cnequity/storage/raw_archive.py#L1)、[默认选择](https://github.com/rootSunc/CNEquity/blob/c118038ea82b5bb78783c0c17a1d9251b36de71d/src/cnequity/config/loader.py#L521)

`verify_raw_archive` 验证实际 bytes、wire_exact 标记以及当次 source/run/request_scope 绑定，避免借用别源、别范围、旧请求 receipt；这些防护有单元测试。[验证实现](https://github.com/rootSunc/CNEquity/blob/c118038ea82b5bb78783c0c17a1d9251b36de71d/src/cnequity/steps/http_common.py#L117)、[测试](https://github.com/rootSunc/CNEquity/blob/c118038ea82b5bb78783c0c17a1d9251b36de71d/tests/unit/test_raw_archive_evidence_scope.py#L65)

`source_snapshots` 是备源规范化 Parquet，和 wire 原件不同；`load_with_receipt` 最后返回 `ReadResult(frame,receipt)`，未自行把每个查询的结果正文写入持久档案。COW/portable snapshots 能保存已发布版本，但不能证明原始供应商响应全部留存。[备源快照](https://github.com/rootSunc/CNEquity/blob/c118038ea82b5bb78783c0c17a1d9251b36de71d/src/cnequity/storage/source_snapshots.py#L1)、[查询返回](https://github.com/rootSunc/CNEquity/blob/c118038ea82b5bb78783c0c17a1d9251b36de71d/src/cnequity/query/receipt.py#L233)、[portable snapshots](https://github.com/rootSunc/CNEquity/blob/c118038ea82b5bb78783c0c17a1d9251b36de71d/src/cnequity/storage/snapshots.py#L1)

## 对 Roll 的建议

采用“CNEquity 隔离数据湖 → 受控只读导出 → Roll 证据导入与验收”作为候选设计。它有价值的部分是适配器、增量/缺口记录、单位规范、版本和重放，能减轻从今天起自建数据库的数据工程量。首期优先 `600362.SH` 的 RAW 日线、每日状态、公司行为、公告索引及原件适配；Roll 保持掌管 `known_at`、按时点选择版本、未知值保留和资格准入。起算日期为 **2026-10-10**，不恢复搜旧 PIT。

接入前应做一轮小范围真实来源验收：RAW量额单位、所需日历/状态/ST、公司行为字段完整性、原件与查询正文/哈希、一次后续修订和冻结版本重放。根据验收结果逐个字段允许用于研究，不能一键继承上游的 strict/health 标签。

EastMoney、Sina、BaoStock 等若与 Roll 已有采集的实际上游相同，CNEquity 只是另一条采集路径，**不构成新增独立原始来源证据**。TDX/交易所等是否形成独立来源，也需按具体事实、真实输出与原始依据判断。

保留用户新路线：虚拟数据用于框架与模型工程；真实采集持续积累；样本成熟、实际训练验证与资格条件满足后，系统才标记可用。源码评估、安装或成功取数都不能替代该条件。
