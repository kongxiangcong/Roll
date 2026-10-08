# 有限市场取证与归档契约（07）

宿主 `EvidenceStore` 是真实 SQLite、可靠原始文件和规范化 Parquet 的唯一写入者。`DataRequest` 先经06当前名单/固定背景检查，再产生 `RetrievalRun`。取数前重新检查当前成员；外部材料只能作为数据。11/12可使用相同请求与结果，不能直接写账、签发资格或把模型回答当成通过检查的事实。

## 请求与运行

`POST /api/data/requests` 返回201以及不可变 `request_id`。输入：

```json
{"instruments":["SSE:600519"],"groups":["DAILY","QUOTE","ADJUSTMENTS","ANNOUNCEMENTS","PERFORMANCE","MAJOR_EVENTS","STATUS"],"purpose":"OBSERVATION","start_date":"2026-01-01","end_date":"2026-09-30","daily_source":"TENCENT","required_fields":[],"max_calls":30,"timeout_seconds":60}
```

对象需明确交易所与六位代码。`purpose` 为 OBSERVATION、RESEARCH 或 BACKGROUND；背景仅预固定指数的 DAILY/QUOTE，不取得股票研究或交易能力。06的20只限制属于新增关注，**真实持仓请求无20只硬上限**。调用预算耗尽仍保存全部请求对象并逐对象/组列出 TECHNICAL_LIMIT。BSE保留名单和请求，但本票来源未适配，产生明确 SOURCE_SCOPE_NOT_ADAPTED_BSE。

`cutoff` 可选，需带时区，默认实际请求时点；它限制事件日期/上游报价，不证明后来获取的历史事实曾在过去可得。`required_fields` 支持公共字段或 `DAILY.amount_yuan` 等组内字段；缺失产生 REQUIRED_FIELDS_MISSING，不静默补齐。`daily_source` 股票默认EASTMONEY、背景默认TENCENT，或显式选择本票支持的primary；背景显式选EASTMONEY返回422，不静默换源。没有自动换源/重试，08负责换源与用途资格。`max_calls`1—30、`timeout_seconds`1—60，单响应最多16MiB；数量含原文JSON/PDF，每个 HTTP 请求计一次，超时/大小有界，无递归。

请求保存所需对象、用途、日期/时区截止、必需字段、技术限制、06的账户/名单版本及对应已确认身份；不传账户资金、持仓数量、授权或凭据给上游。调用 `POST /api/data/requests/{id}/retrieve` 建立关联的新运行，GET同路径读取请求。运行包含 backend=DIRECT_HTTP、model=null、config_fingerprint、实际 httpx/pyarrow/pypdf 版本、适配代码指纹、evidence_kind、实际起止/工具URL与状态/原件指纹、缺口、snapshot_id。COMPLETE表示本次获取处理完成，**不表示字段、当前状态或模型资格全已满足**。部分事实+缺口为PARTIAL，无事实为FAILED；重启发现未提交快照的RUNNING标INTERRUPTED，不伪装成功。取消/模型任务隔离由11—13联验。

## 归档与事实

每个实际响应先写 `ROLL_DATA_DIR/raw/<sha>.raw`，flush/fsync、替换并核验SHA，随后登记引用。原文PDF完成可靠归档和解析后才能形成对应原文事实。规范化Parquet也先可靠归档，再以短SQLite事务同时发布快照与最终运行。原件缺失/损坏 GET与replay返回409。原始文件及SQLite均保留版本，不能在线替换历史输入。

事实包含 instrument、group、来源ID/URL、raw_hash/revision_id、received_at/available_at及依据、适用交易日/披露日期、字段单位/口径及局部质量/缺口。JSON数值先以Decimal保留原token再存字符串。财务 `TOTAL_OPERATE_INCOME` 保存为 **total_operating_income_yuan（营业总收入）**，不能与营业收入混称；报告期、披露日、供应商索引时间分开。DATE字段保持日期，供应商合成午夜不成为发布时点。`published_at`未知为null；provider_display_at/indexed_at属于供应商时钟，未证明原始交易所发布时间。报价 upstream_at逐证券保存，实际获取时间不掩盖9/30行情在10/08仍为旧报告。

`available_at` 是本机真实收到原响应的时点，不能回填历史。requested_cutoff早于首次收取时 `point_in_time_input_allowed=false`，同日仅DATE披露为 UNKNOWN_DATE_ONLY_SAME_DAY；历史输入是当前修订的重构材料，缺乏无修订/PIT证明。RESEARCH快照 namespace=HISTORICAL，只记录真实现在获取，不伪造过去RetrievalRun/StageSnapshot/预测/前向覆盖。

`point_in_time_input_allowed` **仅针对原DataRequest.cutoff**，不是事实永久资格。默认请求先记录cutoff再取数，首次available_at晚于它，false是正常结果。08/17/25应以实际消费/预测自己的知识截止重新核验原available_at、对应事件/上游时点与用途必需字段；现在已取得的事实可以在后来的消费截止下被读取，不能被伪装为原请求之前可得。事件截止、原请求截止和消费知识截止分别保存。该核验也不把当前供应商修订自动升级为历史无修订/PIT证明。

原价RAW用于原价事实，与 FORWARD_CURRENT_VERSION 严格区分，以原件SHA标当前复权版本。腾讯缺qfqday不能退day；日线最多800行。腾讯历史成交额一般未返回，只在同档embedded quote的日期/OHLC/成交量均数值相等时取field35绝对元额，其他日保留缺失，不用最新额回填。当前仅实证已确认 SSE MAIN普通股票成交手数转股（×100）并核对成交额/OHLC；STAR、其他身份/市场、指数单位保留UNKNOWN/reported，不按代码前缀猜。零成交保留ZERO_REPORTED，不能据此推定停牌；价格0占位为缺失，amount缺失不补零。日历休市/未知、同日UNCONFIRMED_CURRENT_DAY、OHLC/单位错误分别标记；未完成或缺必需量额的完整日线模型输入受限。没有授予任何量化模型资格。

当前真实股票异常状态 UNKNOWN。旧报价报告的上下限价格有来源时点，不确认当前风险警示/停牌/上市阶段。五种明确固定状态（正常、停牌、风险警示、除权、未知）仅经注入测试传输进入 METHOD_CASE，其模拟时点和依据明示；生产JSON报价不能接受此夹具格式，也不覆盖06实际UNKNOWN或模型资格。

## 查询、观察与覆盖

- `GET /api/data/runs` 最近100运行，含失败；`GET /api/data/runs/{id}` 精确原运行。
- `GET /api/data/snapshots/{id}` 不可变快照；`GET /api/data/snapshots?instrument=&group=&available_before=` 按实际可得时点过滤，未来取得的事实不会进入过去知识查询。
- `GET /api/data/coverage?instrument=&group=` 逐快照/组实际首末日期、返回行数/来源总数、截断、evidence_kind与获取时点。来源总行数不是已取得深度，单页公告/业绩不是全历史。17/19需据实际覆盖选择研究范围，不能宣称封存最终测试已通过。
- `GET /api/data/observations?instrument=` 保留 snapshot_id/run_id、依赖原件、事件日期/精度、实际observed_at、严重程度、FACT或DETERMINISTIC_INFERENCE、未知/待核项与名单/账户版本。公司事件为已披露客观事实；分派仅待券商核对。除息日价变化和已披露税前现金分派形成明确上下文，不能标普通暴跌或自动入账。简单现金分派调整不是完整总收益验证。
- `GET /api/data/archives/{sha}` 指纹校验原件/Parquet；`POST /api/data/runs/{id}/replay` 验全部原件，并从原Parquet读取与SQLite比对，同输入/结构结果，network_calls=0，不重新发布动作/通知。
- `GET /api/data/sources` 固定来源、权限/深度/单位/修订局限。无需密钥公开请求成功只证明实际小范围可达，不证明商业再分发许可、所有市场覆盖或长期稳定。

页面在既有五入口的“持仓与关注 → 市场事实”。对象选择包括全部持仓、固定背景与所有请求缺口；归档运行可查看原响应/PDF、转换、日期、质量、覆盖和客观观察。后台取证占用外部HTTP线程，账户确认仍通过原账本用例。

## 责任边界与组件

07提供同版本原件/事实/观察与范围信息。08负责用途新鲜度、可比换源、修订依赖失效；14负责关键复盘独立性/冲突；15负责按需/盘后覆盖与客观风险入口；11/12分别验真实后端，13验工具安全/取消，后续模型票复验必需输入。它们均未由07样例替代完成。

DSA固定 `ce364e457aab288863a5707e7b3df79786ad07f2` 的 [tencent_fetcher.py](https://github.com/ZhuLinsen/daily_stock_analysis/blob/ce364e457aab288863a5707e7b3df79786ad07f2/data_provider/tencent_fetcher.py)、efinance_fetcher.py与base.py，分类为**仅参考请求/字段设计，未复制Python实现**。原许可 [MIT](https://raw.githubusercontent.com/ZhuLinsen/daily_stock_analysis/ce364e457aab288863a5707e7b3df79786ad07f2/LICENSE)，Copyright (c) 2026 ZhuLinsen；不继承补OHLC/零额、全市场报价、qfq缺失退day或科创板代码单位假设。Roll独立使用实际响应验收映射，不引入DSA配置/补丁、pandas、numpy、efinance、tenacity、exchange-calendars。新增实际依赖仅 httpx0.28.1、pyarrow25.0.1、pypdf6.19.0，uv.lock锁定；无泛化采集、插件、供应商平台或新审批流程。

2026-10-08 用户新增凭据：可显式选择扶摇，接口、时点/量额/公司行为边界见[扶摇来源契约](fuyao-evidence-contract.md)；原记录和默认来源保持，不能以新来源连通宣称历史PIT或真实19模型通过。
