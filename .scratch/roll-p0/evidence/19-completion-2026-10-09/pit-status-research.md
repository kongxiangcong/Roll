# 600362 历史发布版本与交易状态公开取证

本轮实际归档 **12 份公开 HTTP 响应**，共727,155字节，12个唯一SHA256，逐件长度/哈希复核差异0。原件与实际接收时点在 [.roll-data/pit-status-public/manifest.json](.roll-data/pit-status-public/manifest.json)，核验在 [verification.json](.roll-data/pit-status-public/verification.json)，逐项资格判断与原值在 [assessment.json](.roll-data/pit-status-public/assessment.json)。本轮无需Fuyao/BaoStock，未读取数据库、封存分片、标签、账号或密钥，未训练、改票状态、购买、外部联系或提交代码。

结论：取得了可以补强已知停牌区间的**交易所直接查询依据**和一条官方历史日统计；尚未取得2013—2025完整历史RAW日线的首次公布版本/更正链，不能据此通过全部历史时点与完整状态门禁。这是本次实际覆盖的结论，不能宣称整个互联网绝对不存在免费档案。

## 实际取得的交易所直接依据

按[公司详情页](https://www.sse.com.cn/assortment/stock/list/info/company/index.shtml?COMPANY_CODE=600362)直接引用的[官方JS](https://www.sse.com.cn/xhtml/home/2021public/querySearch/search_stocksDepositoryReceipts_2021.js)，成交统计请求使用 `commonQuery.do`、`sqlId=COMMON_SSE_CP_GPJCTPZ_GPLB_CJGK_MRGK_C`、`SEC_CODE`、`TX_DATE`。没有依赖第三方接口列表、猜测SQL或访问内部接口。JS声明量为万股、金额为万元、A股价格为元，不能套用市场总貌的亿股/亿元单位。

| 试取 | 实际结果 | 可用范围 / 不能推出的结论 |
|---|---|---|
| [2013-01-04](https://query.sse.com.cn/commonQuery.do?sqlId=COMMON_SSE_CP_GPJCTPZ_GPLB_CJGK_MRGK_C&SEC_CODE=600362&TX_DATE=2013-01-04&TX_DATE_MON=&TX_DATE_YEAR=) | HTTP 200，`result=[]`，509字节 | 该请求没有得到旧日数据；不是2013当天没交易或停牌的证明，也未确定全部接口历史下界 |
| [2025-12-31](https://query.sse.com.cn/commonQuery.do?sqlId=COMMON_SSE_CP_GPJCTPZ_GPLB_CJGK_MRGK_C&SEC_CODE=600362&TX_DATE=2025-12-31&TX_DATE_MON=&TX_DATE_YEAR=) | HTTP 200，1行，开50.25、高55.28、低50.24、收54.92；量12884.52万股，额700504.14万元 | 可用于当前公开官方回溯值核对；响应没有首次公布时刻、旧发布版本ID或更正链 |
| [旧停复牌接口，2016-02-16](https://query.sse.com.cn/sseQuery/commonQuery.do?sqlId=COMMON_SSE_XXPL_JYTS_TFPXX_L&SEARCH_DATE=2016-02-16&isPagination=true&pageHelp.pageSize=100&pageHelp.pageNo=1&pageHelp.beginPage=1&pageHelp.endPage=1&pageHelp.cacheSize=1) | HTTP 200，清单78/78行，包含600362 | 是交易所对已知连续停牌区间的直接依据；单日清单不证明13年全期每日状态完整 |
| [新停复牌接口，2013—2025范围](https://query.sse.com.cn/commonSoaQuery.do?sqlId=GW_PL_JYTS_TFPXX&productCode=600362&startStopDate=20130101&endStopDate=20251231&isPagination=true&pageHelp.pageSize=100&pageHelp.pageNo=1&pageHelp.beginPage=1&pageHelp.endPage=1&pageHelp.cacheSize=1) | HTTP 200，`result=[]`、`pageHelp.data=[]`但`total=10` | 返回数据与元信息不一致，不能解释为全期没有停牌，不假装取得10个事件 |

旧停复牌接口是[停复牌官方页面](https://www.sse.com.cn/disclosure/dealinstruc/suspension/)直接引用的[官方查询脚本](https://www.sse.com.cn/xhtml/home/2021public/querySearch/search_tradeTip_2021.js)所用端点。原件SHA为`2511be0a1a618edfd7576563bdbffcc35c697b9e5ebeb9edc81ff9efa2aa01a8`。600362行原值：

```json
{"PRODUCT_CODE":"600362","PRODUCT_NAME":"江西铜业","CONTROLTYPE":"TR","STOP_REASON":"重要事项未公告","STOP_DATE":"-","SHOW_START_DATE":"2016-02-16","SHOW_END_DATE":"2016-02-26","STOP_TIME":"自2016-02-16起连续停牌","BULLETIN_TYPE":"3"}
```

本行给出事件日期DATE精度，没有原发布钟点；`STOP_DATE="-"`不得补造时间。发行人[2016-002停牌公告](https://static.cninfo.com.cn/finalpage/2016-02-16/1201981143.PDF)与[2016-004复牌公告](https://static.cninfo.com.cn/finalpage/2016-02-26/1202000598.PDF)已在前轮归档，后者正文明确2016-02-26复牌。两种原始记录一致支撑停牌开始与复牌边界，但不是全期无其他事件的证明。实际HTTP接收时点只是2026年本次取证时点，不能写成2016本系统已经取得。

## 官方日线与已归档搜狐响应的冲突

只对公开原字节的2025-12-31一行做离线口径核对，没有读取研究数据库或计算标签。搜狐既有原件SHA为`6d05337bb417e4c5ea88856b9e58604721c28310da48bad28a05f48fdadf47e1`，新SSE日统计原件SHA为`a51334316a941c30047614138f201d3dd3d988a453fa754b8673ae1fd74bb113`。

- 四个价格完全一致；搜狐1288452手×100与SSE12884.52万股一致。
- 金额发生未解决冲突：搜狐700504.19万元、SSE700504.14万元，差0.05万元（500元）。保存双方原值；未平均、未挑有利值、未推断哪方曾更正或为何差异。
- 同一交易所上游经不同渠道传播，不自动构成两个独立原始依据；此处是官方数据核对和传播路径交叉检查，独立性并未证明。

历史输入需要的必需字段若冲突未处理，应记录阻断理由。即使OHLC一致，也不能由一条2025官方回溯响应推出2013—2025的RAW首次发布版本均已证明。

## 剩余路径与确切限制

[SSE官方数据产品页](https://english.sse.com.cn/markets/dataservice/products/)本轮实际归档，说明历史资料日发行、年度订阅、CSV，最早覆盖1990-12-19。它指向正式订阅与订单渠道，公开说明没有同时给出免费全期文件、首次发布版本和完整修订档案。本轮没有申请购买或联系供应方。前轮上证信息产品/接口说明书证明产品存在，不能代替实际数据。

[发行人公告页](https://www.jxcc.com/announcement.html)本轮实际归档，目录含证券变动月报和公告版本；页面年份选项包含2026—2017及2010，未显示2013—2016选项。目录不等于这些年份没有公告。证券变动月报主要补股本变化，不能直接补A股每日ST与停复牌状态。既有年报风险字段及股票简称、公告关键词零命中，也不能证明每日没有其他风险警示。

新发现的另一条历史发布版本线索是**有当期版号和报纸日期的原版行情表**：[中国证券报2013-01-23 A19原版PDF](https://epaper.cs.com.cn/zgzqb/images/2013-01/23/A19/CGG0080123C.pdf)搜索索引标出“本表交易数据由上海证券交易所提供”；[2013-02-27 A18 Market data PDF](https://epaper.cs.com.cn/zgzqb/images/2013-02/27/A18/CGG0080227C.pdf)也有沪深证券市场行情表。报纸自身原版可以证明某个出版版的内容，仍要实际取得核对600362行、业务日期、字段单位、版权/来源与修订关系。12个端点预算已满，本轮**未下载这两份PDF**；web打开第一份失败，未由此断言原HTTP不可访问。已将精确线索发给主进程，后续只应在有界的新阶段验证样本，再决定是否扩展，不能在没有字节时把搜索摘要当入库数据。

停复牌旧接口值得进一步按日核对：本轮已证明已知日期清单可实际取得且分页总数一致。扩展为全期资格之前，还需验证旧年度实际留存下界、全部交易日覆盖、分页/空清单语义、风险警示另外的直接记录，以及历史发布/修订情况。可以按预登记保守政策编码未知状态和限制适用范围；不能把缺失自动改为NORMAL，或看结果后按输赢删样本。

## 边界与核验

本轮web搜索/打开共35项，未越过40项上限；专门HTTP取证12次，达到预设12端点停止点，最大响应277,193字节，总727,155字节，远低于每件64MiB/总256MiB。所有专门取证均HTTP 200，但HTTP成功不等于数据完整、独立或PIT合格。12个原件均重读并核对SHA256与长度，差异0。只有本研究文件、取证脚本/清单及公开原字节新增，生产代码、票状态、模型、账户和封存访问记录均未改。

## 第二阶段：原版报纸字段核对（固定特征和NEXT_OPEN保持不变）

根据主进程追加范围，另执行25项web搜索/打开和8次专门HTTP取证的独立有界阶段，总响应3,565,907字节、7个唯一SHA（两个76字节404响应内容相同），逐件长度与SHA差异0。6个HTTP 200原件及2个404失败响应全部保留，见 [.roll-data/pit-newspaper-fields-v2/manifest.json](.roll-data/pit-newspaper-fields-v2/manifest.json) 与 [verification.json](.roll-data/pit-newspaper-fields-v2/verification.json)。4份PDF解析与抽取哈希在 [extractions.json](.roll-data/pit-newspaper-fields-v2/extractions.json)；2013整版、2018/2024表头另离线渲染检查。旧PDF解析器给出对象偏移/字典重复键警告，原件未修复或改写，未将解析成功冒充原字段资格。

主进程已另取得中证报2013-01-23 A19样本，600362收24.55、高24.80、低24.25、成交笔数12228、金额32261万元。成交笔数不是成交股数，表内没有开盘价；本研究据此寻找能补固定输入字段的另一原版，未从成交笔数或金额猜测股数、未调整原候选特征或NEXT_OPEN事件。

| 实际取得的版面 | 日期/版本事实 | 原版字段结果与限制 |
|---|---|---|
| [证券时报2013-01-23 C010](https://epaper.stcn.com/paper/zqsb/page/1/2013-01/23/C010/20130123C010_pdf.pdf) | 737,036字节，1页；版面明确2013-01-23，行情业务日2013-01-22；SHA `a9f9f717e43ed477052b12ed3819c4dd7e32aea54906c5a753cf2c481951f541` | 600362行收24.55、每笔成交1077股、换手0.63%；表头明确**每笔成交(股)**，不是当日总量；整版没有开盘价列。不能用1077乘中证报12228笔造出精确总量，因为平均每笔已取整数，来源覆盖也未核实一致 |
| [证券时报2013-01-23 C009](https://epaper.stcn.com/paper/zqsb/page/1/2013-01/23/C009/20130123C009_pdf.pdf) | 741,587字节，1页；市场总貌/主要指标；SHA `9535cb44fb17db1fb014ba05c09e23df242fa1da2d6632d7433451a51afae396` | 有市场合计股数、黄金开盘价等，但没有600362行；其他对象的成交量/开盘不能移用给600362 |
| [证券时报2018-08-21 A012](https://epaper.stcn.com/paper/zqsb/page/1/2018-08/21/A012/20180821A012_pdf.pdf) | 734,582字节，1页；版面2018-08-21、业务日2018-08-20；SHA `6dc36fe1f329ece0f0025fdd38e3026d74afc04ec931ab1a5fe1dedfbb518194` | 当页未定位600362；日行情表头仍是收盘价、升跌、每笔成交(股)、换手率、动态PE，没有个股开盘价或每日总量列。搜索摘要声称存在开盘价/高低价/总量，实际文本和渲染不支持，未采信摘要 |
| [证券时报2024-12-12上海网络版](https://static-web.stcn.com/upload/2024/1213/15/675be6c6d653d17e0c84.pdf) | 1,084,679字节，1页；版面印刷日期2024-12-12，URL/文件创建修改时间为2024-12-13；SHA `be33ea23f64f23ec05712771ad3e9fb2a6528d5dd0efc87c99d1887f266c36dd` | 当页未定位600362；表头仍是收盘、升跌、每笔成交(股)、换手率、动态PE，没有开盘/日总量。搜索摘要声称含两列，实际原件不支持；URL/元数据晚于版面日，不能把本文件当前版本自动当作12月12日已可得原字节 |

以上3个年代的日行情样本没有给出所需“600362日总成交股数+开盘价”组合，因此**尚不能启动全期按日报纸扩展并认为能完成固定特征/NEXT_OPEN训练**。这只是在所取版面上的字段缺失判断，并未证明其他版面、年份或档案渠道都不可行。收盘等原事实仍有交叉取证价值；单页都正常的证券简称不能证明其余日期无风险警示。

当期目录也已实际归档：[证券时报完整目录](https://epaper.stcn.com/paper/zqsb/html/2013-01/23/node_1.htm)、[中证报目录](https://epaper.cs.com.cn/zgzqb/html/2013-01/23/node_17.htm)均HTTP 200，版面PDF由目录定位；上证报 [node_1](https://paper.cnstock.com/html/2013-01/23/node_1.htm) 和 [node_2](https://paper.cnstock.com/html/2013-01/23/node_2.htm)均HTTP 404，失败字节已存，不借其他网站转载冒充发行者原版，也不据两处404宣称上证报全部历史材料不存在。

另找到[上交所2015-12-28通关测试通知](https://big5.sse.com.cn/site/cht/www.sse.com.cn/ipo/rules/others/c/c_20210514_5463624.shtml)，正文说明向会员及市场参与者经单向卫星发送`mktdt00.txt`、`show2003.dbf`等行情文件，并明确该次是模拟测试，基础为2015-12-31清算后数据。这证明当时文件发布机制存在，**不是免费真实交易历史档案**，更不能把2016-01-01测试行情导作真实日线。搜索未定位能公开按2013—2025日期下载这类真实文件及修订链的样本。

本阶段已到8原件和25项web停止点，没有启动Internet Archive CDX。可另在授权有界阶段查询当期新浪/搜狐/腾讯历史响应的CDX索引并实际取得一份归档payload；索引捕获时间须与市场事件/完成时间分开，索引存在也不代表原字段全部覆盖，且不得重定向live后冒充旧归档。已将此边界与样本字段限制反馈主进程。

## 第三阶段：实际历史行情原字节，而非仅CDX索引

根据主进程新的有界取证任务，读取其已经取得并校验的 [public-archive-index-receipts.json](public-archive-index-receipts.json) 第一个索引：`hq.sinajs.cn/list=sh600362`，索引原字节5,748字节、SHA256 `2980981f7bd4e6a503b8256dc67789ee52ac1835a6a7d722437e618cd5bdcbf9`，包含2015—2025按月collapse后的44个capture。这个44是该特定URL查询的稀疏结果，不是所有新浪quote捕获总数。原URL含http/https以及明确的`:80`变体，均按原URL构建`https://web.archive.org/web/{timestamp}id_/{original}`，不跟随重定向，不回退live。

现已实际取得并解析**40个不同capture正文，对应40个不同业务日（2015-03-27—2023-09-26）**，其中32条原业务时钟在15:00或之后，8条盘中或盘前。40份wire正文SHA1全部与CDX摘要相符，所有原字节SHA256/长度复读差异0。4份响应的`Content-Encoding:gzip`最初不能直接GB18030解码，现保留wire原件并离线有界解压解析，wire与解压正文各有独立SHA，未改写原件或重新请求来解决字段解析。见 [sina-archive-quote-analysis.json](sina-archive-quote-analysis.json)、[sina-archive-verification.json](sina-archive-verification.json)。

| 原字节实际样本 | 原文业务时钟（Asia/Shanghai） | 可证明和不能证明的内容 |
|---|---|---|
| [2015-05-26 capture](https://web.archive.org/web/20150526131935id_/http://hq.sinajs.cn/list=sh600362) | 2015-05-26 15:04:02 | 原quote包含开24.20、当前24.44及高低/成交量/金额；capture为13:19:35Z。能界定该capture记录了此版本，不能将capture当首次公布，尚无交易日历与完整修订链资格 |
| [2019-06-06 capture](https://web.archive.org/web/20190606010802id_/http://hq.sinajs.cn/list=sh600362) | 2019-06-06 09:07:24 | 原开盘0、成交量0；盘前报价不可直接当收盘RAW日线，不能用SDK的零值回填昨收规则替原文造出交易开盘价 |
| [2023-03-17 capture](https://web.archive.org/web/20230317094630id_/http://hq.sinajs.cn/list=sh600362) | 2023-03-17 15:00:00 | 开18.550、高18.840、低18.530、当前18.720、原量15023111。与当前新浪日K该日OHLCV逐字段相同；这支持这一个旧版本的字段交叉核对，并未证明两时点之间没有其他更正 |

每份解析记录保留original URL、capture UTC、requested/received UTC、完整HTTP headers、wire字节长度/SHA256、CDX摘要核对、原业务日期与时钟、原字段串及尾部字段。`original_publication_at`保持null；接收时刻是2026年研究时的本地接收，capture是档案捕获时刻，业务时钟是quote自身市场日期/时间，三者没有互相覆盖。**2021-11-02样本有1秒时钟冲突**：capture为02:17:15Z，而正文10:17:16+08；原精度各到秒，负差原样保留，不加一秒修复，也不拿它作严格同秒可得性的证明。

初次44目标的receipt阶段取得20份，24个网络断连失败；主进程随后授权每个已知失败仅1次、20秒/2MiB/max4的独立重试。重试取得20个HTTP200原响应（16个直接解析、4个gzip经离线解析），原失败保留并链接`retry_parent`，4条原44列表仍断连：2023-05-24、2024-08-17、2024-10-02、2025-03-18。另`hq.sinajs.cn/?list=sh600362`精确CDX取得两条2017-03-22/2018-01-17的索引，但两份实际payload均断连。**这6条是未取得payload，不能写成没有历史数据**。见 [sina-archive-payload-receipts.json](sina-archive-payload-receipts.json) 和 [sina-archive-payload-retry-receipts.json](sina-archive-payload-retry-receipts.json)。

过程限制也保留：最初收集器对原URL`:80`的白名单过严，抛`UNEXPECTED_TARGET`而未输出完整receipt；修正明确原URL变体后重跑同一44目标。因此44+26是有receipt的目标尝试数，**不是全部wire尝试总数**，首次中止前的部分尝试没有完整ledger。此阶段没有新增股票、全站通配或live fallback；最终可持久核验的50条响应记录共715,733字节、48个唯一SHA、唯一原体596,659字节。没有把这项过程缺陷隐藏成一次完美收集。

### 第一方日K URL调查与8个定向CDX边界

实际归档[新浪600362行情页](https://finance.sina.com.cn/realstock/company/sh600362/nc.shtml)、其引用的[sf_sdk.js](https://finance.sina.com.cn/sinafinancesdk/js/sf_sdk.js)、stock20180116.js，以及按SDK模块加载器的点转斜线规则取得的[datas/k.js](https://finance.sina.com.cn/sinafinancesdk/js/datas/k.js)。错误的`datas.k.js`请求404也记入discovery receipt，随后依据实际源码更正路径，未从三方接口大全冒充官方定义。

当前第一方CN源码把quote第8字段除100作为`totalVolume`，第9字段作为`totalAmount`；datas/k.js日K合并CN quote时再乘100。源码可支持“该候选原量字段按股使用”的当前解析约定，也明确另列复权URL，但**当前SDK的约定不是2013—2025历史schema冻结版本证明，也不是完整未复权/权益链证明**。原字段32当前SDK具有停牌状态解释，本次40份尾部均`00`，仍未据此把全部历史状态改成NORMAL；风险警示和缺失日期继续未资格。

第一方datas/k.js的CN历史日K模板为`http://finance.sina.com.cn/realstock/company/$symbol/hisdata/klc_kl.js?d=$rn`，复权另指`/realstock/newcompany/$symbol/p$dirfq.js`。对600362专有`klc_kl.js`路径的CDX前缀查询（包含日期query变体、2013—2025、最多80条、按年collapse）HTTP200原文`[]`。这只是不命中该具体归档查询，不是证明整个新浪历史档案不存在。

第一方分钟K模板为`money.finance.sina.com.cn/quotes_service/api/jsonp_v2.php/$cb/CN_MarketData.getKLineData?symbol=$symbol&scale=$scale&ma=no&datalen=1023`，callback含动态毫秒。为避免广域JSONP前缀扫描，另实际请求并取得两个具体公开JSON日KURL的HTTP200原字节：

- [money.finance固定600362 URL](https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol=sh600362&scale=240&ma=no&datalen=1023)
- [vip.stock固定600362 URL](https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol=sh600362&scale=240&ma=no&datalen=1023)

两份当前响应原字节完全相同，各107,242字节、1023行，首2022-07-18、尾2026-10-08；它们不能作为两个独立来源或历史PIT版本。2023-03-17与2023-09-26两条旧quote的OHLCV均与当前日K相同，比较结果保存在analysis JSON。没有把当前1023行回填成当时发布的日K。

本阶段8个定向CDX索引请求全部留痕：上述klc路径1个、`/?list`精确1个、money/vip固定JSON各1个全期、全期失败后各拆2013—2019与2020—2025共4个。结果2个索引成功；6个JSON日K索引查询分别超时、断连或HTTP503（失败正文归档），**没有拿索引失败判定无capture**，也没有继续广域通配越过8请求边界。见 [sina-kline-discovery-receipts.json](sina-kline-discovery-receipts.json)、[sina-kline-index-receipts.json](sina-kline-index-receipts.json)。其中一次公开URL读取shell调用在执行前自动审批超时，按工具允许规则原样重试一次后成功；该超时不代表数据授权风险。

### 本阶段对ticket 19材料缺口的精确影响

“完全没有任何历史发布版本原字节”现在已被实际40份有摘要吻合的归档quote反例消除；这些记录适合作历史版本样本、单位/字段研究和未来冻结的数据来源证据。但取得的业务日彼此稀疏，仍没有连续21个所需交易日的当时日线版本，盘中/盘前quote不能填成收盘日线；也没有完整状态/权益/correction链或足够CAL0样本。当前回溯1023日K不能解决每个历史观察时点的可得性。因而不能据本批直接训练原固定4特征或宣布满足NEXT_OPEN、独立校准和模型冻结。没有改窗口/阈值/候选特征，没有按涨跌筛选，未访问实际DB/SEALED/标签/账号或拟合模型，票状态和生产代码未改。

本阶段没有把40个业务日逐一与已经归档的完整SSE交易日历核对，因此**不报告任何已日历资格的最长连续完整收盘序列/run数**；32个15时后只能称名义收盘后的quote候选，不能称32个合格收盘。缺口结论仅为未实际取得连续21个所需交易日的历史版本。1秒负差记录也不会被修正或用于强时间门禁。原8索引边界已到，当前具体外部阻塞是6条quote payload断连、3次固定日K索引超时、1次固定日K索引断连及2次HTTP503；原错误和503原体已归档，研究结束本阶段，不继续泛搜。
