# 30: 盘后唯一前向归档与研究终点

**What to build:** 程序运行且冻结实验可运行时，在预登记盘后检查点归档一次预测或明确缺失，记录实际前向起点、最迟终点与成熟结果，让用户看到真实研究进度。

**Blocked by:** [15 · 按需与盘后观察、覆盖时间线](15-on-demand-review.md)；[20 · 冻结研究政策与连续影子](20-policy-continuous-shadow.md)。

**Status:** ready-for-agent

**Completion:** partial

**Primary acceptance:** AT-58、AT-88。

**References:** [规格](../spec.md) ID-09、ID-14、ID-15、ID-16、ID-18；Testing Decisions 的主要边界 1、2、5、6 及“时点与有限研究”；[目录与实施约束](../project-layout.md)。

## Acceptance criteria

- [ ] 程序运行、检查点合法且冻结实验具备所需完整输入时，由一个后台进程结合 SQLite 持久化任务调用共同应用用例，保存预测、动作或拒绝原因及实际依据，不引入 DAG 或分布式队列；不要求交易时段常开，条件不满足保留具体缺口，不自动改成合格样本。
- [x] 确认性样本身份按实验及预登记检查点/交易日固定，独立于任务键、账户版本和数据快照；重复触发、重试、新快照或手动点击可有关联记录，但不能增加确认性样本或 PASS 判定点。
- [x] 首次成功持久化冻结模型的实际前向预测才登记 forward_started_at 和 forward_deadline；创建实验、部署、导入历史或测试 fixture 均不能启动真实计时。失败或崩溃不能留下无实际归档的伪起点。
- [x] 按冻结时区、自然月加法/月末及截止边界计算不晚于起点加三自然月的终点，不能用 90 天替代；缺席、重试、换取证后端和不利结果不延期，预登记较早停止条件保留可追溯依据。
- [x] 停机缺日不补预测；后来行情仅能补事实或按政策结算既有预测，恢复不重置影子。拒绝机会也在结果发生前记录，成熟后反事实诊断不混入连续策略收益。
- [x] 终点到达时按协议关闭本轮采样/判定边界，已成熟与未成熟项分列；不足形成 INCONCLUSIVE 及实际审阅状态，未完成验证/审阅仍标明缺口，不提前判未成熟结果输赢或为其自动续期。
- [x] 经 FastAPI、真实 SQLite/文件和必要真实进程故障验证唯一归档、提交边界与恢复；用可控时钟覆盖月份、月末、截止及标签成熟边界。工程模拟时间只证明算法，实际首次归档及真实终点分别由 32、33 执行留证。
- [x] 遵守目录与实施约束；仅引入本票实际需要的模块、接口和校验，保留 PRD 必需控制，不新增假设性兼容层、审批或泛化框架。

## Comments

2026-10-07：按已确认拆分发布；尚未实施或验收。

2026-10-08 本轮依赖前沿核查：未启动本票。20冻结模型/政策/连续影子未完成；15已完成。保留原分诊标签和全部验收要求，不用合成样例关闭任务；实际解锁后继续。整体执行证据见[实施记录](../execution-status.md)。

2026-10-11：共同前向归档/成熟结算/停止与原截止恢复工程已实现，METHOD使用同一状态机；第一项仍欠真实完整输入 producer 与实际准入闭合，因此 partial。现真实host状态/权益原件UNKNOWN不能最小映射为完整字段，无客户端complete/PASS覆盖。最终23个定向案例单轮22绿/1新增夹具失败，夹具经公共账户/身份前置修正后同案单独1绿；五OS进程及三共享worker/审阅入场通过。Chrome1/48.1s、build59模块/2.05s，原始SQLite及公共查询均无真实起点；八METHOD运行目录SHA/长度保全。七项勾选表示30工程条件验证，不代替32实存或33真实终点。详见[验收和真实缺口](../evidence/30/acceptance.md)。20既有分红/同日卖出P2另由根安排修复，当前工件收据按原时点保留；未推送。

2026-10-11 收口补充：等价UTC截止重放公共API红→datetime修正；最终9公共API96.84s、新Chrome48.0s/build1.90s通过。最终源码11文件前后一致，11METHOD目录保全；核心收据与修正版各自留证，Completion仍partial。

2026-10-11 producer 续推：增加固定 SSE 原件先归档、严格日期/收盘时间/Decimal 校验、持久化有界 source job、原件后/提交前真实 OS 故障恢复；输入包与 forward 消费者保留全部状态来源、金额/单位/范围冲突、原 ordinal/batch、采集失败回执与规则/cash 原件绑定。相同 cutoff 后更正不改写旧包，失败后明确成功仍可离线重放旧失败包。一次匿名 SOURCE_ASSESSMENT 实际收到星期五原响应，不能作星期日当前完整输入或历史预测；endpoint 单位/成交范围未独立证实。14 份已知现金实施 PDF 及字段映射保持原 SHA/字节，不能证明当前完整行动或无事件。第一项仍未勾选，Completion 仍 partial：完整当前停复牌/风险子类型、listing/relisting、ex-rights/当前行动及旧未结义务的权威来源 routes/parsers 尚未全部实现，另有实际交易日完整 closing/单位/范围证明缺口。不能归因于用户通知配置，不能因 parser/METHOD 通过自动解锁 31/32。具体支持/未适配维度、下一最小步骤与真实/工程收据见 [producer 验收](../evidence/30-producer/acceptance.md)。

2026-10-11 producer 检查收口：补修前固定源码综合 51 passed / 416.38s（公共 API/真实 SQLite/原件/source+forward OS/既有 prospective 与 CNEquity），随后历史失败范围公共 API red 1 failed / 8.73s → 日期范围 green 1 passed / 8.13s；当前源码受影响 producer/forward adapter/assessment-binding 固定轮 25 passed / 127.79s，未重复未变的 OS 事务。源码、12冻结19来源/参考、validation/shadow/statistics 和原始19 SQLite前后一致；各阶段分列，不把以前计数称为当前完整轮，仍无实际前向起点。

2026-10-11 producer 有限历史续推：在前轮独立接受后仅离线消费已固定6份官方 SSE public 原件（360501 bytes / SHA-length 0差异），实现历史daily自身单位、单日停牌返回/日期边界、78/78分页及0/10/early-empty具体audit，注册独立source-assessment并接入post-close包、原assessment IDs离线重放和只读source-gaps。历史单位不补yunhq、报告结束日期不造复牌/当前正常、finite结果不造无事件/完整覆盖；原received_at与本次normalized_known_at分列。TDD三条valid red后8关联场景通过；固定源码受影响33 passed / 192.57s，合入31后最小app/worker/source-job/history组合3 passed / 21.91s。15保护源码及6原件前后一致，无rootSQLite/账户/旧保全件打开、新网络或实际模型/时钟/授权。当前STATUS/listing/relisting/行动覆盖仍有具体内部未实现项；已有CNINFO历史candidate/paging schema列为下一有限前沿，不能因无2026范围转成用户外部等待。Completion仍partial、第一项未勾选。见[本轮确切范围、原件及收据](../evidence/30-producer-followup/acceptance.md)。

2026-10-11 CNINFO有限历史前沿：只读取既有manifest指名6个唯一公开raw（17848 bytes/0差异）、保留8个2013—2025关键词请求和24个唯一候选，实现count/unique/原totalpages/日期请求审计、opaque公告索引时间、修订取消关联线索UNKNOWN，以及13个公告ID+PDF原定位精确现金链接。已知现金1202538463未被关键词返回单列gap，14原PDF映射及独立inventory保持原样。新增独立CNINFO assessment进入共同包/只读source-gaps/固定原IDs离线重放；历史范围、2/2且totalpages0、关联ID和空返回均不造当前coverage/noevents/PIT/生命周期。两个valid red→green后7关联API通过；固定源码受影响40 passed/222.29s，15保护源码及SSE6/CNINFO6原件前后0差异。当前区间全行动/实际分页/修订取消/旧未结义务及完整STATUS仍有明确内部未实现项与原件不足；不是用户通知配置等待。第一项仍未勾选、Completion partial、无真实起点/授权。详见[本轮接口、证据及具体剩余项](../evidence/30-cninfo-history/acceptance.md)。

2026-10-11 本批组合收口：合accepted25与runner最终integration ed936ce后最小4公共API/worker/caller组合 passed/27.25s，首次2.47s测试support导入collector环境错误单独保留，不称产品red或执行通过；后续c2bf931仅docs合入未重跑。新7自有测试目录分两目标追加保全2657文件/381402022 bytes/0差异，不读写旧13989/2570保存件，不SQLite-open、不清理worktree。后续当前行动缺口分current区间/分页覆盖caller、revision/cancellation生命周期消费、older obligation审计三项，分别列现有消费者字段、尚未写的内部路径与required sources，待本批独立接受后再开有限slice；Completion仍partial。

2026-10-11 known-obligation有限内部slice：已映射14实施notice按已登记protocol design/horizon及source-bound日历形成reference window，逐notice保留原ID/PDF SHA/record-ex-payment DATE精度与cutoff分类，履行/取消/延期/owned entitlement/resolved全部UNKNOWN，不凭付款日推到账、pending或无义务。新增audit API/SQLite追加归档/按protocol查询及inputs、packet、source-gaps、forward只读消费者；旧包固定原audit IDs，同cutoff追加不能重选。有效TDD red后10公共API与1只读consumer通过，当前固定源码受影响31 passed/174.91s、15保护Git/source参考无diff；未训练/读SEALED/新HTTP/实际model-forward-grant。12新自有目录2749 files/403639159 bytes/0差异追加保全，不读写旧保存件/实际root DB。完整当前行动区间、修订取消/全部旧未结义务、STATUS及yunhq单位仍有具体内部未适配项与原件不足，第一项仍未勾选、Completion partial。见[本轮验收及下一有限可执行slice](../evidence/30-known-obligations/acceptance.md)。

2026-10-11 本片最终组合：原source fbca固定31案后，合7c761最小4 passed/29.60s；26独立accepted0d33179后另跑新audit/current未授权caller2 passed/16.85s，未把旧轮升级成新26完整检查。后61bb仅docs合入，无重复测试；两个新独立composition保存目标追加299 files/41255770 bytes/0差异，本片总3048 files/444894929 bytes，旧13989/2570/2657未读写、不SQLite-open、不清理树。下一有限SSE指定日期停牌receipt/消费者计划已附权威入口、原schema边界及有限验收，本轮不追加网络/源码；Completion仍partial。

2026-10-11 known-obligations第四切片独立接受：公共API首2 passed/1 harness KeyError20.99s，public status字段修正后仅单例1 passed/23.69s；3048新文件444894929 bytes双侧6096 SHA/length零差异，保护15及原19checksum不变。固定14原schedule/reference20/UNKNOWN状态、旧空与非空audit IDs、协议隔离/restart/损坏409已核，无新HTTP/fit/SEALED/真实前向或资金资格。第一项未勾选，Completion仍partial；完整当前行动与STATUS/单位等内部producer缺口保留。详见[独立收据](../evidence/continuation-2026-10-11/ticket30-obligations-independent/acceptance.md)。
