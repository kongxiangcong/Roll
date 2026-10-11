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

2026-10-11 第五指定日期SSE切片：固定官方commonQuery+JS/schema的两页raw-first receipt、SQLite once job、现有worker/current inputs/packet/source-gaps/forward只读消费者与固定原receipt IDs离线重放已交付，错误日期/证券/分页、总数矛盾、四原件损坏、source关闭和字节上限均拒绝/留原。有效红绿之后固定源码受影响32 passed/167.22s，后保存actual raw纯离线caller4 passed/22.00s；合accepted133278d最小组合4 passed/22.65s。一次实际匿名查询只1call/≤2pages，Host请求2026-10-11收到26/total26/page1原件，但queryDate空/searchDate null、无600362且reported starts2024/2025/end全部'-'，不能证明正常/当前日期覆盖/实际复牌；REAL_SOURCE_ASSESSMENT仍system_usable=false/null起点/NOT_GRANTED。原JS大小写/日期格式已只读核，size100采用固定manifest GET变体、非JS默认25/POST-JSONP全前端语义；不追加HTTP。15保护/两固定原件/原19字节checksum前后相同，仅12新own runtimes共2717文件420677469 bytes追加SHA/length保全0diff、旧目标未打开。完整stop/resume/listing/risk/exrights/行动版本/旧义务及yunhq单位仍分具体内部未适配项与源证明缺口，第一项未勾选、Completion partial。见[第五验收与下一有限前沿](../evidence/30-sse-current-suspension/acceptance.md)。

2026-10-11 第五SSE指定日期producer独立接受：归档实际raw13367 bytes/SHA986c403e…eb958离线作为METHOD仍partial，无目标/日期echo不推正常；fixed/empty IDs、4依赖损坏409及worker同日缓存核。首2 passed/1独立harness冷却期错误18.05s保留，正确SOURCE_COOLDOWN0call后仅余案1 passed/9.53s。新2717文件420677469 bytes双侧5434 SHA/length零差异，保护15及原19checksum不变；own213文件23448613 bytes另存仓库外。0新实际HTTP/provider/fit/SEALED/模型或forward/grant/通知。第一项未勾选，Completion partial，原具体producer前沿仍保留。见[第五独立验收](../evidence/continuation-2026-10-11/ticket30-sse-current-independent/acceptance.md)。

2026-10-11 第六new-stock区间slice：固定同官方JS的新commonSoa/GW_PL_JYTS_TFPXX及TRADEDAY调用/typed日期证券分页/先归档finiteplan/raw-first错误与中断prefix、SQLite once worker、新receipt IDs入current packet/sourcegaps/forward只读及原空/非空IDs离线重放已交付。真实TDD红绿后定向24 passed/112.43s，保存actual2raw纯离线caller3 passed/18.84s；合accepted6bb32bab最小4 passed/24.10s，后合accepted27/77f729最小3 passed/18.63s，计数分列不作全suite。独立预算trade-day1+interval最多2/共≤3，实际仅2call、Host2026-10-11T09:20:35.730578Z→36.112711Z：beforeTradeDay20261009，600362请求20261009–20261011/pageSize25返回[]/total0/pageCount0/日期echo空，额外lastTradeDay20261015只保留raw不猜角色；不造normal/无事件/最新日验证/实际复牌，system_usable=false/起点null/NOT_GRANTED，不再实际请求。15保护/固定JS及旧空raw/原19字节checksum前后一致，仅12新t30i目录2728files/375082862bytes及独立composition27目录153files/20080223bytes追加保全0diff，全部旧目标未打开；source018536c，第一项仍未勾选、Completion partial。完整生命周期/上市风险/当前yunhq单位及行动版本和旧义务仍有明确内部producer与来源证明缺口；下一有限公司页/声明JS入口已指名，不能归因用户通知配置。详见[第六验收与下一有限前沿](../evidence/30-sse-stock-suspension/acceptance.md)。

2026-10-11 第六new-stock切片独立接受：source stable `f44d1685a808fcba976007ea3e0fc14d218f93c6` no-ff合入 `f34b5aad2e0e14569a0dc88cfd925c9cda5ccb61`，保留handoff后a205仅docs的时间边界。首公共API3 PASS/1 harnessFAIL43.08s、剩余case前置缺watch1 FAIL6.63s及诊断str→Path错误均保留；公共watch/identity+account0合法交易日后仅同案1 PASS7.53s，不称整4绿。已核实际2raw1080B离线仍UNKNOWN、旧空/非空receipt IDs重启重放、三依赖409、typed日期/证券/分页拒绝、有界3及source-off0call、共享worker重启cache与27真实paused WORKER三次heartbeat零新capture/既存facts可读。2881新文件395163085B双端5762 SHA/length0diff，15保护/原19checksum不变；merge后9源码及实际2raw/固定2依赖root/source bytes和Git身份一致。自身498files60255359B含失败合成METHOD基线/诊断全存仓库外，exact source+harness CIM0。Completion仍partial、第一项未勾选、完整真实producer缺口及NOT_GRANTED/null前向起点保持；0新真实HTTP/provider/fit/forecast/SEALED/真实账户/资格/外发，未push/cleanup。见[第六独立收据](../evidence/continuation-2026-10-11/ticket30-stock-independent/acceptance.md)。

2026-10-11 第七company-client合同slice：固定官方HTML72bdf9/JS478fb2原SHA/317019B，两个精确源的typed raw-first/先归档server finiteplan、Decimal原值与同renderer量÷100/额÷10000展示尺度、完整phase及首字符映射、公司上市描述/上市日/opaque STATUS_A、source policy/SQLite once job/现有worker/输入包固定receipt IDs/sourcegaps/只读forward消费及离线重放已交付。有效receipt/IDs/Decimal red→green；合同19案18 passed/1测试policy旧路径harness failure90.16s保留，修正公开policy URL后只同案+2既有worker3 passed/19.38s，中断prefix/计划1 passed/6.35s；合accepted8fa8c81后实际保存原件纯METHOD与caller组合3 passed/19.25s，不作全suite合并计数。parser cae8f942/source00165b0与两次实际取数前计划ed8d4d1固定；新预算总≤2实际HTTP，实际恰2、Host2026-10-11T10:17:33.540249Z→38.054441Z，停止无重试回退/第三call/新文档查询。snap409B/bc097123返回Friday20261009/162905、volume31419158/amount1314805240、全E110及独立fp原值；company1732B/4e4bd767返回匹配600362/主板A/上市/A_LIST_DATE20020111，queryDate空与状态生效/风险enum仍UNKNOWN。原值转换是document-bound未舍入商，不据phaseE/上市/零或空推正常、full/session/current completion；SOURCE_ASSESSMENT仍partial/system_usable=false/起点null/NOT_GRANTED。15保护/旧refs/原19 byte checksum前后相同，4公开原件Git byte身份0diff；11新t30u目录1577files/181872574bytes追加SHA/length保全0diff，旧保存目标未打开，own进程收口、无provider/fit/forecast/SEALED/实际资金授权/通知。第一项未勾选、Completion partial；仍可离线实现本exactselect价格/换手原字段caller，full日完成/风险生效/当前行动版本/旧未结义务分具体内部与requiredsource缺口，不归因用户配置。详见[第七验收与下一有限前沿](../evidence/30-sse-company-contract/acceptance.md)。

2026-10-11 第七company-client切片独立接受：stable53c5d576（source00165b0，已合handoff时accepted8fa）no-ff合入39a7bdb2；root44b129b后置2docs修正不改产品，未retro改owner。独立新METHOD publicAPI/真实SQLite3 passed/30.30s，核snap409B/company1732B的原精度/同renderer换算、fullphase与独立fp、Friday不抬Sundaycomplete、opaque上市描述/风险与累计session覆盖UNKNOWN、systemfalse/forwardnull/NOT_GRANTED；旧空/非空IDs同cutoff追加及重启固定、3依赖损坏409、Decimal大值/未来日/prefix与cap2/关闭源0call/cache、27真实paused WORKER三heartbeat零新capture且既存事实可读。1577新件181872574B双端3154 SHA/length0diff，保护15/原19checksum同；合后6source-mapping/4公开原件root/source raw及Git身份一致。own280files34125902B全保存仓库外/exact CIM0；sandbox runtime locator与CIM denied诊断保留。原owner18PASS/1harnessFAIL90.16及后相关3PASS、prefix1、final3PASS19.25按阶段原样，不升级整套。Completion仍partial、第一项未勾选，0新真实HTTP/provider/fit/forecast/SEALED/资金或资格/实际forward/通知，不push/cleanup。下一可离线实施exactselect价格/OHLC/换手源绑定successor，不需新call；full每日完成/全状态/行动版本与旧义务仍需具体producer/sourceproof，非通知配置阻塞。见[第七独立收据](../evidence/continuation-2026-10-11/ticket30-company-independent/acceptance.md)。

2026-10-11 第八离线价格successor：仅固定JS478fb2与已存409B行情，新增显式source_receipt_id价格assessment、精确Decimal五价格/OHLC与换手151÷100=1.51%、专用PRICE_SUCCESSOR包/固定原packet+assessment IDs/截止重放、typed current及source-gaps消费。原post_close/company文件与cae8f942全局指纹、旧receipt/packet原fact与ID未变，无自动重解析历史字段；Friday stale/P1不能当前显示，QUOTE不是DAILY/session完整/状态授权。真API404红绿后有限22 passed/104.33s；新发现已拒绝非object source500真RED1 failed/5.95s修409后受影响7 passed/35.62s，合accepted582最小current E/P1+既有sourceworker IDs+27未授权pause caller4 passed/21.33s，各阶段分列不称整24全绿。保护15/旧refs/指定原件与原19字节checksum未变，0新实际HTTP/文档/provider/fit/forecast/SEALED/实际前向/资格/通知，所有新t30q运行件独立SHA/长度追加保全见专用receipt，旧保存件未打开。第一项未勾选、Completion partial；具体行动查询/原ID版本/完整status与旧义务仍分内部producer和requiredsource缺口，下一两精确SQL有限plan仅提案未执行，非通知配置等待。详见[第八验收](../evidence/30-sse-price-quotes/acceptance.md)。
