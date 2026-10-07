# 用途检查、换源与原输入重放（08）

本票沿用 [DataRequest / RetrievalRun / 原始归档契约](data-evidence-contract.md)。`quote_source` 可显式选择 `TENCENT` 或 `SINA`；默认仍为腾讯。统一事实保留实际源、原字节 SHA、精度、单位和首次 `available_at`，两条路径并不因此获得独立来源资格。

`POST /api/data/requests/{request_id}/resolve` 接受 `usage`、`use_cache`、`allow_fallback`、可选 `basis_run_id`、`revision_of`、带时区的 `knowledge_cutoff`，返回 HTTP 202 和 RUNNING 记录。用途为 PRE_MARKET_RECORD、POST_MARKET_RECORD、CURRENT_MONITORING、HISTORICAL_RESEARCH、NEW_RISK。`GET /api/data/resolutions/{id}` 查询完成、失败或进程重启后的 INTERRUPTED；单宿主同时只接受一个补查，忙时返回409，不占用账户确认事务。

实际适配备源仅为 Eastmoney/Tencent 日线和 Tencent/Sina 报价。必需字段不足或分组失败时，最多一次备源尝试，调用和耗时沿用原请求总预算，零重试。07直接取数原运行可作为 `basis_run_id`，先验 SHA/Parquet，再补查；补查不刷新原事实时间。所有持仓请求对象保留（包含21+），预算不足逐对象显示缺口。公告等未适配备源的组明确保留缺口。

切换保留逐字段原值和比较：对象及供应商声明交易所、请求交易日、RAW/qfq、调整版本、缺字段、Decimal 数值均核验。RAW 与 qfq 不拼接，不同供应商的当前 qfq 调整版本不可默认为等价，字段冲突阻断。报价成交量未知时保持 reported/UNKNOWN，禁止按代码或名称猜手/股。实际已核验的 Sina 股数映射仅适用于明确 SSE MAIN STOCK 身份；依据是供应商网页及其原 parser 文件（登记在 registry 的 conversion_basis），其他范围保持 UNKNOWN。Sina普通股原股数3833098与腾讯reported38331精度不同；08未将后者外推成3833100再假称两源股数相同。

消费知识截止默认是本次检查完成时的实际系统时间，或调用者提供的不晚于现在的带时区截止。事实须 `available_at <= 本次消费知识截止`；原请求的 `point_in_time_input_allowed` 只针对原 request.cutoff，不能永久否定后来已取得事实。原请求事件/报价上游截止继续生效。历史材料只在明确请求日期范围内读取，实际后来取得仍不能回填历史可得。闭市/盘前日线与报价按已核验交易所日历选择交易日；不设置全材料通用分钟TTL。日历UNKNOWN保留局部限制；报价日期陈旧则当前监控受限，历史读取保留真实旧日期。

HEALTHY只表示本用途所需归档事实可读。DEGRADED保留已知部分，UNKNOWN状态、未适配材料及缺金额/单位不被补值。当前监控要求每个请求对象都有对应当前交易所时段、有效价格与必需字段的报价；仅存在一只报价或价格占位0不能声称整个范围可监控。complete_daily_model是输入完整性标志，不是模型资格；缺完整日线字段时 BLOCKED_NEW_RISK。NEW_RISK在后续动作新鲜度和模型资格联验前持续阻断；08不授予交易、模型、approved或技能资格。

缓存重新核验原件 SHA 和 Parquet，重新评估本次用途/知识截止，网络调用0；wrapper时间仅描述读取行为。`use_cache=false` 取得新关联运行，并以已完成同请求指纹原记录或显式 `revision_of` 登记修订。normalized字段、调整语义、状态或文件原内容变化产生修订依据；接收时点与相同原件再获取本身不等于事实修订。响应本次缺失不冒充源已撤回。

后继记录与依赖失效在同一短SQLite事务发布。改变/补录事实使原用途评估失效；已存在 Observation 的 basis_raw_hashes 引用改变原件时，也登记失效。GET原记录/observations显示 CURRENT/INVALIDATED，原事实与当时观察值不改写。原件级依赖是保守范围，可能同时限制引用同一整份响应的多个观察；真实研究/预测/动作模型的消费登记及重新资格检查在11/13/19/25联验，不宣称已覆盖。

`GET /api/data/dependencies?resolution_id=...` 查询失效记录。`POST /api/data/resolutions/{id}/replay` 验证全部原输入归档 SHA/Parquet并持久化 ReplayRun；`GET /api/data/replays/{id}` 查询。ReplayRun返回原事实、观察、原用途状态/新鲜度/缺口/知识截止及当前依赖状态，网络调用0。它重现保存的原结构化解释，不用新代码联网重新覆盖旧输入；更新和再生成须新运行。原07版本档案仍按其保存版本离线验证。

只参考 LangAlpha `941ca4a18f5a364caf481a6f78cdb040086aa38d` 的稳定输入ID、版本与依赖方法（Apache-2.0，见 component-evidence）；未复制其代码、运行时、技能或资格语义，未增加依赖包。
