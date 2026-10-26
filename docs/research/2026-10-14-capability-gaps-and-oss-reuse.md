# Roll 能力缺口与 GitHub 组件复用评估

审计日期：2026-10-14（Asia/Shanghai）。结论：保留 Roll 的账户、来源归档、影子与资格内核，优先复用数据接口、文档解析、统计及报告组件；不整仓迁入另一套投研或交易平台。

这是能力审计和选型建议，不是实施规格、任务状态变更或接入验收。已搜索并审阅二十余个候选仓库/官方文档，但不能声称穷尽 GitHub。没有安装依赖、下载模型、训练模型、调用收费数据或发送通知。GitHub 和公开文档的只读请求不属于行情接口验收。

本地快照 HEAD：`fe5d01c7d7af7da9a74354cbaf0ce8455450971c`。审计同时看了工作区：已有 app.py、collection_sources.py、README、任务记录等修改和未跟踪 sse_daily.py，不将未提交代码误认为已验收；没有改动这些文件。实现环境为 Python >=3.12、FastAPI、React、SQLite/Parquet。

## 1. 实际缺口：区分未建模块与未完成证据

| 能力 | 当前已具备 | 真正缺口及类别 | 对最终目标的影响 |
| --- | --- | --- | --- |
| 行情、状态、公司行动 | 多源采集、原件、清洗、冲突与修订、CNEquity/BaoStock适配、后台采集 | **P0未闭合**：用途合格的完整DAILY/session、有效状态、行动身份/版本/履行及旧义务依据 | 直接影响真实预测归档能否启动；增加一个库不自动补全证据 |
| 回测和连续影子 | 历史标签与成交模拟、固定政策、费用、连续资金/持仓、基线和重放 | **已有但未收口**：后继政策完整经济/统计协议、验证和生产派发；通用任意策略研究界面不是当前已交付能力 | 不缺另一套回测内核，缺固定候选的完整运行闭环 |
| 概率模型 | 真实历史量价候选训练、校准拟合和工件冻结；四项量价特征 | **证据缺口**：独立校准有效性、完整确认性和前向验证；目前不是财报/新闻联合模型，也未证明可推广到任意股票 | 不能因模型能输出数值就称可信买卖概率 |
| 深度财报分析 | 部分业绩字段、公告JSON/PDF、报告期与披露时间 | **新增能力**：完整三表、单季/累计/TTM口径、同比、盈利与现金流质量、债务、重述版本、行业适配和可解释分析 | 对综合投研有价值；完整基本面模型超出现有最小量价P0范围 |
| 新闻事件与情绪 | 名单内公告/业绩/重大事项的来源基础 | **新增能力**：稳定新闻输入、正文、转载去重、证券相关性、事件对象、中文分类、情绪序列及效果检验 | 情绪分类置信度不能当收益事件概率；第一版并未要求无边界新闻流 |
| 文档理解 | pypdf、有限页数文本、完整原件保存 | **新增能力**：复杂表格/OCR、跨页、单位/脚注/页码定位与勾稽 | 可用专门解析器减少大量重复工程 |
| 统计验证 | Brier/AUC/可靠性箱、成对区块区间、G1—G7框架 | **已有但待独立验证**；成熟统计库可用于交叉核验/后继实现 | 不应写成“没有统计模块”；库无法补足样本或确认方法假设 |
| 研究报告 | 分开真实/历史/影子/账户条件结果、曲线和文本报告 | **体验增强**：更成熟的绩效图、回撤/月度收益报表 | 很适合轻量直接复用，不必换回测引擎 |
| 持续运行、通知、正式动作 | 独立worker、租约、备份恢复、站内通知、外部配置 | **P0未闭合**：动作有效期、LOSS恢复规则、实际外发配置/验收、全链交付；并非没有调度或通知模块 | 不需要为“持续跟踪”先引入另一套分布式调度系统 |

本地依据：

- [最新工程账本](../../.scratch/roll-p0/execution-status.md)、[10月14日验收剩余责任](../../.scratch/roll-p0/evidence/continuation-2026-10-14/acceptance.md)。20/25/27/30/31仍有明确未闭合责任；32—34真实起点/终点/资格未成立。
- [真实采集最新摘要](../../.scratch/roll-p0/evidence/cnequity-integration-2026-10-10/collection-log/2026-10-14T122227Z-summary.json)：该收据记591事实版本、150归档、2个真实记录交易日、29个背景日；`COLLECTING / system_usable=false / NOT_GRANTED`。这是采集覆盖，不是两天已归档预测。此处读取保存收据，没有连接运行中数据库。
- [模型特征](../../backend/src/roll/research/models.py)、[重建范围](../../backend/src/roll/research/reconstruction.py)：四项量价，真实重建范围600362，显式排除财报/新闻/情绪输入。
- [影子引擎](../../backend/src/roll/research/shadow.py)、[后继影子](../../backend/src/roll/research/successor_shadow.py)、[统计](../../backend/src/roll/research/statistics.py)、[验证](../../backend/src/roll/research/validation.py)、[报告](../../backend/src/roll/research/reports.py)。
- [业绩/公告解析](../../backend/src/roll/market/source_facts.py)、[CNEquity契约](../cnequity-data-contract.md)、[worker](../../backend/src/roll/worker.py)。未跟踪sse_daily.py也明确保留`model_daily_input_allowed=false`，不能据新文件认定来源责任完成。
- [ADR0001](../adr/0001-default-engineering-route.md)、[ADR0002](../adr/0002-on-demand-analysis-and-coverage.md)、[ADR0003](../adr/0003-automated-validation-review.md)、[ADR0004](../adr/0004-reconstructed-price-volume-research.md)：模块化单体、按需/盘后、确定性资格、重建研究边界；不整套引入多角色交易裁决。

## 2. 优先推荐：复用组件，不替换产品

“直接复用”指组件可以通过Python API调用，并非已在本机完成兼容验收。“低/中/高”是相对适配成本，不是交付天数承诺。

| 项目 | 对应缺口和可复用入口 | 复用方式/成本 | 必须保留的边界 |
| --- | --- | --- | --- |
| [AKShare](https://github.com/akfamily/akshare) | 三表、财务指标、单股新闻；`stock_profit_sheet_by_report_em`、`stock_balance_sheet_by_report_em`、`stock_cash_flow_sheet_by_report_em`、`stock_news_em` | **优先试点，适配后复用，中**；MIT，所选公开接口一般无需token | 返回DataFrame不等于有原响应证据；需在请求边界保存原件。现有东财和AKShare东财不算两个独立来源；新闻接口有最近条数限制，不是历史完整库。[官方接口文档](https://akshare.akfamily.xyz/data/stock/stock.html) |
| [Docling](https://github.com/docling-project/docling) | 公告/财报PDF结构、表格和OCR；`DocumentConverter` | **优先试点，组件直接调用、中**；代码MIT、模型单独核对 | 独立解析进程，锁定模型/版本；保存页码、位置和单位，不能用OCR猜测覆盖原值 |
| [QuantStats](https://github.com/ranaroussi/quantstats) | 净值绩效图、回撤、月收益、HTML报告；`stats`、`plots`、`reports.html` | **最容易获得展示收益，直接调用、低至中**；Apache-2.0 | 输入仅使用Roll已保存收益与基准序列，不调用自动下载；缺失日期、年化、现金流和费用由Roll先定口径 |
| [scikit-learn](https://github.com/scikit-learn/scikit-learn) | 概率校准与评分的成熟实现，`calibration_curve`、`brier_score_loss`、`log_loss`，后继候选可评估校准器 | **直接调用、低至中**；BSD-3-Clause，本地运算无需服务账号 | 先独立核对现有计算；不能默认随机交叉验证，更不能静默替换已冻结拟合/截距校准。[官方校准文档](https://scikit-learn.org/stable/modules/calibration.html) |
| [arch](https://github.com/bashtage/arch) | `MovingBlockBootstrap`、`StationaryBootstrap`及区间；用于当前自写区块计算的独立参照 | **直接调用、低至中**；作者宽松许可含保留声明/不背书要求，API的SPDX为NOASSERTION | 明确日历分组、缺失、同日多证券、区块长度、区间和随机实现；数值不同须解释，不能自动覆盖旧实验。[方法文档](https://bashtage.github.io/arch/bootstrap/bootstrap.html)、[许可证](https://github.com/bashtage/arch/blob/main/LICENSE.md) |
| [Trafilatura](https://github.com/adbar/trafilatura) | 已归档新闻HTML→正文/元数据；`extract(..., with_metadata=True)` | **直接调用、低至中**；当前Apache-2.0（旧版本许可不同） | Roll自行有界获取并先存原件，再离线抽取；抽出的日期不等于首次发布或实际接收时刻 |
| [datasketch](https://github.com/ekzhu/datasketch) | `MinHash` / `MinHashLSH`发现转载与近似重复 | **组件直接调用、低至中**；MIT；小量先用规范化hash，无需急于引入LSH | 相似不是同一事件；保留每个来源，不能把修订公告/数字变化误删。分词、阈值和索引版本要固定 |
| [valuesimplex/FinBERT](https://github.com/valuesimplex/FinBERT) | 中文FinBERT2、`Fin-labeler/sequence_inference.py`，金融文本分类 | **条件性候选，中**；仓库MIT，所选情绪checkpoint许可/可下载性未完成确认 | 先验证是否有适用微调权重；SC_2是二分类示例，不自动得到中性/不相关类。需要中文样本、否定句/事件对象/拒判评测，不能直接上线或把输出当买卖概率 |
| [Tushare](https://github.com/waditu/tushare) | `pro.income/balancesheet/cashflow`，报告期、公告及更新字段 | **有权限时适配复用，中**；SDK BSD-3-Clause，数据服务另需token/积分/接口权限 | 不承诺免费或完整历史版本；必须核对实际账户能取到的响应。[官方利润表说明](https://tushare.pro/document/2?doc_id=33) |

重要源码发现：QuantStats 的 [reports.py](https://github.com/ranaroussi/quantstats/blob/main/quantstats/reports.py) 默认`match_dates=True`会dropna，并按首个非零收益调整开始日；[utils.py](https://github.com/ranaroussi/quantstats/blob/main/quantstats/utils.py)还有收益预处理。因此不能“传入序列即可认为符合Roll证据口径”。选用固定完整窗口；未知区段单列；核对零收益/缺席不被抹掉。绩效报告中的胜率也不等于经过校准的未来事件概率。

## 3. 已有复用、备选与不建议当前整合的项目

| 项目 | 结论与原因 | 许可证/依赖依据 |
| --- | --- | --- |
| [CNEquity](https://github.com/rootSunc/CNEquity) / BaoStock | **已经在用，先完善当前适配**；CNEquity固定版本隔离运行，BaoStock已在pyproject。不要重复建设数据湖/时钟/worker | CNEquity Apache-2.0；现有范围与实测见本地契约；SDK许可不授予上游数据权利 |
| [Alphalens-reloaded](https://github.com/stefan-jansen/alphalens-reloaded) | **多证券因子研究时再引入**；`get_clean_factor_and_forward_returns`和`create_full_tear_sheet`可评估IC/分组/换手；当前单标的固定候选不应硬套截面分组 | Apache-2.0；必须记录清洗丢样本，不把事后收益用于特征 |
| [Qlib](https://github.com/microsoft/qlib) | **后续独立研究环境候选**；因子、模型和实验组织有价值，当前整体迁入重复建设。其PIT存储支持不代表拥有合格历史PIT数据 | MIT；本次README明确官方数据集暂时停用，指向社区数据。不能当免费、完整、可验证A股数据源 |
| [skfolio](https://github.com/skfolio/skfolio) | **将来组合优化才考虑**；提供组合优化/风险和交叉验证。当前问题不是缺另一套持仓优化器 | BSD-3-Clause；不得让优化器覆盖用户资金授权 |
| [GS Quant](https://github.com/goldmansachs/gs-quant) | **统计/风险参考，暂不整体接入**；当前重点偏A股现金账户，衍生品定价能力收益有限 | Apache-2.0；高盛API需要相应机构访问权限；本地函数与服务访问分开 |
| [vectorbt](https://github.com/polakowo/vectorbt) | **快速离线策略探索备选**，不替换正式成交/影子内核，不开放无登记的大量试验 | [当前许可](https://github.com/polakowo/vectorbt/blob/master/LICENSE.md)是Apache-2.0加Commons Clause，不应称纯宽松开源 |
| [Backtesting.py](https://github.com/kernc/backtesting.py) | **小型教学/独立对照备选**；更换引擎仍需A股费用、权益及执行适配，当前收益不抵迁移成本 | AGPL-3.0，依具体集成/分发方式检查义务 |
| [RQAlpha](https://github.com/ricequant/rqalpha) | A股场景相关，**独立回测对照候选**；当前不整体替换 | [LICENSE](https://github.com/ricequant/rqalpha/blob/master/LICENSE)区分非商业Apache-2.0与商业授权，不能简单当纯Apache许可；数据另核对 |
| [OpenBB](https://github.com/openbq-org/OpenBB) | 多数据源整合平台；Roll已有API/证据/界面，当前整体接入增加层次，**不优先** | 原OpenBB-finance链接本次跳转openbq-org；README称Apache-2.0，但API为NOASSERTION，集成前需逐组件看LICENSE。服务/数据权限独立 |
| [FinRL](https://github.com/AI4Finance-Foundation/FinRL) | 强化学习研究框架，**不补当前关键缺口**，会扩大训练、模型和执行假设 | MIT；README现将原仓定位教育/研究并指向FinRL-X，不把示例称已验证收益模型 |
| [FinGPT](https://github.com/AI4Finance-Foundation/FinGPT) | 金融LLM研究备选；当前轻量分类+现有Codex取证更小，**不先自训大型金融模型** | 代码MIT；基座、LoRA、数据各自许可 |
| [RSSHub](https://github.com/DIYgod/RSSHub) | 某些站没有RSS时的**可选发现服务**，不是新闻模块必需项；财经路由本次未运行 | [当前LICENSE](https://github.com/DIYgod/RSSHub/blob/master/LICENSE)为AGPL-3.0；具体路由可能需要浏览器/账户，不默认配置 |
| [MinerU](https://github.com/opendatalab/MinerU) | 中文复杂表格解析**对照候选**，先与Docling比较实际公告 | [当前许可](https://github.com/opendatalab/MinerU/blob/master/LICENSE.md)为Apache基础加商业规模/在线服务等附加条款，模型另核对 |
| [feedparser](https://github.com/kurtmckee/feedparser) | 官方RSS/Atom存在时可直接解析，**轻量候选**；未在本轮完成所选版本的完整许可/依赖审计 | 只解析Feed，不能补全文、金融实体和情绪；避免引入RSSHub只为解析现有RSS |
| [finance-report-analyzer](https://github.com/lt91888/finance-report-analyzer) | 仅借鉴取数/指标组织；小仓、分析主要靠SKILL，**不选为核心财报引擎** | MIT；不是已经验证的财报口径体系 |

既有 [组件核查](../alignment/component-evidence.md) 已指出 daily_stock_analysis 的缺失补零、默认复权及换源口径问题；本次沿用该本地审计作为历史风险记录，未对其最新HEAD重新做全审，不能称当前所有版本都存在同一问题。LangAlpha/ai-hedge-fund也不作为整仓替换路线。

## 4. 最省重复工程的接入顺序

### A：先解决当前概率闭环的阻塞

先将30所需字段逐项映射到既有CNEquity/BaoStock/官方来源；新增AKShare或有权限的Tushare只解决明确缺字段，不能凭换源跳过验收。同时完成20/25完整后继协议/验证/派发、动作有效期以及27恢复规则，之后推进合法真实归档。这个阶段不依赖新闻模型或通用回测平台。

验收重点：日期/证券/单位、RAW与复权、分页截断、状态未知、行动更正/取消、原响应归档及离线重放。完整来源无法证实时列出字段与原因，不继续无边界换工具。

### B：财报观察 MVP

AKShare三表 → Roll财报事实/版本 → 确定性财务指标与原件链接；PDF表格不足时才用Docling。先支持当前目标证券适用行业，不泛称全行业财报分析。

最小验收：同一报告期累计和单季不混用；单位万元/元准确；重述不覆盖旧值；财报发布日期与报告期分开；资产负债基本勾稽；负利润/零分母/缺失不生成假比率；原文页码可追溯。财报输出先用于事实观察，不自动改变量价模型。

### C：新闻事实优先，情绪随后

AKShare指定股票新闻或官方Feed → Roll原件 → Trafilatura正文 → 精确hash去重，必要时datasketch近似去重 → 证券/事件绑定 → 中文FinBERT2候选评测 → 分版本情绪序列。RSSHub仅在明确来源缺RSS且对应路由可用时引入。

最小验收：不同网站转载不重复计数；公告更正保留；一篇报道对供应商/客户可能方向不同；中性、不相关、否定和不确定有处理方式；仅使用当时收到的内容；预训练时间污染不伪称历史未知；情绪输出不直接映射BUY/SELL。

### D：绩效展示与计算交叉核验

QuantStats只消费已归档完整收益序列；scikit-learn/arch以隔离诊断参照开始。记录Roll值、参照值、口径差异，不改冻结工件。若决定替换数值实现，应登记后继版本及影响，不覆盖旧实验、失败记录或尝试额度。

### E：确有新增研究需求再上框架

多股票因子用Alphalens-reloaded，候选研究管理可试Qlib，组合优化再试skfolio。它们不作为当前真实启运的额外前置，也不要求全部安装。

## 5. 接入结构与必须由 Roll 保留的部分

建议沿用现有源码结构：取数适配放在market边界；文档/文本模型用独立依赖环境或子进程；统计和报告消费归档输入，结果回到research。外部组件不直接写账户账本或签发CapabilityGrant。依赖版本、模型和新派生字段有独立指纹，不改变旧可重放工件。

仍需要Roll自有实现的薄层：证券与来源身份、首次接收/披露/报告期/修订关系、财报口径、事件对象与去重策略、数据用途准入、资金与成交事实、完整实验/尝试账本、G1—G7资格。这些是产品语义，不能由通用库默认值代替。

任何框架都不能补造历史首次可得证据、代替真实未来样本、证明概率有效、授予资金权限。财报和新闻新增后还需要独立增量价值检验；新候选登记必须保留既有家族失败、关联和共享尝试预算，不能借换库重新计数。

## 6. 维护状态快照与证据层级

下表来自本轮无凭据读取GitHub REST `https://api.github.com/repos/<owner>/<repo>`。日期是`pushed_at`的UTC日期，不是正式发布日、默认分支最后代码更新或质量保证；成功返回者`archived=false`。未锁定候选commit，实施前仍须选定版本。

| 仓库 | pushed_at日期 | API许可证标识 |
| --- | --- | --- |
| ranaroussi/quantstats | 2026-09-27 | Apache-2.0 |
| bashtage/arch | 2026-10-12 | NOASSERTION；已单读许可 |
| scikit-learn/scikit-learn | 2026-10-14 | BSD-3-Clause |
| microsoft/qlib | 2026-10-08 | MIT |
| stefan-jansen/alphalens-reloaded | 2026-10-13 | Apache-2.0 |
| kernc/backtesting.py | 2026-08-05 | AGPL-3.0 |
| ricequant/rqalpha | 2026-10-14 | NOASSERTION；已单读限制 |
| skfolio/skfolio | 2026-10-14 | BSD-3-Clause |
| AI4Finance-Foundation/FinRL | 2026-10-13 | MIT |
| goldmansachs/gs-quant | 2026-10-13 | Apache-2.0 |
| openbq-org/OpenBB | 2026-10-12 | NOASSERTION |
| rootSunc/CNEquity | 2026-10-08 | Apache-2.0 |
| akfamily/akshare | 2026-10-13 | MIT |
| waditu/tushare | 2024-03-13 | BSD-3-Clause |
| docling-project/docling | 2026-10-14 | MIT |
| opendatalab/MinerU | 2026-10-14 | NOASSERTION；已单读附加条款 |
| DIYgod/RSSHub | 2026-10-14 | AGPL-3.0 |
| AI4Finance-Foundation/FinGPT | 2026-09-23 | MIT |

vectorbt元数据请求SSL失败、FinBERT请求超时，不编造近期维护；其仓库/许可/README已另读。其余轻量候选只做页面审查，未核实最近提交时间。Tushare SDK仓库较旧不等于服务停止；反之近期push也不证明接口稳定。

证据层级：本地源码/已存验收审计完成；公开官方文档/部分关键源码/许可证评估完成；候选安装、Windows/Python3.12兼容、真实来源响应、模型权重可用性、准确率、性能和生产效果均未验。不能把推荐写成“直接接入已通过”。数据/财报/中文情绪的详细引用另见[候选审计](2026-10-14-oss-data-news-candidates.md)。
