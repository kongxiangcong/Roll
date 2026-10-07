# Roll 外部组件定向核查

核查日期：2026-10-07。用途：开发前实现对齐；Q1—Q9 已确认，本轮产品边界与路线对齐完成，可作为 to-spec 的输入。不代表 M0 实验协议已冻结，或生产代码、账号权限、真实接口与适配测试已通过。参考项目中的指令文件仅作分析材料。

## DSA 数据采集候选

版本：`ce364e457aab288863a5707e7b3df79786ad07f2`；[MIT 许可证](https://raw.githubusercontent.com/ZhuLinsen/daily_stock_analysis/ce364e457aab288863a5707e7b3df79786ad07f2/LICENSE)。账户与导入审查另见 [实现对齐记录](implementation-alignment.md)。

| 文件 / 组件 | 已查代码行为 | Roll 取舍 |
|---|---|---|
| [data_provider/base.py](https://github.com/ZhuLinsen/daily_stock_analysis/blob/ce364e457aab288863a5707e7b3df79786ad07f2/data_provider/base.py)：BaseFetcher.get_daily_data / DataFetcherManager.get_daily_data | 清洗会丢弃 close/volume 缺失行；按供应器优先级返回首个非空结果与源名；个股日线全失败抛错，报价全失败返回 None；未提供完整原响应、复权版本、收盘状态契约 | 不整体复用管理器；有限换源与错误分类仅参考设计，Roll 自行检查用途和口径 |
| [efinance_fetcher.py](https://github.com/ZhuLinsen/daily_stock_analysis/blob/ce364e457aab288863a5707e7b3df79786ad07f2/data_provider/efinance_fetcher.py) | 日线硬编码 fqt=1；缺 OHLC 用 close 补，缺量额补零；单股报价缓存未命中时先取全市场再筛选 | 请求/字段映射可作改造候选；不采用缺失补值和默认全市场报价路径 |
| [tencent_fetcher.py](https://github.com/ZhuLinsen/daily_stock_analysis/blob/ce364e457aab288863a5707e7b3df79786ad07f2/data_provider/tencent_fetcher.py) | 单证券、最多 800 条；qfqday 缺失退到 day，未标口径变化；普通股手转股/科创板保留股是代码中的单位假设 | 请求/映射可作改造候选；单位须对上游实测，原价与调整价分开，不静默混接 |
| 报价 enrichment / merge | provider_timestamp 可未知；包装时 fetched_at 可能晚于缓存实际采集时点；补字段缺少逐字段来源与时间 | 不采用包装时间充当数据新鲜度，也不隐式拼接不同来源字段 |

必要依赖范围来自 [requirements.txt](https://github.com/ZhuLinsen/daily_stock_analysis/blob/ce364e457aab288863a5707e7b3df79786ad07f2/requirements.txt)：pandas>=2、numpy>=1.24、requests>=2.31、efinance>=0.5.5、tenacity>=8.2、exchange-calendars>=4.13，另耦合仓库配置、补丁与证券解析。这些范围不是 Roll 已锁定版本。

只做过一次无需密钥的腾讯公开只读日线探针：600519、2025-01-01 至 2025-01-10，HTTP 200、业务 code 0，返回 7 条 qfqday、无成交额列。未执行 DSA 代码；该结果仅证明本机一次可达及该样例结构，不证明历史深度、稳定性、单位或报价已验收。

复用分类：没有确认可直接复用的完整组件；少量请求/映射逻辑为改造候选；换源与熔断思路仅参考；补值、无口径切换、整套多市场管理器不采用。需验收原价/复权、除权、单位、证券与指数标识、未收盘/休市/停牌/缺失、缓存时点、800 条截断、限流与超时、原响应先归档及离线重放。

## 扶摇公开接口

检查对象为当日可读在线文档与 main README，没有提出仓库代码复制。README 标示 MIT，不能据此推导数据归档、再分发或商业使用权限。

- [股票行情](https://fuyao.aicubes.cn/docs/api-reference/prices/)：historical 单标的、日线、请求跨度最多 10 年，adjust 默认 forward，另有 none/backward；接入须显式口径。snapshot 支持 thscodes 批量，但 data.timestamp 为整批最新上游有效时间，条目未提供逐证券时间，不能视为每只证券的新鲜证明。
- [指数](https://fuyao.aicubes.cn/docs/api-reference/a-share-index/)：批量快照及单指数日线；文档列交易所及同花顺指数，历史无股票复权参数。
- [交易日历](https://fuyao.aicubes.cn/docs/api-reference/calendar/)：固定近一年至今日，不能独立提供未来排程或长期历史日历。
- [快速开始](https://fuyao.aicubes.cn/docs/quickstart/)：需要 X-api-key；HTTP 成功后仍检查业务 code，2003 表示账号未获对应 capability 权限。
- [README](https://github.com/HiThink-Tech/Financial-API/blob/main/README.md) 与 [能力索引](https://fuyao.aicubes.cn/llms.txt)：公开方式不提供新闻公告/研报原文，部分资讯能力属于客户端内专用。当前不限制累计调用次数的表述伴随动态限流，不足以证明永久免费；没有查到可用于完整费用估算的服务价目。

未读取本地凭据，未登录或调用数据 API。账号权限、实际延迟、停牌/缺失语义、逐证券时点、调整一致性及数据使用权限待接入阶段验证；价格仍无核实结论，但费用规划已按 Q7 移出本轮，不作为开始开发的前提。建议候选路径为扶摇结构化接口与 DSA 小范围采集适配器，公告、日历缺口另寻可追溯路径；不把“备用”误称已通过等价性验收。

## LangAlpha 证据追踪

固定版本 `941ca4a18f5a364caf481a6f78cdb040086aa38d`，根 [LICENSE](https://github.com/ginlix-ai/LangAlpha/blob/941ca4a18f5a364caf481a6f78cdb040086aa38d/LICENSE) 为 Apache-2.0。检查指定 [thesis-tracker/SKILL.md](https://github.com/ginlix-ai/LangAlpha/blob/941ca4a18f5a364caf481a6f78cdb040086aa38d/plugins/langalpha_research/skills/thesis-tracker/SKILL.md) 及关联 [evidence.md](https://github.com/ginlix-ai/LangAlpha/blob/941ca4a18f5a364caf481a6f78cdb040086aa38d/plugins/langalpha_research/skills/research-conventions/references/evidence.md)。

仅参考稳定证据编号、来源与时点、事实/派生/假设分离、观点依赖、失效/替代与冲突记录。它是 Agent 文档工作流，不是已实现不可变存储和确定性重放的证明；不装载其技能，不复制投资论点、目标价、退出触发、用户 approved 状态、美股工具排序或固定一分钟新鲜度。approved 不等于 Roll 技术资格。

本次不涉及运行库复用；Roll 仍需自己验收原始依据归档、修订依赖失效、冻结输入重放、同源转载识别、冲突保留和越权拒绝。

## 受控取证后端

检查的是 2026-10-07 官方在线文档，尚未选定并锁定部署包版本，也未运行模型请求。

- [Agents SDK models](https://openai.github.io/openai-agents-python/models/) 支持 Responses、Chat Completions 及自定义提供者；不同提供者的工具与结构化输出能力不可视为等价。Roll 应明确具体模型/协议，不能依赖 SDK 隐式默认模型；提取结果须由宿主验证。
- [运行文档](https://openai.github.io/openai-agents-python/running_agents/) 提供 max_turns、工具并发与 tracing 控制。Roll 仍须在宿主统一执行时限、调用停止条件和取消，子任务受同一任务边界约束。取证仅接收任务所需对象/字段/截止时点，返回证据候选、来源、时间和缺口；不具有正式账本或授权写接口。默认本地审计，不自动导出含账户信息的云 trace。
- [Codex SDK](https://learn.chatgpt.com/docs/codex-sdk) 当前文档列出 TypeScript SDK 与稳定 Python 包 openai-codex；Python 路径通过本地 app-server JSON-RPC，发布包带固定 CLI runtime。故不能预设一定要增建 Node 桥接，也不能把本机 CLI 0.130.0 视为与当前 SDK 匹配。
- 本机 CLI help 仍列 mcp-server 且称 app-server experimental，而在线 SDK 页已描述 mcp-server 移除，表明版本存在差异。Codex 后端需要锁定 SDK/runtime 组合，并验证取消、事件输出、只读权限、工具和配置隔离；本轮不安装或升级。
- [Codex 配置文档](https://learn.chatgpt.com/docs/config-file/config-advanced) 说明用户状态、项目配置和 AGENTS.md 的自动读取。Roll 不能直接让生产取证继承当前开发目录和个人开发技能；需独立任务工作目录、明确允许的配置/工具与凭据通路，验证正式数据无法被改写。只读文件设置不等于所有联网工具均无写副作用，工具边界仍需 Roll 控制。
- [DeepSeek 工具文档](https://api-docs.deepseek.com/zh-cn/guides/tool_calls/) 列工具调用与 beta strict schema 约束。后续 Q7 已明确将 DeepSeek 与 Codex 均列为可切换后端；该选择不表示 Agents SDK 下多轮工具、取消、结构化输出与用量统计已经通过。本轮未运行 API 调用。

## 已确认决定与后续验收边界

Q7 已明确：用户已有 Codex 和 DeepSeek 订阅，两后端支持切换，本轮不再考虑费用。此前金额上限和费用示例不作为产品要求，已撤回；不安排独立人工复核人员或费用。取证后端实际访问权限与适配仍在实现阶段验收，不由订阅陈述替代。费用规划移出不删除实际成交费用与税费记录，也不删除实验的费用后收益口径。

前向研究从冻结模型首次实际归档起，最长 **3 个自然月**；结束只评价成熟结果，证据不足保留 INCONCLUSIVE。保留有限调用、超时、取消和完整尝试登记，防止无限递归或为了通过而延长实验。Q3/Q5/Q6 已确定按需分析，以及程序运行时对已冻结且可运行实验保存盘后影子记录；遗漏保留缺失，不补造前向预测。Q8 已确定手工表单＋Roll CSV 模板，不等待专用券商格式。

Q9 已确认用可复现自动验证、模型技术审阅和确定性资格检查替换专业人士独立复核的必备门槛，见 [ADR 0003](../adr/0003-automated-validation-review.md) 与 [实现对齐记录](implementation-alignment.md)。保留 G1—G7、冻结证据、完整 ReviewRecord、阻断事项的证据处理以及用户资金启用。模型不能自签资格；必需项无法自动核实则保持未通过或证据不足。界面与交付如实标注“未经人工独立复核”，不再将等待人工复核作为当前正式准入路径。

本记录保留已有公开文档、静态代码与一次有限探针证据，不把它们升级为适配通过。具体时间窗、效应目标、统计方法、规则、SDK/runtime 版本与后端切换契约，以及真实接口验收，仍由后续开发/研究产出并验证；这些是进入规格的工作，不是需要继续向用户索取的产品选择。

## 2026-10-08：票11实际 Codex 适配

本节是后续实施证据，不覆盖以上2026-10-07静态调查。Python3.13.12实际安装并锁 `openai-codex/openai-codex-cli-bin 0.161.0`，采用发行包和公开同步 `CodexClient`/JSON-RPC；固定源码 [979011409de0a60b52f179721948e65531d26144](https://github.com/openai/codex/tree/979011409de0a60b52f179721948e65531d26144)，[许可证 Apache-2.0](https://github.com/openai/codex/blob/979011409de0a60b52f179721948e65531d26144/LICENSE)。分类为官方 SDK/配套 Runtime 实际接入，Roll 自写有限宿主适配，未摘取参考仓库源码，未引入闲置 Agents SDK。

实际完整模型任务解析 `gpt-6.1-sol/openai`，ChatGPT 最小认证副本在独立 home 有效；目录可见与多轮真实任务分别证明。动态工具需要发行物自带 Rust/V8 `codex-code-mode-host.exe`：关闭时实际工具失败，启用最小host特性后完成多轮获取和结构化结果，无 Node 桥。所有额外SDK/runtime模块随 `uv.lock` 固定，实际EXE/bridge SHA、版本、配置和工具指纹记录于 [11验收](../../.scratch/roll-p0/evidence/11/acceptance.md)。

Windows实际仍发现个人技能元数据，因此只在独立 `CODEX_HOME` 写技能 disabled 配置，再强制重载核验 enabled=0；模型线程 instructionSources为空。未修改个人配置、技能或认证。纯V8实际工具面仅两个宿主取证工具与无副作用clock，fetch/process/require不存在，node:fs import实际拒绝。生产提示对抗未读取私文件、未写哨兵、未发POST，账户不变；该证据与固定源码检查、组件clock探针、方法案例分列。

真实 FastAPI/SQLite/原件/Parquet/Chrome 多轮取证、取消、SDK错误及实际API宿主硬崩后Job归零/精确凭据清理已验；有限接收字节包含失败/丢弃，字段门禁不因模型完成移除。仅补充登记茅台官方主页，其他对象/资料无能力时保留缺口；原文短引核对不等于断言真值或历史可得性。票12/13、技术审阅23及完整市场资料覆盖仍有独立验收，不能从本票推及。具体接口与局限见 [Codex契约](../codex-evidence-contract.md)。

## 2026-10-08：票12 DeepSeek工程适配（partial）

实际安装Python3.13.12，锁定`openai-agents==0.23.1`、`openai==3.26.0`、`httpx2==2.13.1`、`jsonschema==4.26.0`。采用官方Agents SDK公开Agent/Runner/FunctionTool/OpenAIResponsesModel及公开HTTP transport，非源码摘取或私有补丁。Agents固定[tag c4a1d047b22488234b2ba81056e1b9b8db2127a5](https://github.com/openai/openai-agents-python/tree/c4a1d047b22488234b2ba81056e1b9b8db2127a5)、[MIT许可](https://github.com/openai/openai-agents-python/blob/c4a1d047b22488234b2ba81056e1b9b8db2127a5/LICENSE)，发行wheel SHA256 `0183e6da7370df80f7cf900379d9f113e664e32b426f51aa7486c9091faf8f2d`；OpenAI客户端[tag 4e152cdefe1844c2d5d78653310e9b9c0195c44e](https://github.com/openai/openai-python/tree/4e152cdefe1844c2d5d78653310e9b9c0195c44e)。必要基础传递依赖MCP未加载服务器；不引入extras、LiteLLM、SandboxAgent、插件或技能。

[DeepSeek Responses官方说明](https://api-docs.deepseek.com/zh-cn/guides/responses_api/)与固定SDK源码核查：provider无状态、不支持include，但SDK实际发送空include。唯一兼容适配删除`include=[]`，拒绝非空及有状态字段；不从固定HTTP方法推定真实strict/schema支持。固定`deepseek-flash`及`https://api.deepseek.com/responses`，无OpenAI fallback；全局及运行tracing明确disabled。Roll复用11具体有限工具和07事实归档/门禁，不抽泛化后端框架。

实际SDK三轮固定响应接续、串行受控工具、失败/丢弃接收预算、结构宿主校验、本地脱敏、FastAPI/SQLite/Chrome及OS故障工程通过，17实际模型工具payload发送前封存输入审计通过。仍没有明确DeepSeek API认证，真实服务多轮、模型权限、schema/用量、实际取消/错误未执行，票12保持needs-info/partial、13未解锁；Codex完成与网页订阅不代替本后端验收。条件及分层原输出/精确保全见[12验收](../../.scratch/roll-p0/evidence/12/acceptance.md)、[接入合同](../deepseek-evidence-contract.md)。

## 2026-10-08：票14决定性事实核验

沿用以上已核LangAlpha固定941ca4a证据依赖方法分类，Apache-2.0来源指针保留；本票只参考设计，没有摘取该仓库代码、迁入技能/approved语义或新增SDK。Roll自写具体14模块复用07原件/Parquet、08短SQLite来源修订事务、17实际字段交付审计；不建设多Agent投票/来源认证平台/泛化后端。

实际两原供应商茅台字符串1258.62/1258.620保留，但原始生产链未证且旧metadata/时点不比，输出不足。发行人原公告文件/metadata重复只计一依据，不能由异域网页或自填origin_id签多源。独立生产者一致正例仅固定外部METHOD原件，真实样例仍不足；源自身基本校验失败亦阻止签核。来源仅原字节/原始链变化时即使规范数值相同也使旧核验失效，新UUID引用已知旧原件仍失效。

15冻原观察疑点的显式消费在一短事务写核验、request和audit关联，并发/重试同ID、原生提交前后故障原子恢复；真实原件Chrome与METHOD/OS分层，原观察与账户保持。六条实际payload经17封存输入审计，未把输入查看当结果检验。真实来源取得后精确SHA复放/412文件34,205,250bytes保全、模型请求0/auth0。初实际对照误选指数的原报告完整保留并按证券/组纠正不重取，详见[14验收](../../.scratch/roll-p0/evidence/14/acceptance.md)与[具体接口](../independent-verification-contract.md)。
