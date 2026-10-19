# 能力补齐执行记录

**Status:** ready-for-agent
**Completion:** pending
**Execution:** IN_PROGRESS — 2026-10-15 用户显式启动，集成分支 codex/roll-capability-expansion。

2026-10-14：按用户要求使用to-spec/to-tickets发布计划；另一个会话仍在执行。仅生成本feature文档，不安装、不修改产品、不取数、不训练、不发送消息、不创建定时任务、不提交或推送。

## 启动门槛

用户在另一会话结束后明确要求开始，才运行01交接。旧调研状态可能已经变化，必须按最终交付重核。尚无本计划实施验收，不能将ready-for-agent解释为运行条件已满足。

## 当前票状态

| 票 | Completion | 备注 |
| --- | --- | --- |
| [01 · 交接基线与既有能力继承](issues/01-handoff-baseline.md) | complete | 交接映射与当前有限兼容检查3 PASS/35.84s；真实服务当前不可访问 |
| [02 · 完整日线用途与来源缺口补齐](issues/02-daily-evidence.md) | partial | 已继承采集/重放，页面查询和Chrome/手机/构建通过；完整session/RAW修订依据不足 |
| [03 · 有效交易状态与未知覆盖](issues/03-status-evidence.md) | partial | 截止查询/单股来源区/API2 PASS及Chrome通过；全状态与否定覆盖依据不足 |
| [04 · 公司行动版本与义务证据](issues/04-action-lifecycle.md) | partial | 截止版本/旧义务查询和单股原件链已验收，生命周期和完整覆盖待证 |
| [05 · 后继政策完整冻结与验证消费者](issues/05-policy-freeze-validation.md) | partial | 同源九类诊断、联合压力、阈值/迁移、工程检查、两主模型中心及原CAL预测完整日历执行已验收；来源包→模型→独立推进METHOD管线已补；REAL准入/authority、共同风险匹配/四非中心工件/独立支持和完整冻结仍缺 |
| [06 · 当前动作有效期与政策派发](issues/06-current-action-validity.md) | pending | 已发布，未实施 |
| [07 · LOSS原因绑定恢复闭环](issues/07-loss-recovery.md) | partial | 用户确认显式后继恢复规则，工程/API/Chrome通过；真实资金条件未满足 |
| [08 · 现有候选真实前向启运](issues/08-existing-forward-start.md) | pending | 已发布，未实施；含真实外部/时间条件 |
| [09 · AKShare利润表首个完整切片](issues/09-income-statement.md) | complete | 独立生产SDK/API/SQLite/Chrome已验收：3HTTP/5期/原件SHA/账户不变，预算封口 |
| [10 · 资产负债表与现金流三表联读](issues/10-balance-cashflow.md) | complete | 三表联读/版本/异常、实际5HTTP封口、只读Chrome通过；其余语义缺口保留 |
| [11 · 财务口径、修订与确定性指标](issues/11-financial-metrics.md) | complete | 确定性公式/未知口径/修订重放/API/真实只读Chrome通过，零新增取数 |
| [12 · Docling表格与页码证据](issues/12-document-tables.md) | complete | 实际 Docling 2.139.0/官方权重/RapidOCR：真实文本页与扫描页、跨页边界、API/Chrome 通过 |
| [13 · 财务分析进入单股与复盘](issues/13-financial-observation.md) | complete | 版本化观察/趋势/缺口/原件与PDF派生；真实三表副本、缺失/修订/禁用源、Chrome通过 |
| [14 · 单股新闻与正文归档](issues/14-news-ingestion.md) | complete | API/原件/标题及真实4HTTP/10条/3HTML/Chrome通过；2026-10-18 实际 Trafilatura 2.3.1 对3份归档HTML抽取成功，reference VERIFIED |
| [15 · 新闻证券关联与转载去重](issues/15-news-entity-dedup.md) | complete | 事件归并/四类关联/别名冲突/多对象/重启幂等；真实10条样本与Chrome通过，真实转载未出现 |
| [16 · 中文情绪组件与有限评测](issues/16-sentiment-evaluation.md) | complete | 单候选训练2轮/348.6秒，冻结400/120/120；主各30/事件17/19/21/27，一次评估全部原门槛通过；真实API12条/账户0/重启一致，pytest23/构建/新旧Chrome/双轴通过。仅单公司非独立受限研究，原失败及修订/转载限制保留；显式候选，NOT_GRANTED |
| [17 · 事件级情绪序列与覆盖说明](issues/17-sentiment-series.md) | complete | 不可变v2事件序列/计数比例/拒判/日历缺口/API/页面；pytest15+审查后序列6、构建、真与METHOD Chrome/双轴通过；真实10已观察/12待次日，零推理；非历史预测/NOT_GRANTED |
| [18 · 财报新闻接入现有日常运行](issues/18-observation-worker.md) | complete | 原worker/租约/API/页面/缓存/取消/站内限定；新10测试/构建/Chrome/双轴通过，检查点推进与取消race已修复；真实22新闻/财务事实观察/重启通过，推理超时及旧通知3基线失败保留 |
| [19 · QuantStats绩效图与导出](issues/19-performance-report.md) | complete | 三条保存基准读取遗漏已修复；固定窗口/错位/API/Chrome/旧报告重放通过，未授资格 |
| [20 · scikit-learn概率计算核验](issues/20-probability-reference.md) | complete | 固定口径实际库/API/边界/Chrome/源绑定/重放已验；非独立统计资格 |
| [21 · arch区块统计核验](issues/21-block-stat-reference.md) | complete | 实际arch成对统计/API/边界/Chrome/保存重放通过；来源区间不足，独立有效性未授予 |
| [22 · 新增特征快照与消融协议](issues/22-feature-asof-protocol.md) | partial | 关联家族预算/固定契约/特征快照/预检/API/页面；14回归+最终4新项/构建/真与METHOD Chrome通过；真实来源快照零拟合/SEALED，待双审查 |
| [23 · 后继候选真实训练与完整冻结](issues/23-successor-fit.md) | pending | 已发布，未实施；含真实外部/时间条件 |
| [24 · 后继候选真实前向启运](issues/24-successor-forward.md) | pending | 已发布，未实施；含真实外部/时间条件 |
| [25 · 后继实验终点验证交付](issues/25-successor-verdict.md) | pending | 已发布，未实施；含真实外部/时间条件 |
| [26 · 增量工程交付与兼容验收](issues/26-integration-delivery.md) | pending | 已发布，未实施 |

## 规划文档检查

2026-10-14：只读结构检查通过：30个Markdown文件、26张连续编号任务、58条连续编号用户故事；本地引用全部可解析，依赖均指向先前票且无环，每票保留pending/NOT_STARTED及验收条件。另检查08没有错误依赖正式动作/LOSS恢复、26没有依赖真实自然时间票。此结果仅说明计划结构通过，不代表产品测试或任何能力已经实施。

## 后续记录约定

### 2026-10-15 启动与交接接受

本轮用户已明确启动，前述 NOT_STARTED 为2026-10-14发布历史。按编号单票推进。详见[交接](handoff.md)：HEAD fe5d01c7…及9份tracked旧修改、6份旧新源码受保护；另一实施会话completed/idle。既有47项日线验收与政策/费用/行动验收按原边界继承；当前3项公开API/隔离SQLite检查通过。默认沙箱socket拒绝和首次测试无输出中止分别保留。只读服务复核8010连接拒绝、8010/5173无监听，不将历史运行状态当当前。02开始补页面查询；完整session/状态/行动覆盖仍不足，原资格NOT_GRANTED，未建立真实前向起点。原P0任务不改写。

每票追加实际基线、继承范围、实现与独立验收、失败/阻塞、剩余条件和下一可执行票。当前没有假定真实起点、资格或资金启用；这份状态不覆盖原P0执行账本。


### 2026-10-15 当前收口与需确认事项

本地集成HEAD将在05-input-consumer提交后记录；01/19/20/21 complete，其余保留表中partial/pending。05补齐原主模型两中心身份、原CAL40会话20概率独立执行，以及来源输入→冻结特征/预测→独立v2状态的METHOD正向管线；不覆盖真实来源权威缺口或实际模型/独立资格。消费者最终API1 PASS/93.32s、Chrome/构建和双审查通过，原15脏文件与12旧模型依赖保留。

当前无已确认契约且工件齐备的新增独立消费者可正向验收。02—04需源证据才能接通REAL；05四非中心拟合工件/独立支持不从手填概率补造；08/23—25另需真实窗口/登记与授权。07仍需选择LOSS恢复语义。09已备独立一次性生产整链脚本及integration-plan.json（600362/8调用/18秒/8MiB/零重试重定向/隔离profile），等待用户确认，不重开已关闭的源评估；09未complete故10—18及22/26依赖仍未解除。没有推送、PR、真实前向起点、资格或真实资金状态变化。

2026-10-15 用户确认07恢复语义与09一次预算；09独立生产整链成功并关闭，票09 complete。07已解除needs-info并进入实施；10/12/14的09依赖已解除，按编号在07之后继续。前文待确认状态为历史快照，不再要求重复授权。

2026-10-15：07原因绑定LOSS恢复工程交付；API总计42通过及已修复旧基线fixture单项通过、子进程2通过、Chrome/构建及双审查证据见07-loss-recovery/acceptance.md。原峰值及历史保留，再次越界重新锁定；未启用真实资金，07保留partial。下一依赖就绪工程票10，复用09采集/原件约定；09已封口预算不重开。

2026-10-15：10 complete，单独用户批准的资产负债/现金流真实验收成功并CLOSED_NO_RETRY：5HTTP、681064B、6.386677秒、10facts；H1三表完整关联，其余语义未知保留。API/SDK、METHOD及真实只读Chrome/构建证据在10-statements/acceptance.md；15原脏文件及12旧模型依赖保持。下一票11依赖解除，复用保存事实做确定性指标，不再额外取数。

2026-10-15：11 complete，复用09/10不可变事实，季度/TTM/同比及同主体比率、营业收入专用字段、零负基期/字段冲突拒算、当前修订与旧截止重放已验。详见11-metrics/acceptance.md；下一依赖就绪票12。

2026-10-15：12工程partial，PDF选页/原件/表格/页边界/API及METHOD验收交付；最终依赖解析600秒达到上限封口，Docling运行时UNAVAILABLE，未下载模型。详见12-docling/acceptance.md。13依赖未解除，下一独立票14；09/10预算保持封口。

2026-10-15：14工程partial，实际新新闻来源一次4HTTP/218675B/10条/3HTML成功并封口，账户不变；METHOD全文与实际SDK传输/API/恢复并发最终4 PASS/33.18s，真实只读Chrome/构建通过。见14-news/acceptance.md。Trafilatura两次有限依赖准备分别元数据超时及TLS超时，运行环境UNAVAILABLE；不重试或冒充真实全文。当前7票complete（01/09/10/11/19/20/21），02/03/04/05/07/12/14 partial；13依赖12、15依赖14，后续情绪/快照/工程整体验收依赖仍未解除。06受05完整冻结/资格缺口、08/23—25受真实来源/冻结/自然窗口等条件阻塞。当前无全部前置条件齐备的新工程票；未完成整份规格，未推送或建立真实资格/资金/前向起点。

### 2026-10-18 14 运行时补齐

新独立依赖尝试 TRAF-DEP-ATTEMPT-04（旧 CLOSED 记录不重开）经环境既有代理访问官方 PyPI，54请求/29.4MB/17.7秒下载并哈希锁定18个 wheel，离线安装 Trafilatura 2.3.1 成功。生产适配器对 14 票实际归档 HTML 运行真实 `bare_extraction`：3/3 EXTRACTED（2663/1760/1115字符，1.51秒），reference 由 UNAVAILABLE 转 VERIFIED 并固定包/文件 SHA256；news 回归 4 passed/47.35秒。14 转 complete，解除 15 依赖。未改变账户、资格、真实前向起点，也不声称全量新闻覆盖。下一票 15。

### 2026-10-18 15 事件归并与关联

新增确定性规范URL/内容SHA256事件归并、注册身份四类关联、别名冲突与多对象，派生表只追加；查询与页面按唯一事件展示转载/修订。METHOD 2 passed（同文异URL/修订/同标题异内容/别名冲突/多对象/重启），news 全套 6 passed/44.71s，构建通过。真实副本 10 条归档新闻：10 唯一事件、4/2/2/2 分类、账户不变，Chrome 1 PASS/11.0s，手工核查 10/10 一致。限制：真实样本无转载/修订，近似改写不合并，身份非时点快照。15 complete，解除 16 依赖；下一票 16（中文情绪）。

### 2026-10-18 12 Docling 运行时补齐

新依赖尝试经代理 250 请求/395MB/88.8s 安装 83 wheel（哈希锁定、离线安装），模型 47 文件/701MB/99.3s（layout Apache-2.0、TableFormer CDLA-Permissive-2.0、RapidOCR PP-OCRv6）。真实解析：三季报第10页 9文本/2表；年报第102—103页（pypdf 零文本扫描页）OCR 22文本/2表并识别真实金额；API COMPLETE、工件 65,938B/115,755B、账户不变、0网络；跨页表头显式不合并。修复子进程 home/username 环境与 NaN JSON 序列化；回归 3 passed/29.18s，真实 Chrome 1 PASS。12 complete，解除 13 依赖；下一票 13（11、12 均已 complete）。

### 2026-10-18 13 财务观察

新增只追加版本化财务观察与公开查询，单股与历史复盘均有折叠入口；文字只来自确定性指标，结论/限制分列。真实 r10real 副本 15 条三表事实：FRESH、2026-06-30、4期趋势、4份PDF、1份真实 Docling 派生、账户不变、0网络；历史截至 2026-04-01 显示缺失。METHOD 2 passed（幂等/修订/行业/禁用源/旧版本不变），财务回归 11 passed/100.9s，Chrome 1 PASS/13.0s。修复当前查询版本膨胀。13 complete，18 的 13 依赖解除；17 仍受 16 阻塞。下一票评估 16 或 18 的剩余依赖。

### 2026-10-18 16 情绪权重与语料诊断

只读核对官方 HuggingFace/GitHub：FinBERT2 仅发布 base/large 预训练与检索模型（apache-2.0），情绪任务只有 Fin-labeler/SC_2 数据集与训练脚本，没有可直接推理的情绪 checkpoint。本仓库归档新闻 10 条标题/3 正文，不足 120 条带标签评测集。16 转 needs-info，未下载权重、未训练、未改依赖；17 及 18/22/26 继续受 16 阻塞。已向用户提出具体选择。

### 2026-10-18 本轮收口与剩余前沿

本轮完成 14（实际 Trafilatura 2.3.1）、15（事件归并/证券关联）、12（实际 Docling 2.139.0 + 官方权重 + RapidOCR）、13（版本化财务观察）。四次本地提交：01f8338、fdbee49、f2cc5fb、a475f12、8a10cc4（16诊断）。真实运行均为隔离 venv、哈希锁定、零隐式重试；账户版本保持0，未授资格、未建立真实前向起点，未推送/PR。

仍 complete 的条件：
- 02/03/04：需权威官方来源契约/原件补齐。03 的 STATUS_A 与 getFpphaseText 定义不在已归档官方JS中；02 的完整会话/RAW修订依据与 04 的当前公告生命周期均需新的有界公开来源尝试（旧 CLOSED 预算不重开）。
- 05/06/08：05 缺四个非中心拟合工件、REAL authority/独立支持与完整冻结；06 依赖 05 的完整派发；08 依赖 02—05 的真实准入。
- 07：真实资金启用条件未满足，工程/规则已完成但保持 partial。
- 16：官方 FinBERT2 只发布预训练 base/large 与 SC_2 训练集，无直接推理情绪 checkpoint；归档新闻 10 条/3 正文不足 120 条标签集，needs-info。
- 17/18/22/26：分别受 16、17（及 13）阻塞；23—25 需真实自然时间/授权。

下一可执行顺序（需用户选择）：(A) 提供许可明确的情绪 checkpoint → 16/17/18/22/26；(B) 授权自训+≥120条标注；(C) 授权并登记 02/03/04 新的有界官方来源尝试 → 逐票补源证据。未选前不伪造完成，不把 partial 改 complete。

### 2026-10-18 03 官方状态文档尝试

STATUS-DOC-ATTEMPT-01 取回 search_HQ_2021.js 与 sse_full.js（2请求/537KB/零重试），但两份均无 kcbShowIconFlag/STATUS_A/getFpphaseText 定义；全状态/风险映射仍无依据，未生成回执、未重开行情预算，03 维持 partial。下一线索需另登记 sse_menufun_2021.js 或状态模块。

### 2026-10-18 16 语料补充

SENTIMENT-CORPUS-01 经 3 次有界请求取得 150 条唯一标题/摘要（73KB、零重试、同上游），数量达到120但仅标题摘要且非独立来源；仍需冻结标签/阈值与许可明确的情绪权重。16 保持 needs-info，未下载模型、未训练、未改依赖。

### 2026-10-18 16 语料构成复核

150 条代码关键词语料经 15 票规则分类：COMPANY_SUBJECT 33 / COMPANY_MENTIONED 28 / INDUSTRY 33 / UNRELATED 29 / UNCERTAIN 27，公司相关仅 61 条，不足以做 120 条公司级情绪标签。下一步改用公司名称关键词的新有界尝试；16 仍 needs-info。

### 2026-10-18 16 最小替代评估

SENTIMENT-CORPUS-02 150条公司名标题摘要；冻结120条代理标签（P45/N24/U18/I33）与门槛后，用 apache-2.0 Erlangshen 二分类模型离线推理：macro-F1 0.853、P recall 1.0、N recall 0.625、低置信拒判9.2%、p95 0.26s；但中性/不相关51条仅3条被拒判，48条强判方向。能力 RESEARCH_LIMITED，16 转 partial；下一轮先冻结拒判规则再重跑并接入API/页面。未授权/未训练 FinBERT2。

### 2026-10-18 16 拒判层与留出验证

冻结 R1—R5 后：设计集 macro-F1 0.956、中性/不相关拒判 0.804；留出集 N recall 0.000、macro-F1 0.333；合并 macro-F1 0.803、N recall 0.500、总拒判覆盖 0.540，未过冻结门槛。能力仍 RESEARCH_LIMITED；下一差量为受限组件的持久化/API/页面，16 保持 partial。

### 2026-10-18 16 受限情绪组件

交付隔离推理/指纹/只追加存储/公开查询/页面限制；真实10条归档新闻运行 POSITIVE2、拒判8、覆盖20%、账户0、0网络；METHOD 1 passed、Chrome 1 PASS、回归5 passed。替代模型合并 macro-F1 0.803、N recall 0.500、拒判覆盖0.540，未过门槛；FinBERT2 权重缺失，16 按验收第6条保持 partial。17/18/22/26 继续阻塞。

### 2026-10-18 交接文档

供后续代理/工程师接手的完整说明见 [handoff-2026-10-18.md](handoff-2026-10-18.md)：分支/HEAD、11 complete、6 partial、9 pending、运行时路径、复现命令、阻塞条件与陷阱。

### 2026-10-18 接手：16 checkpoint核查与指标纠正

现场分支codex/roll-capability-expansion、HEAD b4fb440；上一实施会话notLoaded，379条既有dirty/untracked保留。新独立attempt02—06完成公开元数据核查，官方base/large为MLM；第三方Riverise虽有权重但为环境主题分类且许可缺失，不能作情绪模型。发现Apache-2.0的yiyanghkust/finbert-tone-chinese（约409MB、三分类、非FinBERT2），已请求用户选择替代评估路线，未下载权重或训练。

审查发现旧评测漏计拒判FN与跨类FP，已新增只读纠正工具、真实support/混淆/指标、reference口径版本和页面解释；旧报告/保存包保持可重放。合并150条二类macro-F1纠正为0.563218、正向召回0.867925、负向召回6/30=0.200，总拒判0.540，原门槛未变且未通过。旧120/30日期重叠、holdout无中性支持，精确hash组不证明语义事件隔离；新候选推理前必须重新冻结有效切分。

修改后pytest10 passed/37.93s、构建通过、Chrome1 passed/12.7s；真实已有模型在新副本10条新闻上运行正向2/拒判8/覆盖20%/账户0→0/网络0，旧包不变。初次沙箱无输出、纠正后Windows长路径失败日志均保留；新短临时目录复跑通过。双轴审查和证据见[evidence/16-sentiment/takeover-20261018/acceptance.md](evidence/16-sentiment/takeover-20261018/acceptance.md)。状态仍11 complete/6 partial/9 pending；16未完成，不解除17/18/22/26依赖。无推送、PR、资格、真实资金或前向起点变化。

### 2026-10-19 16中文FinBERT替代：授权评估完成，门槛未过

用户明确允许下载并评估yiyanghkust/finbert-tone-chinese；固定revision e91b1a3a…、Apache-2.0、三分类0中性/1正向/2负向，409103316B权重SHA256 0c25b105…与LFS元数据一致。新attempt01白名单停止、02时间封口、03复制已哈希前缀并Range完成，全部留证且零隐式重试；未改业务依赖。

原150条旧代理标签在候选结果前按保守事件组/09-16时间边界冻结，剔除12条跨边界回顾，138条/35组（开发105、较晚33）。标签仍非独立且曾暴露，不声称新人工未见测试。实际82次模型调用、网络0、无训练、冷启动12.033s、p95 0.241s、峰值约783.5MiB。较晚集合二类F1 0.167、三类F1 0.349、P/N/U召回0.333/0/0.833、I拒判0.800、总拒判0.636；四条N全为前置拒判，不能说模型错判。其不相关构成使覆盖门槛推理前已知不可同时满足，原门槛不改，结果未过。新候选未部署或替换生产reference。

API/指标METHOD pytest6通过/20.00s，构建通过，干净副本/独立端口现有组件Chrome1通过/33.4s；逐条复算、冻结/模型摘要及生产reference不变验证通过。首次模型结果set序列化失败日志保留，仅修复序列化后相同方案重跑。完整证据和双轴审查见[evidence/16-sentiment/finbert-candidate-01/acceptance.md](evidence/16-sentiment/finbert-candidate-01/acceptance.md)。16仍partial；资源选择等待已解除，但新独立事件、对象归属/覆盖协议、真实更正等验收差量未满足，17/18/22/26不解锁。状态仍11 complete/6 partial/9 pending，无推送、PR、真实前向/资格/资金变化。


### 2026-10-19 16新真实语料02：冻结主评测负召回失败

新有界采集03—08共31HTTP、2968599B，1221新新闻索引、148发行人索引、7原件PDF；新主120条P/N/U/I各30、91事件组，另13早期开发及1转载压力样本。对象/拒判先冻结、最终事件/2016时间边界/标签清单在新输出前冻结，边界设计修订透明保留。一次真实CPU推理134条/100模型调用、0网络/未训练，主二类F1 0.7683、三类F1 0.7522、P/N/U召回1/0.3667/0.9、I拒判1、总拒判0.2833、p95 0.095秒；N召回未达0.55，其他数值及支持/隔离门槛通过。非独立代理标签与标题级事实/语气限制保留，不重新标注/删样/调整规则或重跑此holdout。原件/冻结摘要与独立算术复算通过、生产reference不变；METHOD pytest14/构建/现有组件Chrome1通过。见[验收](evidence/16-sentiment/fresh-02/acceptance.md)。仅16有差量且仍needs-info/partial；总计11complete/6partial/9pending，17/18/22/26不解锁。下一仍16：单候选有界训练方案待新授权，或提供契合任务的许可明确checkpoint；未默认训练/启用。其他真实来源/工件/资金/自然时间门槛保持。


### 2026-10-19 16单次训练获授权，数据可行性阶段停止

用户批准一次2 epoch/60分钟本地候选训练。先按授权进行32HTTP/120秒/16MiB取数，实际32/2723000B/62.180秒封口；含25索引查询及7接口契约读取。新公开历史接口/实际页长20已核实；CNINFO page50重复错误保留，page30真实内容翻页修复。训练<=2022、开发2023—24、主留出>=2025在任何模型前固定，旧曝光材料保守排除；原始候选上界243/82/1214，对象投影164/34/225，不能称金标准支持。必要训练400/开发120尚不足，故0训练/0新模型评估，原fresh02负召回11/30失败不改、不降低门槛。摘要/预算/冻结校验通过、METHOD14通过、构建/原组件Chrome1通过，见[验收](evidence/16-sentiment/train-03/acceptance.md)。16仍needs-info/partial、总11complete/6partial/9pending，17/18/22/26仍阻塞。训练权限已解决且未消耗；下一仅语料64请求日历分段提案待新增外部取数预算授权，不能无限追加请求。其余真实来源/工件/资金/自然时间条件不变。

2026-10-19：17完成受限观察工程，证据17-series/acceptance.md；审查发现旧转载覆盖更正/推迟首次消费两个问题，v2及METHOD回归修复，旧快照保留。下一18，22工程依赖亦就绪；26仍缺02/03/04权威来源、05完整拟合/REAL、06、07真实资金，不能标记完成。

2026-10-19：18完成受限观察工程（18-worker/acceptance.md）；默认暂停，旧worker脏字节保留，仅提交两行接入。真实首轮推理45秒超时没有冒充成功；最终事实路径原进程租约/重启/通知/账户通过。通知回归3项旧失败已在pre18模块复现；不改旧P0路径。下一22，26真实前置仍不齐。
