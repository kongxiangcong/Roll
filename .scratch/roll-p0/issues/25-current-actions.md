# 25: 有资格的当前动作与联合预算

**What to build:** 用户按需分析时，在资格、资金、账户、数据与证券规则均允许的范围得到唯一当前动作及可执行条件；条件不足时看见具体限制和客观事实。当前报价、量价事实与最近完整日线概率分别标注时点。

**Blocked by:** [09 · 账户估值与现金流调整绩效](09-valuation-performance.md)；[15 · 按需与盘后观察、覆盖时间线](15-on-demand-review.md)；[22 · 独立风险回退政策](22-independent-risk-policy.md)；[24 · 确定性资格签发与范围核验](24-capability-grant.md)。

**Status:** ready-for-agent

**Completion:** partial

**Primary acceptance:** AT-15、AT-16、AT-22、AT-30、AT-34、AT-87。

**References:** [规格](../spec.md) ID-05/09/10/11/12/13/17/19、Testing Decisions；[任务计划](../ticket-plan.md)；[目录与实施约束](../project-layout.md)。验收场景原文以 [PRD](../../../ashare_market_decision_prd.md) 为准，补充覆盖 1.3、AUTH-04、DEC-02—05、RUN-02 及附录 B 的损失触发口径。

## Acceptance criteria

- [ ] 经应用入口完成评估、持久化、查询与“今天”/单股页展示。复用 20 的冻结政策计算，按能力与模式、系统/数据、账户/资金、证券规则、独立风险回退、模型适用性、存量/新增机会、联合预算、发布前版本复核的顺序作确定性检查；硬失败不能被评分抵消。
- [ ] 单独检查用户确认的账户交易权限及适用范围，与市场/板块证券规则、模型技术资格和资金授权分别保存检查结果。账户未开通或权限未知时限制依赖该权限的新增动作，不能因证券规则已适配、模型合格或资金充足推定可交易；已存在持仓及已发生事实继续显示和受理。
- [ ] 每个正式动作按 basis_type 核对相应依据的有效资格；无对应资格不产生 BUY/ADD/HOLD/REDUCE/EXIT 或判断型 WAIT。收益模型 UNGRANTED/停用而独立回退 ACTIVE 时，仍可在该政策覆盖范围内产生合格降风险动作；无回退资格时不得把风险事实转成回退动作。未知可卖量、买入当日不可卖、未知规则、用途陈旧数据各返回具体限制，不假设可清仓或应持有。
- [ ] 当前有限名单按冻结优先级和稳定排序联合分配现金、数量和暴露，纳入费用与用户授权保留额。两条机会不能合计超支，默认同时最多一条新增入场意向；新增卡片数量限制不隐藏存量持仓风险。不扩大股票池或放宽阈值凑机会；反向动作和冷却遵守同一冻结政策，报价刷新不任意翻转，政策变化保留持仓迁移安排。
- [ ] 联合预算调用 10 中用户确认并版本化的损失触发口径和剩余额度计算，使用 09 的估值/绩效证据，明确账户或授权范围、计算起点、外部现金流调整及已实现/未实现损益。陈旧或缺失估值按已登记政策处理，无法判定时限制依赖它的新增风险，不按零损失或正常额度放行；每日切换、资金转入和价格反弹不能擅自重置累计损失或恢复已暂停能力。
- [ ] Decision 持久化动作及各项账户、数据、模型、执行、资格状态，绑定依据类型、grant/资金/账户/数据/模型/政策/规则版本；卡片列明当前/目标数量、价格范围、生成与数据截止、期限、触发/失效条件、依据和不确定性。已发布内容不覆盖，变化形成后继；价格触发不改真实账本。
- [ ] 盘中调用展示实际可得报价/累计成交时点与最近完整日线预测的独立截止及期限；未完成成交量不得进入完整日线模型，未合格概率留在研究视图。缓存陈旧不重标为当前，相关正式动作按用途失效或限制新增风险。
- [ ] 从 FastAPI 公共入口使用真实 SQLite、隔离归档和测试专用合成资格覆盖上述 AT；固定全部结构化输入重放，动作、数量、有效条件与依赖一致。联验 01 的账户交易权限、09/10 的损失口径与剩余额度、两机会联合预算以及评估/发布间用户缩小授权后立即拒绝超出新边界的动作；已有动作失效和意向竞争在 26/27 接续联验。浏览器验证时点、可卖/权限限制、陈旧估值受限和无资格页面；确认合成资格无法进入生产授权链。
- [ ] 将实际动作的后继、失效、拒绝原因与反向变化接入 15 的运行审计，可追溯账户、资金、模型/政策及输入版本；固定输入不重复计数，实际变化不被“无实质变化”吞掉。26 补齐意向指标、28 补齐通知指标后完成其责任范围的联验。
- [ ] 在记录的设备、30 只个股与 5 个指数、实际冻结候选配置下测一次名单本地评估 P95 ≤ 30 秒；外部取证计时独立记录。测试与性能证据随本票交付，不延至 31，也不据此宣称真实 G1—G7 通过。
- [ ] 遵守目录与实施约束；仅引入本票实际需要的模块、接口和校验，保留 PRD 必需控制，不新增假设性兼容层、审批或泛化框架。

## Comments

2026-10-11 独立接受：最终source759033c8的五状态Spec修复经新增3项FastAPI/真实独立SQLite验收PASS/18.89秒；profit绑定自身BUY grant，风险model NOT_APPLICABLE与自身REDUCE/EXIT grant，METHOD_ONLY、零可卖BLOCKED无伪Decision，GET/replay/重启和生产METHOD拒绝均通过。原4fc2403的31 PASS与held缺口保留历史边界，没有重复或升级旧suite/浏览器/benchmark。新增1201档案2402次来源/目标SHA/长度核0差异，1934/2922保全条目在3135中未改写，15保护及原19 checksum匹配，最终source_inventory与当前benchmark收据一致。工程范围独立接受complete；真实研究仍FITTED_UNVALIDATED/NOT_GRANTED，不提前声明26/27意向/成交、28外部发送或30当前源producer完成。独立记录见[状态修复验收](../evidence/continuation-2026-10-11/ticket25-independent/decision-states/acceptance.md)。

2026-10-07：按已确认拆分发布；尚未实施或验收。26 接入实际执行意向后，再联合验证占用去重、部分成交和账户入账导致现存动作失效；本票不提前伪造这些实际结果。

2026-10-07：补齐账户交易权限、损失口径/剩余额度、陈旧估值和即时缩权的动作检查及运行审计衔接；26/27 接续验证现存动作/意向失效。仅补充文档，新增要求尚未实施或验收。

2026-10-08 本轮依赖前沿核查：未启动本票。24资格签发未完成；09/15/22已完成。保留原分诊标签和全部验收要求，不用合成样例关闭任务；实际解锁后继续。整体执行证据见[实施记录](../execution-status.md)。

2026-10-11：已在独立票25工作树完成当前动作公共入口、冻结20/22复用、联合费用/保留额预算、版本化损失、资格/权限/规则/数据限制、同SQLite发布与查询复核、不可变后继/失效/重放及今天/单股展示。当前partial的语义为implemented-awaiting-independent-acceptance，父代理独立接受后改为complete。实施检查与独立验收分开：24 API cases PASS（20 actions +4 CODEX-only）、审计1 PASS、Edge主流程1 PASS与陈旧估值/UNKNOWN购买权限/可卖0股拒绝分支各1 PASS、TypeScript/Vite PASS。性能使用实际冻结模型/校准参数和当前应用路径，在30 METHOD持仓+5指数上21 samples P95=0.4026603秒；1只冻结范围内数值路径，29只范围外拒绝，不称30只合格。全部原始红/fixture错误及旧性能收据保留，详见[票25验收记录](../evidence/ticket25/acceptance.md)和[已接受实施边界](../evidence/ticket25/plan.md)。

2026-10-11：METHOD工程证据不关闭真实资格；现有研究仍 FITTED_UNVALIDATED/NOT_GRANTED，真实费用/当前状态/完整日线及正式用途未满足时保留具体拒绝。冻结20只覆盖BUY/REFUSE；`POLICY_FOR_ADD_HOLD_WAIT_REVERSAL_COOLDOWN_NOT_FROZEN`为既有政策缺口，不创造ADD/HOLD/判断型WAIT/反向或冷却。独立22/24风险政策覆盖合格REDUCE/EXIT。26/27继续意向竞争/占用/入账，28按用户决定先站内通知和外部配置页，真实外部发送等用户配置。本票等待父代理独立接受；分诊标签保持原词汇，没有将METHOD或未验证的后续结果升级为真实完成。

2026-10-11 最终收口：补已有幂等receipt计算期间的缩资/名单/过期writer复核；同一个具体SQLite边界核对账户/资金、持久grant/恢复状态、已接受数据/名单/估值/forecast/风险评估、loss peak与expiry，拒绝形成新不可变修订，查询原记录及replay保持不变。已合root 2db3bd1（30producer、CODEX-only），source修复8911282/merge6fa0a951的公共actions23 PASS/130.29秒及组合5 PASS/28.45秒；当前源完整本地21 samples P95=0.4863553秒，各层计时保留。旧0.4026603秒及四个浏览器后端源均明确为历史检查，前端字节不变。损失峰值6000跨重启/扩容保持PAUSED，扩容后的算术余额4000不恢复新增风险；原fixture包改写与错期望两个红例保留且不修改既有保护/公式。停止METHOD档案保全由977追加957至1934文件，全部来源/目标SHA256及长度0差异，12冻结源/三只读模型资料/原19 SQLite不变。详见[当前验收记录](../evidence/ticket25/acceptance.md)，仍partial等待独立接受。

2026-10-11 独立Spec复验修复：原source4fc2403独立31例PASS/201.74秒但DEC-01/ID10要求的account_status/data_status/model_status/execution_eligibility/capability_status未在Decision行显式保存，故held，不将输入archive当作满足行字段。source e3a4a56最小投影现有用途/数据/依据/执行与自身grant状态；风险model NOT_APPLICABLE，METHOD执行METHOD_ONLY，拒绝/可卖0 facts BLOCKED，旧immutable不补写。公共profit红1→绿1、risk红4→绿4；投影stage23 API PASS/134.57秒、6组合PASS/34.20秒。已先合root7390ccef（31），后合c3fe7d8及docs-only28fd34d；30历史来源改变source_inventory后仅最小3组合PASS/18.90秒及一次当前source21 samples P95=.4157914秒，未重复未变23/6/旧31/浏览器。投影stage .4361794与投影前.4863553全部保留历史source区分。原1934追加988+213至3135 stopped METHOD文件，来源/目标SHA/长度0差异；12冻结源、三allowed模型资料与原19 SQLite不变，最终source_inventory等于benchmark。字段值形状/来源见[投影说明](../evidence/ticket25/decision-state-projection.md)，仍partial待父代理独立复验接受。

2026-10-11 历史运行材料追加保全独立接受（仅 preservation）：已接受源759033c8保持干净，新增10108文件824294955字节与旧五份清单去重3135文件264329777字节，共13243文件1088624732字节。独立26486次双端SHA/长度检查零差异，实际13249条运行路径仅六个已由受控测试定义溯源的auth fixture排除；这些文件未读取、哈希或复制。当前15保护源及原19 SQLite仅校验且不变，精确25进程清单0；长路径检查器首次WinError3诊断保留，修检查器后84.44秒exit0。父代理复制15份原始回执并逐文件核对字节，没有新业务测试、资格升级或清理。见[独立保全回执](../evidence/continuation-2026-10-11/ticket25-preservation-additional/roll-ticket25-preservation-independent-report.md)及[复制核对](../evidence/continuation-2026-10-11/ticket25-preservation-additional/root-receipt-copy.json)。源工作树保留，清理另行核对。

2026-10-11 当前审计 DEC02/MON03 有限差距修复（待独立接受）：新自有 tree ticket25-ordering 从已接受8fa8c81实施；公开双独立 METHOD grant 的 literal REDUCE100→BUY200 红例先证实旧 BUY→REDUCE，再最小前移既有风险计算。收益 policy 缺失/不支持、无自身收益 grant 的不可解析概率均真实500红→独立风险100可发布绿，收益无权输入不进入冻结数值政策。新10公共例 PASS/44.45秒，第二新机会限额不遮风险，预算仍包含现有30000暴露，不用计划减仓释放资金；风险NOT_APPLICABLE、METHOD_ONLY与自身grant五状态保持。必要测试专用supplier仅根PROFIT_MODEL+唯一risk_qualification子RISK_POLICY，全外包SHA/archive/current源码绑定、不同材料/审阅/proof及自己的五gates，共享事实冲突/子失败gate/生产/损坏envelope拒绝。受影响19组合18 PASS+1已独立证实的旧基线审计红/95.87秒（同动作第二次current因派生reason插重复ACTION_INVALIDATED）；该红与排序修复分开，父代理另授权独立最小去重，旧档案不覆盖。未改保护15/冻结数学/阈值、实际模型/provider/forecast/资格及原19SQL，未升级真实G门禁。

2026-10-11 独立追加授权的旧动作失效事实去重（待独立接受，单独commit）：ordering组合保留的2vs1红由28在root8fa独立复现。新的公开literal先红1/6.49秒，最小复用同SQLite writer快照下已有decision失效标识，仅首次转换append ACTION_INVALIDATED；后续当前原因继续完整返回，旧事件/评估一律不删不改。绿2/11.28秒覆盖原资金缩权两次current，以及新真实METHOD账户声明version3的ACCOUNT_VERSION_CHANGE仍可经public版本/receipt定位、旧evaluation/replay不变、重启后事件及audit仍1。该修复与排序2faf033分commit与证据，不碰28模块/受保护15或原19SQL，详见[独立失效事实修复记录](../evidence/ticket25-invalidation/acceptance.md)。

2026-10-11 本修复最终交接：排序2faf033与独立失效去重541103c分离；合accepted7th870b451后fresh69源码绑定METHOD证明/两个公共caller PASS/12.56秒，再合docs-only5827edfe不重跑。全部2039自身运行档案154331607字节已追加至新ticket25-ordering namespace，4078双端最终SHA/长度核0差异，无private排除、SQLite连接或删除，CIM自身0；现15保护源双树30核、另外3模型/校准/config字节及原19仅checksum均不变。旧10 PASS、19组合18PASS/1基线红、去重2绿分源保留，没有新benchmark/浏览器或全19 PASS声明。树与旧25档案继续保留，待独立接受；见[本修复验收边界](../evidence/ticket25-ordering/acceptance.md)。


2026-10-11 排序+单次失效事实独立工程接受：stable9332d0cd（已合5827edfe）no-ff77f53ffd；新独立fresh METHOD公共API/真实SQLite5 passed/32.86秒，核同账户REDUCE100→BUY200、第二ONE_NEW_ENTRY、现有30000暴露/10005buy预算不借计划减仓释放；unsupported policy及无profitgrant坏概率不遮独立风险，自身risk/profit grant/NOT_APPLICABLE/METHOD_ONLY分列；缩权后double current仅首次ACTION_INVALIDATED immutable，后账户声明version3的ACCOUNT_VERSION_CHANGE仍可定位，旧eval/replay及重启audit1同；整档child SHA/共享facts/failed自有gate与production拒绝已核。新2039files154331607B双4078SHA/length0diff、15双树/allowed3模型校准config/原19 checksum/旧6保全manifest及旧guard不变；合后69source及2生产+3testfixture raw/Git root-own同。own229files16173385B全存仓库外，exactCIM0，读元数据syntax诊断保留。原10PASS44.45、受影响19的18PASS+1基线FAIL95.87、单去重2PASS11.28和当前source2caller12.56分阶段保持，未重标全19绿。Ticket25工程complete保持，实际NOT_GRANTED；0新actualHTTP/provider/fit/forecast/SEALED/正式资金或资格/通知，不push/cleanup，不改rootdocs。见[独立排序/审计修复收据](../evidence/continuation-2026-10-11/ticket25-ordering-independent/acceptance.md)。

2026-10-11 最终内部规格审阅责任回写：既有独立接受的风险排序、预算、失效去重和五状态工程证据保持；整票 Completion 改为 partial。当前冻结收益政策仅覆盖 BUY/REFUSE，ADD/HOLD/判断型 WAIT、反向、冷却及版本化持仓迁移未登记。生产 capture 仍缺实际费用，且把有效期置为已到的 required 截止，不能发布当前正式动作；安全拒绝不等于生产输入契约已实现。这些缺口分别回 20 的政策责任及本票 production capture，不能以 METHOD 或能力标题修复关闭，不补造金融参数、费用、未来有效期或真实资格。见[最终双轴审阅](../evidence/continuation-2026-10-11/final-review/review.md)第5项；四项 P2 的最小修复另留验证和独立接受收据。

2026-10-11 最终双轴审阅修复（等待独立复验）：修正 host 当前展示真值，已接受 METHOD/action 发布仍保持严格 source binding；缺冻结风险费用在29报告保留 None/UNKNOWN。四项内部工程修复不解决本票既存政策/生产费用与有效期输入 partial，不补金融政策或改变冻结 producer。见 [本轮回执](../evidence/final-review-fix/acceptance.md)。
