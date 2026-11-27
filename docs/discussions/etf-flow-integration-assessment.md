# 宽基 ETF 净申赎报表接入评估

本文保留数据核查和送审前的页面设想；正式命名、页面归属和实施范围见[阶段 06 方案](../design/roll-v3-research-pipeline/06-market-workbench.md)。

**建议在 Roll 的「信息」页面下提供完整的 ETF 净申赎报表，以逐基金份额和净值复算，用上游在线报表对照。** 2026 年 11 月 26 日首页的 **+112.10 亿元** 可以复算。它回答的是这组基金的份额合计增加了多少价值。逐笔申赎人身份、中央汇金当天买卖金额和流入个股的金额都超出这些字段的识别能力。510300 的 2025 年报确实列出中央汇金资产管理有限责任公司为年末持有人，这份证据的粒度是特定时点的持仓。[首页](https://wwww1998.github.io/national-team-etf-flow/) · [510300 年报 §9](https://www.sse.com.cn/disclosure/fund/announcement/c/new/2026-03-31/510300_20260331_W6CZ.pdf)

## 2026 年 11 月 27 日复核

以提交 `c713dea5` 固定首页和数据缓存。对首页清单中的每个代码，用 11 月 26 日份额减去 25 日份额，乘以从天天基金重新取得的 26 日单位净值，最后合计并换算为亿元。35 只均有两日份额与重新取得的同日净值，当天均未触发脚本的份额变动超过 30% 这一折算判定前提。[固定提交](https://github.com/wwww1998/national-team-etf-flow/tree/c713dea55647abe2dd90cde853bd0ee1ba191382) · [份额缓存](https://raw.githubusercontent.com/wwww1998/national-team-etf-flow/c713dea55647abe2dd90cde853bd0ee1ba191382/_etf_shares_cache.json) · [取值与折算实现](https://github.com/wwww1998/national-team-etf-flow/blob/c713dea55647abe2dd90cde853bd0ee1ba191382/refresh.py#L704-L725)

| 11 月 26 日 | 相邻两日份额差（亿份） | 当日单位净值（元／份） | 复算净申赎额（亿元） | 首页（亿元） |
| --- | ---: | ---: | ---: | ---: |
| 510300 沪深300ETF华泰柏瑞 | +1.782 | 3.9741 | +7.0818462 | +7.08 |
| 159915 创业板ETF易方达 | +21.01 | 2.2048 | +46.322848 | +46.32 |
| 首页 35 只合计 | | | **+112.0964733** | **+112.10** |

以上是一次对发布数字的算法核对。固定提交没有首页 35 只的净值快照，另一份宽基净值缓存中 123 个代码的最后净值日均为 11 月 23 日。完整复算借助了之后仍可查询的同供应链净值。因此可以解释首页数字，但仅凭这个 Git 提交无法重放其全部输入，也无法确定 26 日盘后何时首次齐备。[固定宽基净值缓存](https://raw.githubusercontent.com/wwww1998/national-team-etf-flow/c713dea55647abe2dd90cde853bd0ee1ba191382/_broad_nav_cache.json) · [天天基金 510300 净值序列](https://fund.eastmoney.com/pingzhongdata/510300.js) · [天天基金 159915 净值序列](https://fund.eastmoney.com/pingzhongdata/159915.js)

## 两份报表怎么读

| 页面 | 实际证券池和 11 月 26 日读数 | 可支持的问题 |
| --- | --- | --- |
| [原项目首页](https://wwww1998.github.io/national-team-etf-flow/) | 35 只，按作者分为 12 类，当日 +112.10 亿元。23 只基础篮子加 12 只作者后来纳入的产品。 | 哪些跟踪产品驱动这个特定篮子的净申赎？ |
| [宽基对照页](https://wwww1998.github.io/national-team-etf-flow/broad.html) | 123 只，按 8 个宽基指数分组，当日页面公布 +109.97 亿元。 | 几个宽基之间的净申赎方向是否一致？ |

两份清单逐代码交集为 28 只。若要比较共同指数中的其他基金，应先按基金代码和实际跟踪指数确定共同范围、去重，再逐只计算。例如，563800 确为广发中证 A500 ETF，固定版本的 123 只清单却未收录。首页现金额与宽基页现金额直接相减，差值包含两个方向的成分差异。[首页清单](https://github.com/wwww1998/national-team-etf-flow/blob/c713dea55647abe2dd90cde853bd0ee1ba191382/refresh.py#L143-L191) · [宽基清单](https://github.com/wwww1998/national-team-etf-flow/blob/c713dea55647abe2dd90cde853bd0ee1ba191382/refresh_broad.py#L143-L215) · [上交所 563800 公告](https://etf.sse.com.cn/disclosure/ssenotice/c/c_20261118_10838132.shtml)

**指数归类存在可核验的错误。** 首页把 159949 标为嘉实的创业板 ETF，归入与创业板指 399006 联动的一栏。华安的申赎清单将该代码列为华安创业板50ETF，拟合指数 399673。11 月 26 日该只基金的 +3.63 亿元因而进入了错误的指数小计。全篮子合计通过复算，仍须用交易所或管理人资料校验逐只身份，才能解释分类结果。[上游名称、分组和指数映射](https://github.com/wwww1998/national-team-etf-flow/blob/c713dea55647abe2dd90cde853bd0ee1ba191382/refresh.py#L154-L201) · [华安申赎清单](https://www.huaan.com.cn/etf/159949/sgshqd.jsp)

**历史证券池也有可得时间。** README 仍写 23 只，首页脚本硬编码 35 只。脚本注释记载新增品种的筛选参考了 11 月 2 至 4 日的平均净申购，随后回补历史份额。若以今天的 35 只回测筛选日以前的表现，会把后来才知道的入选结果带入过去。可从当时已知的成分与名单披露日重建证券池，或把整段明确标为按现有名单回看。[README](https://github.com/wwww1998/national-team-etf-flow/blob/c713dea55647abe2dd90cde853bd0ee1ba191382/README.md) · [名单与筛选说明](https://github.com/wwww1998/national-team-etf-flow/blob/c713dea55647abe2dd90cde853bd0ee1ba191382/refresh.py#L143-L174) · [新增品种历史回补](https://github.com/wwww1998/national-team-etf-flow/blob/c713dea55647abe2dd90cde853bd0ee1ba191382/refresh.py#L545-L563)

## 数据访问、更新与缺值

- **输入和发布物。** 刷新程序通过 AKShare 读取沪深交易所份额和天天基金单位净值，沪市最新份额可能采用东财快照兜底。项目公开了两个 HTML 页面和若干份额、净值、K 线缓存。首页脚本在本地生成 `_etf_data.json`，工作流没有将它提交为公共数据接口。首页的刷新按钮只重新加载网页，K 线组件在该发布版本还会请求外部 ECharts 脚本。[采集函数](https://github.com/wwww1998/national-team-etf-flow/blob/c713dea55647abe2dd90cde853bd0ee1ba191382/refresh.py#L465-L543) · [沪市回退](https://github.com/wwww1998/national-team-etf-flow/blob/c713dea55647abe2dd90cde853bd0ee1ba191382/refresh.py#L663-L699) · [页面生成](https://github.com/wwww1998/national-team-etf-flow/blob/c713dea55647abe2dd90cde853bd0ee1ba191382/refresh.py#L1366-L1372) · [发布工作流](https://github.com/wwww1998/national-team-etf-flow/blob/c713dea55647abe2dd90cde853bd0ee1ba191382/.github/workflows/daily-refresh.yml#L34-L57) · [K 线脚本](https://github.com/wwww1998/national-team-etf-flow/blob/c713dea55647abe2dd90cde853bd0ee1ba191382/refresh.py#L1019-L1026)
- **数据日与可用时刻。** 工作流配置北京时间每天 07:45 至 09:30 每 15 分钟一次，另在 16:00、23:00 尝试刷新。页面同步日通常只要求沪深各至少一只有份额，遇两市无共同日期还会退到单边。更新时间取运行机本地时间，同一数据日可沿用旧值。Roll 应保存交易日、可查证的披露时点、实际取得时刻和版本，按冻结截止时点选取可用值。[任务配置](https://github.com/wwww1998/national-team-etf-flow/blob/c713dea55647abe2dd90cde853bd0ee1ba191382/.github/workflows/daily-refresh.yml#L1-L17) · [同步日和时间戳](https://github.com/wwww1998/national-team-etf-flow/blob/c713dea55647abe2dd90cde853bd0ee1ba191382/refresh.py#L747-L779) · [Roll 历史时点原则](../adr/0004-reconstructed-price-volume-research.md)
- **逐日金额的例外。** 缺份额时脚本跳过该日，下次作差可能跨越几个交易日。缺净值时沿用最近可见净值。份额骤变超过 30%、净值反向且两者比例乘积落在 0.6 至 1.6 之间时，脚本将净额置零。汇总只加可算行，部分展示把缺值渲染为零。Roll 复算宜要求连续两日份额和当日净值，折算另核公告。指数和篮子合计同时给出应有数、可算数及缺失原因，避免把部分和读成完整总额。[计算与聚合](https://github.com/wwww1998/national-team-etf-flow/blob/c713dea55647abe2dd90cde853bd0ee1ba191382/refresh.py#L704-L745) · [展示转换](https://github.com/wwww1998/national-team-etf-flow/blob/c713dea55647abe2dd90cde853bd0ee1ba191382/refresh.py#L846-L860) · [Roll 资金流口径](../design/architecture/roll_v3_trading_pipeline_spec.md#54-etf-资金流的数据语义)
- **使用权限。** 核对版本未见许可文件，README 中的用途说明也没有授予复制或再发布权。原站外链可先满足查看需要。计划复制脚本、托管页面或分发缓存时，应分别确认作者授权和原行情、基金数据的使用条款。自行从允许使用的来源取数和实现计算，可以独立推进。[固定仓库文件树](https://github.com/wwww1998/national-team-etf-flow/tree/c713dea55647abe2dd90cde853bd0ee1ba191382) · [GitHub 许可说明](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/licensing-a-repository)

Roll 先前的固定版本复核另有 2025 年历史样例、四只 ETF 的覆盖长度和旧版晴雨表预热条件，可用于后续数据对照。本次复核着眼于当前发布页、当日可复算程度、篮子版本和指数归属。[早期宽基 ETF 复核](../design/data/broad-etf-flow-review.md)

## 工作台的信息页面

工作台设置独立的「信息」入口，按市场主题组织子页面。ETF 净申赎报表、行业信息、观察池信息为同级页面。单只 ETF 的数值放在 ETF 报表内，首页无需承担逐只展示。行业与观察池的具体字段留到各自页面设计时确定。

**ETF 净申赎报表**是首个具体专题。参考在线版的阅读顺序，用户打开子页就能在 Roll 内读到以下内容。[参考报表](https://wwww1998.github.io/national-team-etf-flow/)

1. 篮子口径、数据所属交易日、更新时间、有效成分数，以及当日、近一周、近一月、半年、一年和年初以来的估算净申赎额。
2. 逐日净申赎趋势、篮子资产规模历史，以及可切换跟踪指数的 K 线与对应 ETF 组每日净申赎联动图。资产规模按纳入基金的总份额与净值计算。
3. 按指数、按基金的区间汇总和逐日明细。基金行可核对相邻两日份额、当日单位净值及估算金额。净值迟发、份额缺失和折算不可比都显示具体原因，部分合计标出覆盖数。

**数据与研究的分工。** 信息页读取 Roll 保存的结构化市场数据，用于浏览和核对。采集层保留来源、篮子版本、交易日、实际取得时间和修订记录，同步失败时仍可查看最近完整报表。研究流水线如何主动取得大盘及 ETF 背景，由后续流水线改造决定；用户浏览报表无需选择或传递研究材料。本次评估范围为信息页面与支撑该页面的数据。[Roll 版本与快照](../../backend/src/roll/v3/market.py)

## 现有供应商怎样分工

| 所需字段 | 本次证据 | 建议路由 |
|---|---|---|
| 基金单位净值 | 上海时间 2026-11-27 用项目已配置的扶摇密钥查询公开 GET /api/fund/performance/nav，两只基金均返回 HTTP 200、业务码 0。11 月 25、26 日，510300 分别为 3.9718、3.9741，159915 为 2.1986、2.2048，元／份。11 月 26 日与本次报表复算取到的净值逐一相符。 | 扶摇优先，用 unit_nav 和净值所属日。缺口按需用管理人披露或 Investoday 历史净值核对，单独保留实际取得时间。[扶摇净值契约](https://github.com/Hithink-Tech-Org/Financial-API/blob/main/docs/api/fund/fund-performance.md) |
| 日终总份额 | 扶摇公开基金目录列场内行情、净值及持有人等能力，未查到可外接的历史逐日日终总份额序列；宽基 ETF 净流入接口标为端内专用。Investoday /fund/shares-changes 已有账户实测，510300 的两日份额可复算；同一窗口，159915 在 2025-07-22 的份额差为 +2,000 万份，深交所原表给出 −2,600 万份。 | 逐交易所验收。用交易所日终份额确立日期、单位及折算口径，Investoday 通过对应基金与窗口核验后可承担取数或按需补缺。保留原日期，发生冲突时回查原表。[扶摇基金能力目录](https://github.com/Hithink-Tech-Org/Financial-API/blob/main/docs/api/fund/README.md) · [Investoday 账户核验记录](../design/research/roll_dual_pipeline_review.md#42-两个-etf-的逐日份额给出不同结论) |
| ETF 场内价格与成交额 | 扶摇列有公开场内快照和历史日线，估算申赎只依赖相邻两日份额和当日单位净值。 | 若工作台也需要盘中表现，行情用独立时间戳和单位，日终申赎卡显示最近完整披露日。[扶摇基金行情文档](https://github.com/Hithink-Tech-Org/Financial-API/blob/main/docs/api/fund/fund-market.md) |

本次 Investoday 结论采用项目已有账户实测。此次未另行调用计费接口，11 月 26 日该接口对 35 只基金的覆盖仍待小窗验收。公开网站用于报表设计和结果对照。日常同步按字段选源，一次落库后供信息页展示，也为后续流水线主动读取保留来源和时点。[Roll 数据路由与预算](../design/data/roll-data-capabilities.md)
