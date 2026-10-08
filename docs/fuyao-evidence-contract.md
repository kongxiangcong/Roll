# 扶摇真实来源与研究边界

用户配置 `FUYAO_API_KEY` 后，宿主在固定 `https://fuyao.aicubes.cn` 请求头 `X-api-key` 使用它。浏览器、DataRequest、运行配置指纹、日志、Prompt 和归档不含密钥。密钥缺失保留 `FUYAO_CREDENTIAL_NOT_CONFIGURED`，不发外部请求。若响应原文或JSON解码后反射密钥，宿主在归档前拒绝该响应并保留脱敏错误。沿用原调用、单响应/总字节、期限与取消预算，无重试或重定向。

`POST /api/data/requests` 可选 `daily_source=FUYAO`、`quote_source=FUYAO`、`adjustment_source=FUYAO`（默认仍为 EASTMONEY）；使用现有名单/固定背景、原件先保存、SQLite 快照、Parquet、观察和离线重放路径。页面提供相同选择。每次取数只显式传一个对象；不请求全市场或登录 Cookie，不复制官方 SDK/Skill。

- 日线为 `/api/a-share/prices/historical`，显式 `interval=1d`、上海日期换算的毫秒 start/end、`adjust=none` 与 `forward` 分两份归档。必须核对响应对象、周期和复权，空量额不补零、价格零为占位。公开文档指定股数/CNY；股票检查成交额/股数均价与 RAW OHLC。背景指数使用 `/api/a-share-index/prices/historical`，不传 adjust；指数点位与市场总成交额/股数不作个股 VWAP 比较，不能进入个股模型。
- 报价为 `/api/a-share/prices/snapshot`，背景使用指数域同路径。`data.timestamp` 是响应中最新上游有效时间，不是逐证券时钟；即使单对象请求也未承诺逐证券时点，故保存 `source_snapshot_ready_at` 与其依据，`upstream_at/trade_date/age_seconds` 留 null，显式 `QUOTE_PER_INSTRUMENT_TIME_UNKNOWN`。新鲜报价用途、估值与盘后引用不会把它当已知逐证券报价；原始事实仍可查。状态保持 UNKNOWN，不从名称、非零量或 OHLC 猜正常、停牌或风险警示。
- 公司行为为 `/api/a-share/corporate-actions/adjustment-factors`，股前税现金、送股比例和除权日期分列；毫秒午夜只表达 DATE，不变成披露时间。返回事件不是用户到账，仍待账户核对。记录日/披露时点、完整历史与全部配股覆盖没有证明，不把未返回的事件类型或 null 填零。
- 同时检查 HTTP 与业务信封 `code=0`；code必须为int且不接受bool/string/object，其他形状保留稳定FUYAO_BUSINESS_CODE_INVALID，不向错误记录拼入上游任意文本。2003权限、4001限流即使 HTTP200也失败；源对象错配/调整错配/缺失保留归档和规范化错误，无法规范化的材料不能生成事实。已取得合格部分照常留存。

来源登记、实际范围与权限、版本指纹和环境见[实取验收](../.scratch/roll-p0/evidence/fuyao/acceptance.md)。主契约来源为官方[价格文档](https://fuyao.aicubes.cn/docs/api-reference/prices/)、[公司行为文档](https://fuyao.aicubes.cn/docs/api-reference/corporate-actions/)、[指数文档](https://fuyao.aicubes.cn/docs/api-reference/a-share-index/)及[当次全文](https://fuyao.aicubes.cn/llms-full.txt)。该文档原件SHA留在实取清单中，未把动态文档当固定外部代码依赖。

## 19 与后继协议

实际新增 2023—2026-09-30 的 908 RAW 和 908当前前复权日线、7公司行为；2026股数量额完整的181 RAW日线，三背景各181日线。覆盖长度增加并补齐实际成交额，不能证明历史无修订/PIT、历史交易状态、公司行为全集或以前的交易规则/日历已适配。2023—2025日历规则仍未知；报价逐证券时点仍未知。

19保留原真实120机会/0训练失败、原CAL40最多20成熟标签、每类20及依赖块等冻结条件；没有生成真实模型、校准器、概率、后继协议或前向起点。当前没有支持合法后继协议的必要信息增量：更长量价历史本身无法补历史PIT/状态/完整行为，也不能换窗、调低阈值或把新读原价窗口称为独立最终检验。后继方案只有取得可审计PIT/历史状态/公司行为等必需资料后才可登记，旧尝试预算/失败/UNPROVEN封存状态必须留存；本轮不请求用户设置统计阈值或自然时间等待。
