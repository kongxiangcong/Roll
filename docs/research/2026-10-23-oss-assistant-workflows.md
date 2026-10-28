# 开源投资助研与决策工作流：固定版本源码调查

调查日期：2026-10-23。范围：作者 GitHub 仓库、固定提交源码、README 与许可证；使用 GitHub connector 读取，网页搜索仅用于发现项目。**只读源码，未安装或运行这三个项目，未调用模型或行情服务，未读取密钥或真实账户数据。** 本文证明代码中存在的路径与限制，不证明部署可用、模型有效、A 股数据可靠或具有正式使用资格。未改 Roll 产品、规格、任务状态或预算。

已对齐 [GLOSSARY](../../GLOSSARY.md)、[按需分析 ADR](../adr/0002-on-demand-analysis-and-coverage.md) 和 [自动验证 ADR](../adr/0003-automated-validation-review.md)：模型观点、账户事实、验证结论和能力授权仍是不同对象。

## 结论

三者值得学习的部分不同：**TradingAgents 是带显式缺口的研究辩论与评级工作流；ai-hedge-fund 是将模型意见、确定性组合约束、模拟执行和连续账本分开的研究引擎；TradingAgents-CN 是面向 A 股研究助手的应用工作流参考，但应用层并非开放源码许可证授权。** 这些结论来自下面的固定源码，不代表已跑通或投资表现比较。

尤其不能将三类“回测”混为一谈：TradingAgents 评价独立证券/日期上的评级；ai-hedge-fund 连续演化模拟资金与仓位，但默认模拟成交没有费用、滑点和保证金模型；TradingAgents-CN 检查到的是独立回测服务客户端，不能据此确认社区版具有无需外部服务的完整回测能力。[TradingAgents 回测范围](https://github.com/TauricResearch/TradingAgents/blob/e8f5503e9b86d5c2710b0c76b1f686703968c9df/tradingagents/backtest.py#L1-L15)、[ai-hedge-fund 模拟成交](https://github.com/virattt/ai-hedge-fund/blob/4e1657ddc689e3939c481a8f0955444b10f02dc9/hedge_fund/brokers/sim.py#L1-L12)、[CN 回测客户端](https://github.com/hsliuping/TradingAgents-CN/blob/51060a7682cf51810b4bc3a704829438d18cd8dc/core/backtest/engine_client.py)

## 固定版本与许可

以下时间为 GitHub commit 的 committer UTC 时间，并非运行验证时间。

| 项目 | 固定提交与时间 | 已核验的许可 |
|---|---|---|
| TauricResearch/TradingAgents | [e8f5503e9b86d5c2710b0c76b1f686703968c9df](https://github.com/TauricResearch/TradingAgents/commit/e8f5503e9b86d5c2710b0c76b1f686703968c9df)，2026-10-16 21:38:41Z，v0.7.0 合并 | [Apache-2.0](https://github.com/TauricResearch/TradingAgents/blob/e8f5503e9b86d5c2710b0c76b1f686703968c9df/LICENSE) |
| virattt/ai-hedge-fund | [4e1657ddc689e3939c481a8f0955444b10f02dc9](https://github.com/virattt/ai-hedge-fund/commit/4e1657ddc689e3939c481a8f0955444b10f02dc9)，2026-10-19 17:48:03Z，v2.6.0 | [MIT](https://github.com/virattt/ai-hedge-fund/blob/4e1657ddc689e3939c481a8f0955444b10f02dc9/LICENSE) |
| hsliuping/TradingAgents-CN | [51060a7682cf51810b4bc3a704829438d18cd8dc](https://github.com/hsliuping/TradingAgents-CN/commit/51060a7682cf51810b4bc3a704829438d18cd8dc)，2026-09-22 12:10:31Z，v3.0.0 社区版 | [混合许可](https://github.com/hsliuping/TradingAgents-CN/blob/51060a7682cf51810b4bc3a704829438d18cd8dc/LICENSE#L1-L22)：tradingagents/、cli/、docs/、tests/、web/ 与根配置属于 Apache-2.0；app/、frontend/、core/ 为专有 source-available，声明允许个人使用、评估、教育，限制再分发和商业使用 |

CN 提交说明只写 Apache-2.0，但同一提交的 LICENSE 和 README 已明确分层；应以实际文件界定范围，不以提交标题或仓库标签代替审查。本调查未作外部法律判断。

## 1. TradingAgents：研究报告与评级闭环

### 实际源码路径

输入是证券标识、分析日期、所选分析师和模型配置，可额外传入 portfolio。入口 [main.py](https://github.com/TauricResearch/TradingAgents/blob/e8f5503e9b86d5c2710b0c76b1f686703968c9df/main.py) 调用 [TradingAgentsGraph.propagate](https://github.com/TauricResearch/TradingAgents/blob/e8f5503e9b86d5c2710b0c76b1f686703968c9df/tradingagents/graph/trading_graph.py)，校验日期不能晚于当前日期，建立运行状态、执行图、记录报告和决策记忆。

[图编排 setup.py](https://github.com/TauricResearch/TradingAgents/blob/e8f5503e9b86d5c2710b0c76b1f686703968c9df/tradingagents/graph/setup.py) 的真实顺序为：

1. 市场、情绪、新闻、基本面分析师各自调用工具；所选分析师并行执行，记忆结算也可并行。
2. 等待分析报告后，进入多空研究辩论。
3. Research Manager 汇总为研究计划，Trader 形成提案。
4. 激进、保守、中性风险角色辩论，Portfolio Manager 输出最终评级和论据。

[Portfolio Manager](https://github.com/TauricResearch/TradingAgents/blob/e8f5503e9b86d5c2710b0c76b1f686703968c9df/tradingagents/agents/managers/portfolio_manager.py) 优先采用结构化 PortfolioDecision，失败时回退文本生成与评级解析。输出为 Buy / Overweight / Hold / Underweight / Sell；[propagate 契约](https://github.com/TauricResearch/TradingAgents/blob/e8f5503e9b86d5c2710b0c76b1f686703968c9df/tradingagents/graph/trading_graph.py) 还允许不可解析的 REVIEW。这里的 Hold 可以来自证据过薄，不应在 Roll 中直接解释成有资格的正式 HOLD。

### 数据与缺口

[默认配置](https://github.com/TauricResearch/TradingAgents/blob/e8f5503e9b86d5c2710b0c76b1f686703968c9df/tradingagents/default_config.py#L153-L170) 将价格、指标、新闻主要路由到 Yahoo，财报链为 SEC EDGAR/Yahoo；[router](https://github.com/TauricResearch/TradingAgents/blob/e8f5503e9b86d5c2710b0c76b1f686703968c9df/tradingagents/dataflows/router.py) 对价格、技术、财报、新闻、宏观和事件概率分别配置来源。显式来源列表决定回退顺序，不悄悄加入未配置来源。

[错误分类与路由](https://github.com/TauricResearch/TradingAgents/blob/e8f5503e9b86d5c2710b0c76b1f686703968c9df/tradingagents/dataflows/errors.py)、[router 缺口返回](https://github.com/TauricResearch/TradingAgents/blob/e8f5503e9b86d5c2710b0c76b1f686703968c9df/tradingagents/dataflows/router.py#L176-L298) 区分没有可用数据、供应商不可用、配置缺失。已识别的无数据/不可用可以返回 NO_DATA_AVAILABLE 或 DATA_UNAVAILABLE，并提示模型不要编造；可选宏观/事件数据失败可降级继续；部分未分类核心错误仍抛出。**这不是“任何关键数据缺失都禁止评级”的确定性门禁**，继续生成报告依赖后续模型对缺口的处理。

[Yahoo fundamentals](https://github.com/TauricResearch/TradingAgents/blob/e8f5503e9b86d5c2710b0c76b1f686703968c9df/tradingagents/dataflows/vendors/yahoo/fundamentals.py#L23-L37) 对过去日期拒用没有历史版本的当前快照。因此支持某市场 ticker 并不代表该市场历史基本面完整。实际来源可达性、具体证券覆盖和历史修订证据均未在本机验证。

### 回测与最低运行条件

[run_backtest](https://github.com/TauricResearch/TradingAgents/blob/e8f5503e9b86d5c2710b0c76b1f686703968c9df/tradingagents/backtest.py#L129-L181) 遍历 ticker/date 网格、隔离回测记忆日志、记录单格与结算失败；[汇总](https://github.com/TauricResearch/TradingAgents/blob/e8f5503e9b86d5c2710b0c76b1f686703968c9df/tradingagents/backtest.py#L184-L214) 区分 resolved/pending/unscored。源码明确其不模拟数量、成交价格和现金账本，传入 portfolio 时每格仍使用同一组合上下文。[摘要文本](https://github.com/TauricResearch/TradingAgents/blob/e8f5503e9b86d5c2710b0c76b1f686703968c9df/tradingagents/backtest.py#L108-L125) 明示文本来源未归档且每格仅一次模型采样，指标仅具指示性，不能当连续影子账户业绩或可严格复现的实验结果。

最低依赖：Python ≥3.11、项目依赖、一条可用模型服务路径、所选数据源网络/权限以及可写缓存与结果目录。README 提供托管 API、Ollama 或其他兼容本地服务路径；本地模型虽可减少 API 凭据需求，仍需模型资源和可用数据。核心 Yahoo 路径不以 Alpha Vantage key 为统一前提。以上为配置/安装要求，不是本机成功记录。[pyproject](https://github.com/TauricResearch/TradingAgents/blob/e8f5503e9b86d5c2710b0c76b1f686703968c9df/pyproject.toml)、[README 安装与模型配置](https://github.com/TauricResearch/TradingAgents/blob/e8f5503e9b86d5c2710b0c76b1f686703968c9df/README.md)

适合借鉴：报告分工、工具轮数上限、结构化评级、缺口显式化、运行设置指纹和待结算结果。不能借用其模型评级代替 Roll 的 ForecastBundle、统计验证或 CapabilityGrant。

## 2. ai-hedge-fund：模型意见到确定性组合与连续模拟

### 当前版本的真实路径

本次固定版本已使用 hedge_fund/ 包，不能拿旧版 src/agents 路径描述它。[入口 run.py](https://github.com/virattt/ai-hedge-fund/blob/4e1657ddc689e3939c481a8f0955444b10f02dc9/hedge_fund/run.py) 接受 mandate YAML、universe、日期与模式；mandate 描述策略、人员/模型、风险、资金和频率，证券池在回测或部署时另给。

[assess_fund](https://github.com/virattt/ai-hedge-fund/blob/4e1657ddc689e3939c481a8f0955444b10f02dc9/hedge_fund/pipeline/stages.py#L40-L103) 的输入到决策顺序：

1. 按分析截止日取得价格，对可交易候选运行每个策略中的模型。
2. LLM 角色从 [FundamentalsSnapshot](https://github.com/virattt/ai-hedge-fund/blob/4e1657ddc689e3939c481a8f0955444b10f02dc9/hedge_fund/features/snapshot.py#L178-L238) 读取结构化财务资料；不同模型统一输出 Signal。
3. [LLMAgent](https://github.com/virattt/ai-hedge-fund/blob/4e1657ddc689e3939c481a8f0955444b10f02dc9/hedge_fund/signals/llm_agent.py#L158-L215) 将 bullish/neutral/bearish 与模型 confidence 转成 [-1,1] 意见分值，并记录 prompt key、snapshot hash。
4. [blend_signals](https://github.com/virattt/ai-hedge-fund/blob/4e1657ddc689e3939c481a8f0955444b10f02dc9/hedge_fund/portfolio/construction.py) 按模型权重和 long-only/long-short/dollar-neutral 规则合成目标权重；随后 apply_limits 和 validate_targets 执行风险约束与一致性检查。源码明确这种相对定仓没有把 conviction 校准成预期收益。

[advance](https://github.com/virattt/ai-hedge-fund/blob/4e1657ddc689e3939c481a8f0955444b10f02dc9/hedge_fund/pipeline/session.py) 先核对账本与 broker，执行上一时点决策、估值，再按频率生成新决策。日频决策在下一推进交易日收盘执行，非同一收盘价“看完再买”；记录代码版本、mandate hash、模型及哈希链。回测和 paper 模式调用同一推进函数，但换时钟、broker 和状态存放位置。

### 缺数据与历史时点

这里的缺口路径比“模型给中性”更明确：

| 情况 | 代码行为 | 证据 |
|---|---|---|
| 分析时过去 7 日没有可用收盘价 | 将该证券写入 skipped，不参与当次分析 | [stages._mark_prices](https://github.com/virattt/ai-hedge-fund/blob/4e1657ddc689e3939c481a8f0955444b10f02dc9/hedge_fund/pipeline/stages.py#L166-L190) |
| 财务历史不足 | LLMAgent 生成 abstained=True；聚合时排除弃权，区别于有意见的 neutral | [LLMAgent](https://github.com/virattt/ai-hedge-fund/blob/4e1657ddc689e3939c481a8f0955444b10f02dc9/hedge_fund/signals/llm_agent.py)、[construction](https://github.com/virattt/ai-hedge-fund/blob/4e1657ddc689e3939c481a8f0955444b10f02dc9/hedge_fund/portfolio/construction.py) |
| 模型调用或解析失败 | 弃权并记录原因；调用/解析轨迹缓存 | [LLMAgent](https://github.com/virattt/ai-hedge-fund/blob/4e1657ddc689e3939c481a8f0955444b10f02dc9/hedge_fund/signals/llm_agent.py#L70-L126) |
| 数据层一般错误 | 向上抛出，不假装是中性意见 | [数据客户端错误约定](https://github.com/virattt/ai-hedge-fund/blob/4e1657ddc689e3939c481a8f0955444b10f02dc9/hedge_fund/data/client.py#L262-L310) |
| 持仓估值或日频执行缺少当日收盘价 | 报错；不拿之前价格替代精确执行价 | [clock.exact_marks](https://github.com/virattt/ai-hedge-fund/blob/4e1657ddc689e3939c481a8f0955444b10f02dc9/hedge_fund/pipeline/clock.py#L78-L91) |
| 回测窗口没有基准交易数据 | 报错；无法建立交易网格 | [backtest_fund](https://github.com/virattt/ai-hedge-fund/blob/4e1657ddc689e3939c481a8f0955444b10f02dc9/hedge_fund/backtesting/fund.py#L114-L136) |

[FDClient 财务请求](https://github.com/virattt/ai-hedge-fund/blob/4e1657ddc689e3939c481a8f0955444b10f02dc9/hedge_fund/data/client.py#L107-L129) 使用 filing_date_lte，源码注释将无披露日期排除交给服务端；本调查只确认客户端查询契约，未验证服务端响应。snapshot 还明确用最新 sector/industry 作为近似，不能据此宣称严格历史时点完整。[snapshot 限制](https://github.com/virattt/ai-hedge-fund/blob/4e1657ddc689e3939c481a8f0955444b10f02dc9/hedge_fund/features/snapshot.py#L208-L228) 回测入口启用 blind prompts，隐藏证券、行业、日期等以缓解模型记忆泄漏；这是防护设计，不能证明消除了预训练污染。[入口的 blind=True](https://github.com/virattt/ai-hedge-fund/blob/4e1657ddc689e3939c481a8f0955444b10f02dc9/hedge_fund/run.py)

### 回测与最低运行条件

[backtest_fund](https://github.com/virattt/ai-hedge-fund/blob/4e1657ddc689e3939c481a8f0955444b10f02dc9/hedge_fund/backtesting/fund.py#L114-L172) 建立 SimBroker 和连续 FundState，逐交易日 advance，记录 NAV、基准、决策和执行结果；这确实是连续模拟。**但 [SimBroker](https://github.com/virattt/ai-hedge-fund/blob/4e1657ddc689e3939c481a8f0955444b10f02dc9/hedge_fund/brokers/sim.py#L1-L12) 全额按参考价成交，费用/滑点留作未来扩展，也不建保证金模型。** A 股 T+1、整手、涨跌停、无法成交、税费及公司行动不能凭这个模拟器推定已覆盖。

最低依赖：Python 3.11 系列起、项目依赖、Financial Datasets API 权限；使用投资者 LLM 角色时还需受支持模型服务及凭据。纯量化模型路径与 LLM 角色的模型依赖不同，但不能据此推定金融数据服务免费或 A 股覆盖成立。[pyproject](https://github.com/virattt/ai-hedge-fund/blob/4e1657ddc689e3939c481a8f0955444b10f02dc9/pyproject.toml)、[README](https://github.com/virattt/ai-hedge-fund/blob/4e1657ddc689e3939c481a8f0955444b10f02dc9/README.md) 本次未检查真实账户/服务套餐，未运行 paper 或回测。

适合借鉴：模型输出只作观点，确定性组合层控制权重；分析与执行分离；弃权与中性分离；回测/影子共用推进逻辑；连续账本与版本记录。其置信度加权没有替代 Roll 的概率校准，MIT 代码可用也没有消除数据许可、经济成交模型和独立验证工作。

## 3. TradingAgents-CN：助手产品与工作流编排，不能只看旧 graph

### 入口与输出

[README](https://github.com/hsliuping/TradingAgents-CN/blob/51060a7682cf51810b4bc3a704829438d18cd8dc/README.md) 定位是 A 股研究辅助，提供单股/主题研究、自然语言筛选、记忆、Skills 与模拟交易；社区版与 Pro 能力分开标示。

实际 [app/routers/analysis.py](https://github.com/hsliuping/TradingAgents-CN/blob/51060a7682cf51810b4bc3a704829438d18cd8dc/app/routers/analysis.py#L249-L418) 默认 v2，并拒绝 legacy；任务创建后入队。[TaskAnalysisService](https://github.com/hsliuping/TradingAgents-CN/blob/51060a7682cf51810b4bc3a704829438d18cd8dc/app/services/task_analysis_service.py#L87-L145) 持有 UnifiedAnalysisEngine；后者选择/解析工作流、整理 ticker/analysis_date 等输入并通过 core 的 WorkflowAPI 执行。[统一引擎](https://github.com/hsliuping/TradingAgents-CN/blob/51060a7682cf51810b4bc3a704829438d18cd8dc/app/services/unified_analysis_engine.py) 因而仓库中的旧 [LangGraph setup](https://github.com/hsliuping/TradingAgents-CN/blob/51060a7682cf51810b4bc3a704829438d18cd8dc/tradingagents/graph/setup.py) 虽能读到分析师→研究→交易员→风控结构，**不能据此宣称它就是当前 Web 默认执行链**。

本次还核对了 [StockAnalysisEngine](https://github.com/hsliuping/TradingAgents-CN/blob/51060a7682cf51810b4bc3a704829438d18cd8dc/tradingagents/core/engine/stock_analysis_engine.py#L141-L219) 的数据收集→分析师→研究辩论→交易决策→风险阶段接口，以及 [risk_manager](https://github.com/hsliuping/TradingAgents-CN/blob/51060a7682cf51810b4bc3a704829438d18cd8dc/tradingagents/agents/managers/risk_manager.py) 的风险汇总、争议、约束、信息缺口和观察点输出。它们证明相应模块存在；未完成对所有默认 workflow 模板及节点的逐条可达性审计。不能把模块存在扩大为全部 UI 路径已经验收。

### 缺数据、回测与部署限制

最值得注意的是 [TaskAnalysisService.execute_task](https://github.com/hsliuping/TradingAgents-CN/blob/51060a7682cf51810b4bc3a704829438d18cd8dc/app/services/task_analysis_service.py#L221-L270)：运行前数据校验代码已被注释，注释原因为历史数据同步未完成。它并不意味着其他节点没有检查，但足以说明不能用“有 validation 方法”认定默认执行前强制数据完整。

抽查的 [A 股数据接口](https://github.com/hsliuping/TradingAgents-CN/blob/51060a7682cf51810b4bc3a704829438d18cd8dc/tradingagents/dataflows/interface.py#L1526-L1639) 调用 data_source_manager，异常可包装为错误文本；指定 start_date 还会按 end_date 和配置回溯天数重算。[风险汇总模块](https://github.com/hsliuping/TradingAgents-CN/blob/51060a7682cf51810b4bc3a704829438d18cd8dc/tradingagents/agents/managers/risk_manager.py) 的 LLM 重试耗尽会生成明确的默认研究观察。这类继续产出文本的设计利于助手可用性，不能等同证据充足或正式交易资格。以上是明确函数路径的静态观察，不代表已证明所有 v2 工作流都会经过这些函数。

[core/backtest/engine_client.py](https://github.com/hsliuping/TradingAgents-CN/blob/51060a7682cf51810b4bc3a704829438d18cd8dc/core/backtest/engine_client.py) 将 DSL/Python 策略提交给独立 HTTP 回测服务（默认 localhost:8900）；本次没有运行服务，也未证明社区版入口、外部服务、数据和成交规则闭环可用。README 将策略创建/优化/模板调试等交易系统能力列为 Pro，不能把仓库内文件存在解释成社区版完整可用。

文档最低完整应用环境：Python 3.11、Node.js ≥18、MongoDB ≥7、Redis ≥6、模型配置和所选数据源条件；pyproject 的 Python 下限写 ≥3.10，存在文档与元数据口径差异，未据此承诺 3.10 能跑完整应用。[README](https://github.com/hsliuping/TradingAgents-CN/blob/51060a7682cf51810b4bc3a704829438d18cd8dc/README.md)、[pyproject](https://github.com/hsliuping/TradingAgents-CN/blob/51060a7682cf51810b4bc3a704829438d18cd8dc/pyproject.toml) 与两个轻量 Python 入口相比，服务配置与运维面更大。

适合借鉴：把研究发现、主题问答、缺口说明、研究记忆放在用户可操作的助手路径里。可借鉴交互思路；复用任何 app/core/frontend 代码前必须重新按许可范围审查。更不能因中文与 A 股支持就默认获得来源独立性、历史首次可得性、模型有效性或 Roll 正式动作授权。

## 对 Roll 的研究判断

以下是基于上述源码与 Roll 已有术语的推论，不是实现决策：

1. 可先学习“生成有来源、有缺口的研究材料”，让它作为 Evidence/Observation 的候选输入；不要将多 Agent 一致或 LLM confidence 直接写成 ForecastBundle 或正式 Decision。
2. 如评估连续影子研究引擎，ai-hedge-fund 的分析/执行分离最有参考价值；先补 A 股经济语义、费用和无法成交情况，再谈复用价值。TradingAgents 的评级网格应单独称为评级评价。
3. 对个人助研体验，CN 的主题、选股、记忆和工作流入口有参考价值；但运行前数据检查关闭和分层许可，都阻止“直接拿来就满足 Roll”的结论。
4. 三者均不提供本次已验证的 Roll REAL 能力。下一步若另获实施授权，应使用独立沙箱、公开样本和固定版本做最小运行验收；本次没有替任何候选安装依赖、使用真实账户、开展拟合/校准或消耗既有研究预算。

## 可复核范围

本次成功读取三个提交的完整 Git tree（truncated=false），并核对本文引用的入口、核心流程、数据错误路径与许可；至少 TradingAgents 与 ai-hedge-fund 已按固定提交贯穿入口到输出/回测路径。CN 由于多引擎与模板架构，记录已读路径及未贯穿部分，避免将 legacy 模块误报为现行 UI 实现。

未验证：依赖解析、Windows 启动、模型服务及行情服务可达、任何证券实际分析、费用与资源消耗、上游测试是否通过、回测成绩、社区实际使用效果、严格历史时点数据质量和投资有效性。README 的功能描述、源码存在和本机运行成功是三种不同证据；本文只有前两种。

