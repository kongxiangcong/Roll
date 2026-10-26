# 02 官方日线来源契约核实 — 2026-10-20

调查基线：`907431842dca6f943868d33cc650ef083f8c82bd`，分支 `codex/roll-capability-expansion`。只读原 `sse_daily.py` / `post_close_packet.py` 及 issue/evidence；未修改产品代码、旧原件、模型、账本或票完成状态。

## 结论

取得新的真实 **2026-10-19、SSE:600362 官方日统计响应**，并重新下载官方 JS，字节 SHA 与旧绑定的 `478fb2a7…` 完全一致。可以补真实原件、所属日期、证券、OHLC及量额的直接展示口径；不能由这些字节证明完整会话、该端点 RAW/调整政策或历史修订规则。02 仍需 partial，不得把本调查当成公开采集/API/页面完整正向验收。

## 可直接绑定的主源与真实下载

1. [官方公司页](https://www.sse.com.cn/assortment/stock/list/info/company/index.shtml?COMPANY_CODE=600362&tabActive=1)的成交统计与[官方 JS](https://www.sse.com.cn/xhtml/home/2021public/querySearch/search_stocksDepositoryReceipts_2021.js) 是该页面查询的直接来源。JS 行 3042—3050 定义 `turnoverParams`，行 4089—4092 将 day 分支绑定到 `COMMON_SSE_CP_GPJCTPZ_GPLB_CJGK_MRGK_C`；行 4136—4139 调用该参数；行 4153—4166 显示 A 股 OHLC 元；行 4184—4213 将 `TRADE_VOL` 绑定 `stockUnit="万股"`、`TRADE_AMT` 绑定万元。这里有端点级单位依据，不借用另一个协议。
2. [固定证券、固定日期请求](https://query.sse.com.cn/commonQuery.do?sqlId=COMMON_SSE_CP_GPJCTPZ_GPLB_CJGK_MRGK_C&SEC_CODE=600362&TX_DATE=2026-10-19&TX_DATE_MON=&TX_DATE_YEAR=) 返回一条记录，`SEC_CODE=600362`、`TX_DATE=20261019`、`DATE_TYPE=D`；OHLC=`39/39.46/38.78/39.09`，TRADE_VOL=`1950.3` 万股，TRADE_AMT=`76300.67` 万元。按既有展示单位精确换算为 **19,503,000 股 / 763,006,700 元**；没有把显示精度扩张为逐笔精度。`queryDate` 空，响应没有逐行公布时刻/修订序号/最终会话标记。
3. `host-capture01/capture-manifest.json` 保存 URL、实际 headers、UTC 接收时刻、完整性、字节数和 SHA；新日统计原件 SHA=`1c4ce7b610ad84b966ebee62c7a29e1490ed5907d2a30607cabc505d1f4abd74`，1147 bytes；JS SHA=`478fb2a72fc5a3725088adb208756e88171f79628956a9f5ca67c900d37def2f`，277193 bytes。

## 找到的更强官方产品契约及其边界

[上证信息智能数据产品说明书 v2.0.0](https://www.sseinfo.com/services/assortment/znsj/znfwnr/c/10790553/files/01e3eccd5e4f41a3a0f960b859fb47e8.pdf) 为 2025-01-03 发布版（本轮保存 152042 bytes，SHA=`4e84bcd09b24fe932ffd43ebb8cc0387391213071bc681478d03483f052ffb90`）。第 4 页 2.2/2.3 明确订阅历史产品含日K线，每交易日盘后18:00以Rsync提供增量，文件结构及接入另见专门说明。它是 **另一个订阅服务** 的约定，没有声称网页 commonQuery JSON 同时具备这些属性；不能据此把网页响应升级为完整日线。此前 2021 v1.1.1 也已下载保存，保留版本差异；新版不再列主参考产品，不能把旧产品列表当当前可用性。

[官方行情历史数据产品页](https://www.sseinfo.com/services/assortment/historical/) 列出日K线、基本信息、快照等服务，业务申请指向 BSP。它没有提供匿名数据文件下载地址、账户凭证或本网 JSON 字段对应声明。尚未申请付费业务、发送联系消息或创建账户；现有最大工程授权不等于已经取得服务凭证。

搜索发现[正式历史数据接口说明书 1.1.4 链接](https://www.sseinfo.com/services/assortment/market/hqywwd/wdzsjk/c/10800481/files/43b75567ae224148bd576acf11d30bd3.pdf)，搜索摘要涉及 `sh1/YYYYMMDD/Day.csv` 及 OHLC、Volume、Amount、科创板盘后分离字段。但本轮实际 HTTP **404**（原件150 bytes、SHA=`d03c9c9c5fef19b7e84125dd79b77167d00e1df5f56da4818992e23e67360bbb`），因此只作后续定位线索，**不是已取得可验收契约**。技术开发稿或搜索摘要也不能代替正式原件，更不能绑定到其他端点。

## 仍缺字段与确切补齐路径

| 要求 | 已有真实依据 | 剩余及下一可执行步骤 |
| --- | --- | --- |
| 单证券、日期、OHLC与量额单位 | 新响应 + 同SHA官方JS | 可由现有解析器离线重放，不提升用途 |
| 完整会话（包含哪些交易阶段） | 网页名义“每日”与收盘字段 | commonQuery端点本身最终状态/交易阶段覆盖声明未取得；另一18:00订阅不能迁移 |
| RAW/调整 | 请求无调整参数 | 不能以没有参数推出RAW；需同端点官方定义，或取得另一有明确价格调整字段的合法来源后做独立适配 |
| 修订与可得性 | 本次实际接收时刻、内容SHA | 不存在公开版本号/修订政策；保存今后变化只能证明后续观测版本，不补造历史公布时刻 |
| 逐笔/大宗/盘后量额纳入范围 | 网页单位与字段绑定 | 缺该统计端点的纳入/排除声明，不能拿 Level-1/2 或年鉴统计定义套用 |
| 替代订阅数据 | v2.0.0/产品页真实原件 | 通过官方 BSP 获取服务凭证、正式当前文件接口及合法样本，再核对RAW/完成/修订；当前无凭证、没有付费授权金额或官方样本，未猜下载路径 |

公司页对网站资料的及时性/准确性/完整性有免责声明；这本身不意味着数据错误，但也没有提供所需端点最终性保证。未将泛化免责声明作为单独拒绝理由；真正剩余的是字段级契约证据缺失。

## 有界执行与失败保留

`plan.json` 先冻结 ≤12尝试 / 120秒 / 16MiB、零自动重试。首次4次在sandbox下均 WinError10013，0 bytes，失败manifest和空prefix保留，已CLOSED_NO_RETRY。随后显式分开host-capture01、host-capture02，各4个固定请求，均有自己的先存plan和终态；前者在已授权网络主机重新执行固定4项，属于 **显式环境修复后的第二次尝试，不是首次成功**。没有重开任何旧P030/CLOSED预算，也没有隐式重试。总计12次客户端尝试，8次实际HTTP响应（7×200、1×404），730032 bytes，执行累计21.25秒；首次拒绝、后续host下载全过程均保留。

所有HTTP body、headers及失败详情见三份 `capture-manifest.json`；sha为解压后的所存body字节，原响应Content-Encoding单独保留。工具web检索用于定位/阅读元资料，未作为本地原件或已消费市场数据。

本研究没有METHOD数据，也没有生产API写入、完整日线验收、模型拟合、账户事件、资格或前向起点。真实材料可补，原门槛所缺契约仍缺。

## 后续补查：BaoStock 原有来源可提供另一条正向日线路径

上述“仍缺”针对 SSE 网页 JSON。02 的既定范围优先复用 CNEquity/BaoStock，并不要求只接受这个 JSON。继续核查 **已有 BaoStock 来源** 后，取得明确的供应商本源契约；可以对同证券、已完成日期另行做 PUBLIC 有界真实验收，SSE 原件仍保留未准入。此结论尚未代替实际取数/API/页面/重放的验收。

`baostock-docs/plan.json` 单独冻结仅文档6请求/60秒/8MiB、无自动重试。官网SPA两个HTML只含外壳；从所引用 `/assets/index-DUQ-MKvt.js` 实际定位到其读取文档的 `POST /helpdocs/api/markdown/{file}`，请求体 `{}`。没有猜私有数据端点，没有行情请求或安装库。三份正文均HTTP200：

| 官网入口与直接读取契约 | 本地正文 | SHA256 |
| --- | --- | --- |
| [平台介绍](https://www.baostock.com/mainContent?file=home.md) / [正文接口](https://www.baostock.com/helpdocs/api/markdown/home.md) | `04-home.md.raw` | `6a931ebea4ff858c46cf89e6c8f448b755cceab10071a35265b576ff09545884` |
| [A股K线](https://www.baostock.com/mainContent?file=stockKData.md) / [正文接口](https://www.baostock.com/helpdocs/api/markdown/stockKData.md) | `05-stockKData.md.raw` | `2a6db3b24ab21a199aa17bd949dfbe545d3279007bea1664854f9b7c20542aac` |
| [复权因子](https://www.baostock.com/mainContent?file=factorInfo.md) / [正文接口](https://www.baostock.com/helpdocs/api/markdown/factorInfo.md) | `06-factorInfo.md.raw` | `6820224b59a62b5e96b3347e0342263f0f9fb448a00a5c4ce1e61d2857b8984b` |

正文接口需要POST，不应把浏览器直接GET返回行为当文档不存在。六次请求及原件/headers/时间/SHA，全部见该子目录 `capture-manifest.json`。供应商本源和交易所本源身份分别记录，不冒称 BaoStock 是交易所权威或与另一供应商具有独立上游。

**契约判断：** 平台正文给出当日17:30完成日K入库、18:00完成因子入库。K线说明将日频 `d` 与不复权 `3`、交易日期、OHLC人民币元4位、成交数量股及金额人民币元4位直接绑定到 `query_history_k_data_plus`；`tradestatus=0/1` 区分停牌/正常，停牌存在前收平价、零量额占位。其 `preclose` 在除权日可以是交易所除权参考值，不能当昨日RAW收盘；实际回报若使用它需遵循旧处理边界。因子说明是另一个接口的分派日/算法，不是日K修订链或来源不修订保证。以上都是该供应商自己的字段定义，不从论坛、第三方仓库或SSE其他协议移植。

**现有 adapter 足够的部分：** `backend/src/roll/market/baostock.py:135` 已校验对象、adjustflag=3、日期范围、重复日期、状态枚举、缺值、OHLC、量额均价范围、停牌非零量额；只在交易日期早于实际接收上海日期时标 `COMPLETE_REPORTED_HISTORICAL`，今日仍 `UNCONFIRMED_CURRENT_DAY`。昨日10/19在今日10/20取数已经跨过其每日入库时刻，适合做**当前取得的已完成日 RAW 日线用途**。既有 source_facts 注册保留 `historical_revision_proof=NOT_AVAILABLE`，status完整性false、listing_stage及ex-rights未知，不提升03/04。

**需要父代理验收时确认的差量：** 将新契约的内容SHA与公开响应/回执/页面对应起来，明确保存供应商当前版本而非历史当时版本，保留修订未知。现adapter `daily` 对 trade=1 且 volume=amount=0 的分支没有单独拒绝条件（量额交叉检验只在 v>0 时做）；在声称符合02“无量额不自动升级”前，需要适用边界测试/消费端核对，不能只凭旧 `model_daily_input_allowed` 一位布尔值关闭。量额纳入哪些市场交易阶段尚无更细供应商声明，按 **provider daily accumulated turnover** 有界口径展示，不能冒充交易所逐笔全市场统一口径。

**修订与历史PIT：** 未找到官网为上述日K提供可回取历史版本的修订API、无修订承诺或精确首次公布时间。当前真实原件、实际接收和SHA足以保存“本次取得的供应商版本”；不支持严格历史时点资格。如02被解释为必须证明永久不修订/当年原版，仍不够，但这不应把允许当前历史版本的既有用途一并封死。先按原02用途及ADR0004区分，审查时精确记录限制。

继承旧票19 [BaoStock验收](../../../../roll-p0/evidence/19/baostock-acceptance.md) 的真实909天RAW/状态/socket存证与零联网重放，可避免重建原服务；该旧证据有自己的日期/范围，不能冒充这次新查询。此次仅补权威文档，未请求任何市场数据，未关闭02。
