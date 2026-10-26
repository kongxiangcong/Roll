# 08独立只读payload审计（已追加exact wire核对）

前段保留最初“仅源码/回执、待wire”阶段的审计边界；文末“exact wire追加”是后续实际文件核对结果。本记录始终不是批准启动，也不代替auto-review。

目的：为同一auto-review补充可检查的payload范围与目的地证据，**不是批准启动，也不绕过已拒绝操作**。检查工作树`D:/dsh-proj/Roll/.scratch/worktrees/rv-ticket08`。未读auth文件、未运行编译器/DB入口、未启动服务/模型/网络、未更改08实现或数据库；此笔记是唯一写入。

## 已实际读取

- `backend/src/roll/research/company/report_runtime.py`，尤其ReportRuntime.command纯本地编译、execute边界。
- `backend/src/roll/agents/company_report_runtime.py`：章节INSTRUCTIONS/OUTPUT、无工具分派及结果归档。
- `backend/src/roll/research/company/report_template.py`：template_bundle/reference_text/source_reference。
- `backend/src/roll/research/company/reports.py`：freeze/chapter_preview及固定字段来源。
- `backend/src/roll/agents/codex_process.py`、`codex_worker.py`、`codex_evidence.py`的任务分派、隔离配置、模型/认证类型检查；**只读代码，不读取任何实际授权文件/变量值**。
- evidence08 `real-revision02.json`、`real-prepare02.json`、`real-source-plan.json`和相应准备脚本、旧start/stop文本。旧start/stop仅历史回执，不代表现在进程状态；本笔记未探测进程。
- 报告实际可能引用的7份冻结模板文本（02、01、04、13、15、10、11）做私有绝对路径及常见token字面模式只读扫描，未发现匹配；不等同对所有自由文本的安全保证。

## 回执能证明与不能证明的范围

`real-revision02.json`保存新job `82629305-575a-45b7-bf25-d6b0b03de028`，父job已CANCELLED；同一承德露露company/snapshot，core_sha256=`37b71966590cb1cb8d0c2898c4bace4c7ec1bc3b216018d2f941204f22dcac1d`；模板08.2，REUSE附加两份公开CNINFO年报。receipt记network_calls=0/model_calls=0；这是该准备动作回执，不能单独证明后来运行无调用。

`real-prepare02.json`隔离data_directory为`.scratch/rv08-real02`，account_version=0，snapshot_origin明确TICKET05_SOURCE_DRIVEN_NOT_NEW_LLM_OPERATING_ANALYSIS，current blocked/baseline conditional。account_version=0只说明准备回执记录的账户版本，并非本审计独立查询DB；没有读取账户表。

source plan中两份来源为CNINFO2023年报/2022更新年报，预期SHA分别`10501f7a2b295ae00fec12e81de456bb291b259d865c9589f004807ba151ed13`、`609b60a5bd4d83c76dd9bc204f9d0a65509de107362b5e71bb4ab78f58fe3e0f`。本人先前实际下载原件时已核对；本次没有重下载。来源计划包含公开URL、主体、报告期、语义限制及source identity basis；不含账户持仓。

## 编译器外发字段（待实际实例核对）

外层command是`model,tools,output_schema,instructions,prompt`，tools源码固定空列表。prompt编译字段：section_id/title/requirements/input_sha256/template/reference_content/company/CORE/VALUATION/current_valuation_status/facts/references/peer_facts/peer_context/request_cutoff/actual_obtained/knowledge_frozen_at/historical_pit_eligible/source_gaps/source_check_receipts/unincorporated_material_ids。

这不是只发送段落正文：template含27文件资产metadata与archive注册记录；CORE是完整共享snapshot，可能含input/candidate archive引用；facts是完整事实记录，含change_reason/derivation等自由文本。company可能含identity_basis/market_identity_reference；source_check_receipts也是嵌套对象。必须按实际wire检查所有嵌套字符串，不能仅检查顶层字段名或“没有account字段”。

source_reference只输出公开source_url、hash、原件page/table、相对`/api/company-research/.../original`及事实口径/数值/主体/角色，没有主动加入本机绝对路径；但archive注册metadata及自由文本是否实际携带本地路径仍待实例检查。evidence08准备回执里的data_directory是**本地审计信息**，不能混为将发prompt的既定字段。

## 目标/能力的静态证据及限制

报告model在job.start时从ROLL_CODEX_MODEL或默认`gpt-6.1-sol`冻结；execute要求显式授权文件并验证auth_mode=chatgpt，经过已有openai_codex SDK边界；worker代码调用account_read检查类型chatgpt，model_list要求精确型号，thread_start禁provider fallback。隔离配置禁shell/文件变更审批、web、MCP、skills、apps/plugins、多代理；章节工具列表为空，宿主tool返回DENIED。

以上证明代码意图使用既有ChatGPT认证的CODEX，**未独立读取实际新job.model或实际effective provider/网络终点**；没有读取auth也没有联网确认订阅状态/实际provider。真正请求model要以exact preview为准，最终resolved_model/provider只可能由获准真实运行回执确认；不因此发起调用。

## 初次源码阶段尚未覆盖/不作结论（历史记录）

root通知exact章节preview/audit尚未落地；截至当前记录，没有实际wire文件可读。因此尚不能断言“所有即将外发字段仅公开资料”“无本地路径/无秘密/无账户内容”，也没有为任何发送签泛泛安全保证。需收到具体preview文件后核对JSON bytes/hash、model、字段集合、嵌套内容及命令同一性再追加。

## exact wire追加：已实际复核12份章节命令

输入目录：`D:/dsh-proj/Roll/.scratch/worktrees/rv-ticket08/.scratch/roll-research-valuation/evidence/08/preview-08.2/`。实际读取`audit.json`、`packet.json`、`command-1.json`至`command-10.json`、`command-REVIEW.json`、`command-CHALLENGE.json`。没有调用chapter_preview或任何产品方法，没有打开DB/授权文件、没有启动服务/模型/网络，也没有改这些源文件。

独立逐文件结果保存在同级外部审计产物 `C:/Users/72449/.codex/visualizations/2026/10/26/01a178d3-3ac6-7763-8382-1200d54806f8/rv08-independent-wire-summary.json`。该JSON由单独文件读取/标准JSON/AST/Hash计算生成，没有导入或运行Roll服务。

### 字节、冻结输入与源码一致性

- 12个command文件均为实际可发送的规范UTF-8 JSON字节（ensure_ascii=False、sort_keys=True、separators=(',',':')），不是仅供展示的另一个缩略对象。**每个文件自身SHA256均与audit.commands登记值一致**；逐个完整SHA和byte数见独立summary。大小181448–208961 bytes，均小于256KiB。
- packet.payload按上述canonical编码SHA=`bdb2252f4f9aab4d24dfbd8b98d17a50dc603c579ee3092bd5a9ea59c2b6a77e`，同时匹配packet.packet_sha256、audit.input_sha256及12份prompt.input_sha256。实际job/input分别为`82629305-575a-45b7-bf25-d6b0b03de028` / `33ee7a98-3a94-479a-8eca-131264e6a07a`。
- 12份command共享字段逐项与packet固定值相等；章节title/requirements与当前源码SECTIONS相等；INSTRUCTIONS和OUTPUT schema与对应源码AST字面值相等，且其hash也匹配audit。每章reference_content逐份与包内冻结参考正文相等。packet中14个代码hash与当前实际文件字节一致，未见冻结后源码漂移。
- 12份command.model都精确为`gpt-6.1-sol`，tools都为空。相同51条subject facts、51条references；peer_facts和peer_context为空。CORE快照ID及core_sha与audit相同。当前用途字段为CURRENT_PRICING，current_valuation_status=blocked；CORE内旧baseline valuation记录仍保留conditional/usable_range元数据，这不是本审计重新审批估值。

### 实际内容范围，而非泛称“纯年报”

已逐条人工阅读51个fact的metric/value/unit/currency/scope/page，且阅读所有去重的change_reason、derivation、identity_basis和path值。它们是露露公开2025年报/2024比较列中的收入/成本/税费、费用、利润、现金/关联存款、银行/租赁/回购义务、股数、CFO/Capex/DA/WC、权益/承诺文本，以及明确有派生定义的经营利润/桥/权益差额。

包还含**非发行人年报资料**：中债2025-12-31国债收益率、NYU Damodaran作者公开China ERP/全球软饮料行业beta、已连接provider取得的000848历史市值近似值。其URL/hash、派生方法/日期/未确认RAW-price限制在相应fact元数据中保留。provider引用是`registered-source://CONNECTED_MX_FINANCE_DATA/000848/market-cap-20251231`，不是新网络请求地址，不含工具凭证。

company为承德露露公开主体/上市证券/会计准则/登记说明；market_identity_reference实际为null。CORE内有内部研究UUID、哈希、原件archive引用及确定性研究说明，这些是本地项目研究metadata，不是账户持仓。source_check_receipts实际为NOT_REQUESTED/显式REUSE，不含网络调用响应或私有账户资料。新增两份2023/2022年报在packet材料索引中；当前51fact并未假称已将它们全部提取为新经营核心。

### 嵌套路径与内容筛查的具体结果

- 检查整个prompt每个递归叶值，覆盖CORE、facts、template.assets、references、source receipts及自由文本。每章约2627–2628个字符串叶（精确计数见summary），不是只搜顶层键。
- 实际`archive.path`为`raw/<SHA256>.raw`相对引用；模板原资产path是`references/...`、`scripts/...`、`tests/...`、`examples/...`及许可文件相对名。没有观察到`D:/...`、`C:\...`、UNC、`/Users/...`或`/home/...`等本机私有绝对路径进入实际prompt。准备回执中的data_directory未出现在这12份command.prompt中。
- 递归字段未出现positions/holdings/cash_balance/account_events/account_snapshot/broker_account/account_number/auth/tokens/password/secret/api_key/credentials等实际承载字段；常见Bearer/API-key/private-key字面模式与URL username/password userinfo筛查均0。人工所读事实/自由文本未见真实账户持仓、交易、账户现金、授权秘密或本机用户名地址。这里“cash”指标明确是发行人合并货币资金，不能误当用户cash_balance。
- 这些是**对指定已哈希字节的内容观察与模式筛查**，不保证检测所有可能的秘密编码，也不保证后来发出的命令未变。没有读取实际auth内容或订阅私有信息去作额外验证。

### 目的地与尚未覆盖边界

actual command已确认model=`gpt-6.1-sol`，audit明确提议目标为既有ChatGPT订阅的OpenAI Codex、无新API key；既有worker源代码要求chatgpt account类型并禁model/provider fallback，未定义新的外部API endpoint。**这次是纯文件审计，没有实际网络请求，因此不能独立确认将来运行的effective provider、具体网络终点或订阅当时有效状态**；这些应由同一auto-review结合此前授权与已有运行配置判断，获准后才可能有真实resolved_model/provider回执。

本记录提供新证据供同一auto-review重新评估一次；**不构成启动/发送许可，也不主张绕过或改变拒绝规则**。如果冻结packet、命令hash、源码/配置、model或目的地变化，此次内容核对不自动覆盖新版本。
