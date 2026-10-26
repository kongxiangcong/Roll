# 持续投研与独立报告合同 v1

状态：2026-10-26 按[规格 v1.0](../../.scratch/roll-research-valuation/spec.md)冻结。本文规定后续实现边界，不表示服务已实现；验收和缺口见[01证据](../../.scratch/roll-research-valuation/evidence/01/README.md)。

## 权威来源与模块入口

同一公司只有一份共享事实与分析版本。`CompanyResearch` 作为新增 `backend/src/roll/research/company/` 包的公开服务；包内按票增加 identity/evidence/state/valuation/drivers/changes/reports/features 模块，内部拆分可以调整，下面持久化语义和公开边界保持一致。API统一使用 `/api/company-research`，不复用账户 `/api/account/valuations` 或旧实验 `/api/research/*` 的写接口。沿用 Pydantic 的 `extra=forbid`、宿主时间、`ledger.connection()`、`encode()`、SQLite事务与现有 HTTP 错误惯例；版本记录以不可变 JSON 存储，查询索引列不构成另一个事实源。

| 当前入口（已检查源码） | 复用/迁移边界 | 负责票 |
| --- | --- | --- |
| `market/directory.py:MarketDirectory`、`market_identities`、`market_watch` | 保留A股账户/关注权威；研究公司映射引用其证券身份版本；新增HK研究证券不可写入真实账户许可或默认加入关注 | 02、07 |
| `market/evidence.py:EvidenceStore.archive/raw`、`evidence_archives` | 原件、提取物、报告工件均登记内容hash，使用raw/parquet现有受控路径；共享研究事实仅引用归档，不复制权威原件库 | 02、09 |
| `market/financial_income.py`、`financial_statements.py`、`financial_documents.py`、`financial_observation.py`、`news.py`及已配置来源 | 保留既有事实/解析版本，研究事实关联原记录、页码与口径；覆盖不足按公司/用途返回，不默认新增第三方服务 | 02、05、07 |
| `runtime/assistance.py:Assistance`、`agents/assistance_runtime.py` | 复用限定证据包、CODEX、候选JSON及引用校验；目前代码硬编码江西铜业/市场指数、独立线程且不等同共享快照。07改为公司参数与共享分析，08接worker；不可照搬硬编码或用其COMPLETE表示事实审核通过 | 03、07、08 |
| `runtime/reviews.py:Reviews.work/acquire_worker`、`runtime/observation_updates.py:ObservationUpdates.work`、`worker.py` | 在已验证租约的worker循环中增加有界研究处理器；公司研究任务表保存检查点，沿用宿主owner/存活检查与事务认领，不能新增常驻调度器。独立报告与盘后更新轮转，单次工作有限时 | 07、08 |
| `runtime/backups.py:references/safe_relative/attachment_path` | 现有SQLite备份覆盖新增表；所有文件由evidence_archives登记并走raw/parquet安全路径，恢复校验每个引用hash。不得直接沿用未被附件枚举覆盖的`assistance-raw`目录 | 02、09、12 |
| `accounts/valuation.py:Valuations`、capabilities/actions及旧研究协议 | 账户计值、正式资格与旧实验保持各自权威；公司估值不得调用其发布/授予/账户确认接口 | 全部 |
| `frontend/src/pages/daily-use.tsx`、`components/assistance-panel.tsx`、`financial-observation-panel.tsx` | 日报正文增加研究切片、展开证据/历史；独立报告入口使用同一快照。无账户确认亦可研究，账户位置仍显示未知 | 07、10 |

以上路径相对 `backend/src/roll/`（前端行除外）。基线为 `ebe3fc8`，其中已有工作并非本功能成果，复制清单在 `.scratch/roll-research-valuation/baseline-paths.txt`。本票只加合同与文档，既有实现未迁移。

## 通用记录与时间

所有新增对象带 `schema_version=1`、稳定ID、`created_at`（宿主UTC带时区）、`content_sha256`。版本对象另带 `version_id`、`entity_id`、`parent_version_id`、`revision`、`change_reason`。写入只追加；相同幂等键+相同请求hash返回原结果，相同键+不同请求拒绝。跨公司引用在事务内拒绝，发布时校验所有引用存在、公司一致、hash匹配。删除不用于“更正”已发布内容。

`disclosed_at`为披露时间，未知为null并存`unknown_fields`；`period_start/end`为报告期；`received_at`是本次真实收到，`consumable_at`为宿主完成检查可消费的时间；`as_of`为所述观察/研究截止时点；`generated_at`为真实生成时间。不得互相补写。当前取得旧报的实际取得时间仍是今天。当前研究允许用当前收到的历史报表，但用途为 `CURRENT_RESEARCH`，并标明信息时间；`STRICT_HISTORICAL_AS_OF`须同时有历史可得性、版本与实际消费依据，当前重建不能通过改字段取得资格。特征导出只取观察时点已可消费材料。

数值保存为有限十进制值及`unit/currency/scope/period`；缺失为null+原因，事实零值仍为零。不得通过`float`默认或前端占位填零。计算层转换单位要生成派生记录，记录原值、转换公式及汇率引用。预测、披露和确定性推算分别标 `DISCLOSED/DERIVED/ASSUMED`。

## 公司、证券与来源（02）

| 合同/建议表 | 必备字段和关系 |
| --- | --- |
| `Company` / `company_research_companies` | `company_id`、法定名、别名、注册地、会计准则、年结日、行业/模型适用性、身份依据；稳定身份不随名称修改而变 |
| `Listing` / `company_research_listings` | `listing_id`、`company_id`、交易所/市场、代码、股类、币种、有效区间、身份来源和版本；A/H是同公司不同证券，代码必须有市场限定 |
| `IdentityResolution` | 原输入、候选公司+证券、依据、`RESOLVED/AMBIGUOUS/NOT_FOUND`；歧义返回全部候选，执行必须给明确公司ID和必要证券ID，不默选首项 |
| `ResearchMaterial` / `company_research_materials` | 公司、来源类别`PUBLIC_ACQUISITION/USER_IMPORT/METHOD_CASE`、原件archive sha、上游来源ID/URL、页码/表号、实际取得/可消费时间、报告期/披露时间、原始来源根ID、来源run/现有事实ID、许可/覆盖限制；转载共用来源根，不算独立证据 |
| `ResearchFactVersion` / `company_research_facts` | 稳定事实ID、版本、公司/业务、指标、值、单位币种合并范围、时间、材料+定位、`supersedes`重述链、`conflict_group_id`、未知字段；冲突双方均保存，`resolution`引用双方及选择理由，不最后写入覆盖 |
| `SourceCheck` / `company_research_checks` | 公司、来源、请求类别/期间/字段、attempt ID、开始/结束、`SUCCESS/PARTIAL/FAILED`、`new_material_count`、已完成/失败覆盖范围、前次最近成功check ID和时间、错误及重试。成功无新增=SUCCESS+0；来源失联=FAILED；PARTIAL必须列每个失败范围 |
| `ResearchQuote` | `listing_id`、交易日/报价时点、价格/币种、材料引用、实际可得时间；研究读取现有行情快照时只建立引用，不另复制当前权威价格 |

核查事实与经营判断分开。最近核查时间取任一已结束attempt；最近成功时间仅取对应请求范围全部SUCCESS的check，局部成功另列，失败不得刷新成功时间或旧观点的验证日期。过期由资料年龄及用途政策派生，不能用最近失败时间隐藏资料过期。

## 经营假设与共享快照（03）

`OperatingHypothesisVersion`（`company_research_hypotheses`）保存稳定假设ID/版本、公司/业务、判断、期限、观测指标及口径、支持和反证fact-version引用、失效条件、下一验证事件（日期未知允许null+原因）、缺口、实际创建时间、修改理由。初次3—5项；证据不足可少于3项并存原因；支持和反证均可明确为空+缺口，不能造引用。价格变化不能自动改变经营预测。

`AnalysisSnapshot`（`company_research_snapshots`）保存`company_id/as_of/generated_at/parent_snapshot_id`、明确用途、全部material/fact/hypothesis/valuation/check/quote引用、核心结论和反证、限制、模型ID、prompt模板ID/hash、输入包hash、已校验来源ID及候选原文归档hash。`snapshot_id`是两工作流共同入口，结论/数值取自同一个规范化payload；日报和报告不能各跑一遍模型重算核心结论。无估值时valuation引用为空并携原因，其他研究可发布。

发布前冻结输入包和引用清单。`DRAFT`可保存在任务检查点；公开快照为`PUBLISHED`且不可变。更新只能创建新快照及父引用。输入变化触发新快照，不混入运行中的旧报告。离线重放读取保存候选/结果，确定性重算单独标新重算验证记录，不能重新调用模型冒充原文复现。宿主检查事实来源和数值，不把“模型生成成功”标成事实核验完成。

## 条件估值与经济审核（04、05）

`ValuationInputVersion`（`company_research_valuation_inputs`）与`ValuationResult`（`company_research_valuations`）分别保存输入版本和确定性输出，绑定公司、facts/hypotheses/driver-model版本、单位/币种、场景路径、价格/汇率时点、`method_id/version`、实际计算器文件hash、原输入/结果归档hash。结果不能只含模型填的未来FCFF。

输入包含年度经营桥：分部量×价→收入→成本/利润率→税→资本开支→营运资金→FCFF；无法量价分拆时说明使用收入驱动及依据。每项预测都引用披露锚点或显式假设。正常化调整行带原值、调整后值、公式、范围、证据、理由，利息分类/税盾/维持与扩张投资分列。增长、再投资及资本回报一致性检查逐项保存，不把CFO机械调整当作正常化。江西铜业工业/贸易/金融、抵销、联营及受限现金缺口保留；两年均值不能表示铜周期。

计算适用性为`APPLICABLE/CONDITIONAL/NOT_APPLICABLE`；首版FCFF+WACC仅适用非金融企业。银行保险等仍返回方法选择/缺口和其他研究，不调用FCFF执行器；复杂集团无分部依据、周期无正常化依据则经济审核blocked。FCFE、银行剩余收益、股息模型、SOTP/NAV/EVA专用执行器及仓位/评级不在本期。

计算必须保留：完整同年数场景、年末折现、终值N+1、终值占比、WACC/g网格、正负现金流有效性、EV到归母权益逐项桥接；净债务兼容字段和桥接明细互斥。桥接正数扣减、负数加回，少数股东、现金、联营资产等只处理一次，股数是同尺度参与分配/稀释口径且注明局限。EPV仅用扣维持性再投资后的正常化FCFF，共享输入，不标独立验证。反向DCF固定前N年路径，只解N+1终值现金流，只有同口径稳态FCFF利润率才可转收入/按N+1年求增速。

`MarketEquityBasis`保存每一股类股份数版本×同日证券价格及汇率，换为估值币种后相加；A+H缺A价/H价/汇率/任一类股数即拒绝反推，不得A价×总股数。公司价值和A股折溢价解释分开。WACC须保存无风险利率、溢价、beta、债务成本、税盾依据、市场权重、币种与日期；g须保存长期增长与再投资理由。禁止为贴现价自动反调这些假设。

`EconomicReview`（`company_research_economic_reviews`）为版本记录：`unreviewed/conditional/blocked/reviewed`、逐项检查ID/结果/证据、审核者类别、日期、限制、输入hash。宿主逐项有据检查后才能reviewed，候选自述不得升级；任何缺关键口径项使blocked，有条件假设为conditional。reviewed仅表示记录中经济口径检查成立，不表示收益或资格。保存诊断结果时`usable_range=false`，日报/速览/UI不得突出其每股价或区间；可以在明示“诊断不可用”的展开底稿查看计算。合格条件区间连同限制展示，情景权重是研究输入而非事件概率，最小/最大值不是置信区间。

## 三类变化（06、07）

`ResearchChangeSet`（`company_research_changes`）绑定同公司旧新快照和明确比较算法版本：

| 变化 | 保持/替换及输出 |
| --- | --- |
| `OPERATING_EVIDENCE` | 新事实/修订→受影响假设ID与前后版本、支持/反驳、来源及实际可得时间；无新证据不等于经营未变 |
| `PRICE` | 固定旧经营路径和估值方法/参数，仅替换同证券/同币种时点价格或A+H合计市值，计算现价要求前后；明确模型条件，不由价格推断市场真实因果 |
| `VALUATION_ASSUMPTION_OR_METHOD` | 折现率、正常化、g、桥接、方法等旧新版本、修改理由与影响；不可由价格自动抬高预测 |

多因素对照固定顺序为经营证据/经营路径→价格→估值参数/方法，每一步显示固定项和替换项，保存路径依赖/交互说明。方法、币种、单位或范围无法有据对齐时`NOT_COMPARABLE`，保留两边和原因，不硬减价格。示例永续100/10%=1000与100/8%=1250、+25%只是条件计算；固定10%支撑1250需125、固定100需8%，经营状态保持原样，不是市场定价原因。

日报 `DailyResearchView` 引用`snapshot_id/change_set_id`，包含关注理由、三类变化、现价要求（或拒绝原因）、下一验证、下行风险、量价判断冲突、材料日期、核查/最后成功日期、适用性与缺口、可展开引用/历史。范围由持仓与用户关注映射到公司，首次江西铜业仅为样例。无新材料只新增check/必要的变化记录，不调用完整报告生成；无估值仍交付研究正文。

## 报告任务、版本与错误（08—10）

`CompanyResearchJob`（`company_research_jobs`）保存`job_id/company_id/workflow(DAILY/REPORT)/request_hash/idempotency_key`、用户截至日期/刷新或复用模式、绑定snapshot/input hash、阶段、检查点、attempts、owner/lease、重试时点、取消时间、创建/实际起止时间、进度/错误、输出report ID。首次采集可在取得材料后绑定快照，但`ANALYSIS`阶段开始前必须冻结输入；后到材料留给下一job。

阶段顺序：`ACQUISITION→ANALYSIS→VALUATION→CHAPTERS→QUALITY→RENDER→PUBLISH`。阶段状态`QUEUED/RUNNING/RETRY_WAIT/COMPLETE/PARTIAL/FAILED/CANCELLED/INTERRUPTED`与工作流最终交付状态分离。VALUATION不适用/blocked可作为有结果的阶段并继续，不能把整个研究任务置死。worker重启保留检查点，将owner已死的RUNNING变INTERRUPTED，按有界策略重试；重试同一输入与发布幂等键只产出一个版本，事务发布引用和工件登记。取消保留已取材料和已完成阶段，发布前检查取消，已发布版本保持不变。

队列边界：沿用已有worker循环，每轮最多认领一项研究任务或一个可恢复阶段，DAILY/REPORT轮转，不能无界占用盘后任务；队列容量、单阶段超时、最大重试有显式配置及默认上限，票08记录实际默认。超过容量拒绝并返回retryable错误，失败不无限重试；阶段不能持有SQLite写事务等待网络或模型。新任务不得绕过现有租约的所有者验证。

`ReportVersion`（`company_research_reports`）保存稳定report ID/版本、公司、snapshot/job/parent-report、模板版本+冻结文件hash清单、章节、核心payload hash、出处清单、质量逐项结果、`FULL/PARTIAL`、生成与发布时间、Markdown/PDF工件及SHA-256/大小/MIME、交付状态。历史版本不可替换；报告核心数字直接取快照，章节扩写不能修改核心计算。缺材料/经济审核blocked的章节保留说明，原始未通过质量项仍为FAIL/UNKNOWN；允许发布带缺口的PARTIAL，只有全部适用必需项成立才可FULL。渲染失败可保留Markdown并显示`PDF_FAILED`，不标两格式完整交付。

API合同：`POST /resolve`；`GET /companies/{id}`；`POST /materials`（受控大小/类型/身份检查的用户导入）；`GET /companies/{id}/checks`；`POST /companies/{id}/refresh`；`GET /companies/{id}/snapshots`和`GET /snapshots/{id}`；`GET /companies/{id}/daily`；`POST /reports`（明确company ID/as_of/source_mode/idempotency_key）；`GET /jobs/{id}`；`POST /jobs/{id}/cancel`和`/retry`；`GET /companies/{id}/reports`；`GET /reports/{id}`及`/artifacts/{format}`。报告无需账户声明/正式策略授权；输入有歧义则返回选择界面。分页与大小有界，下载校验归档hash和公司引用；HTML只渲染清理后的文本，禁执行嵌入脚本/来源指令，图片只用登记本地工件，不加载任意远程URL。错误结构沿用`HTTPException(detail={code,reason,context,retryable})`。

| code类别 | 语义/处理 |
| --- | --- |
| `IDENTITY_AMBIGUOUS/NOT_FOUND`、`CROSS_COMPANY_REFERENCE` | 409选择候选/404未找到/422拒绝跨公司；用户选择前不跑采集 |
| `SOURCE_UNAVAILABLE/SOURCE_PARTIAL/ACQUISITION_TIMEOUT` | 保存check覆盖与尝试，有限重试；仍可用已有材料交付部分结果 |
| `MODEL_UNAVAILABLE/MODEL_TIMEOUT/MODEL_OUTPUT_INVALID/UNKNOWN_CITATION` | 保存阶段错误与既有材料；不能编造候选、改用模型记忆填事实 |
| `INVALID_NUMBER/UNIT_MISMATCH/CURRENCY_MISMATCH/WACC_NOT_ABOVE_G/TERMINAL_NOT_APPLICABLE/AH_BASIS_INCOMPLETE` | 确定性拒绝相应计算，保留输入与原因，其他研究继续 |
| `ECONOMIC_REVIEW_BLOCKED/QUALITY_INCOMPLETE` | 业务部分结果，可发布PARTIAL；不是网络重试能自动解除的错误 |
| `RENDER_FAILED/ARTIFACT_CORRUPT` | 标记格式交付失败或409拒绝损坏下载；修复后同输入重试，不覆盖已发布版本 |
| `INPUT_CHANGED/IDEMPOTENCY_CONFLICT/LEASE_LOST/QUEUE_FULL/CANCELLED/INTERRUPTED` | 冻结版本、事务幂等与有界运行错误；owner失效不得继续发布 |

## 特征与实验入口（11）

`ResearchFeatureSnapshot`（`company_research_feature_snapshots`）保存公司、观察时点、实际可得时间、特征定义版本、用途、snapshot及fact/hypothesis/valuation版本、支持证据独立根、审核状态、缺失mask/原因与信息年龄。候选包括假设修订、现价要求与研究情景差距、催化/风险状态；blocked估值数值不导出为有效特征，未知不填零，材料事后取得不能回填旧观察。情景权重、LLM自信与报告语气不映射上涨概率。事件、期限、原量价基线、样本、成本、时间外测试、Brier/log-loss/校准、风险行业暴露及停止规则先冻结协议，独立成熟证据不足返回INCONCLUSIVE；同季报多日报不是新独立样本。入口不自动训练、读取SEALED、重置预算或发放资格。

## 需求归属与可检查边界

| 规格条款 | 负责票/验收 |
| --- | --- |
| §1双工作流同数据与目标；§2身份/AH、持仓关注、覆盖边界 | 02、03、07、10；A1、A2、A8 |
| §2非金融/周期/集团适用性，报告交付默认与CODEX复用 | 04、05、08、09；A6、A7 |
| §2禁止扩围/无需逐次批准；§3条件语义/无账户资格写入 | 所有票，05、11、12验证；A9 |
| §4公司证券、原件事实、核查与修订冲突 | 02；A1、A3、A5 |
| §4假设、快照、双工作流一致、不可变/冻结/重放 | 03、07、08、09；A2、A10 |
| §5全公司问题链/3—5假设/驱动/正常化及江西铜业限制 | 03、05、08；A6 |
| §6第1—7项计算、许可/hash、审核与价格展示限制 | 04、05、09、10；A4、A6 |
| §7三类变化/多因素顺序/不可比/核查与日报正文 | 06、07；A3、A4、A5、A8 |
| §8入口/阶段/取消重试/十节/估值九子节/附录/质量闸门 | 08、09、10；A7，模板详见同目录`company-report-template-map.md` |
| §9队列公平/worker与盘后复用/缓存/版本双向丰富 | 07、08；A2、A8 |
| §9归档恢复/hash/不可信渲染/生产模型限定证据 | 02、03、08、09、12；A10 |
| §10特征时点/缺失/审核、协议、旧预算/封存保护 | 11、12；A9 |
| §11 A1—A10真实/模型/浏览器/合成分账，两实际盘后周期 | 12（各票保存分项证据）；未观察不能用时钟模拟补造 |
| §12串行、证据、五标签+Completion、失败/整体完成定义 | 每票及12汇总，01本身不声明后续功能完成 |

2026-10-26用户已确认TDD公共边界：研究服务/API验证身份、证据、快照和报告，计算器入口验证估值，网页验证流程并覆盖备份恢复；后续票在这些边界做红绿循环，无需重复询问已确认范围。本文不新增权限审批或更改规格验收。
