# 28: 有效通知与当前状态深链

**What to build:** 用户在站内和一个已配置的自用外部渠道接收有意义的提醒；重复信息合并，重要新增风险可升级，旧消息链接打开当前状态和失效原因。

**Blocked by:** [27 · 暂停、撤回、到期与恢复](27-suspend-revoke-recover.md)。

**Status:** ready-for-agent

**Completion:** partial

**Primary acceptance:** AT-24。

**References:** [规格](../spec.md) ID-11/12/13/17/18、Testing Decisions；[任务计划](../ticket-plan.md)；[目录与实施约束](../project-layout.md)。验收场景原文以 [PRD](../../../ashare_market_decision_prd.md) 为准，补充追踪 UI-07、EVAL-05/06/16 的送达边界与执行时间依据。

## Acceptance criteria

- [x] 从已持久化且符合条件的事实/动作产生 SQLite 出站记录，经发送、失败/未知结果、站内查看及深链查询形成完整路径；按需要行动、需要同步/恢复、阶段摘要区分。重启和重试不重复创建业务通知，不承诺外部供应商无法保证的严格恰好一次送达。
- [x] 动作通知出站记录引用动作版本；各类通知分别保存发送尝试、渠道受理、可证明的送达和已读时间及证据来源，供 26/29 关联执行时间链。发送成功或渠道受理不推定用户收到、已读或已操作；无回执或渠道不支持时对应状态/时点保持未知，晚到回执保留实际时点与系统获知时间，不改写旧发送记录。
- [x] 去重依据动作、状态与严重程度；普通波动、重复新闻、文字变化不产生新提醒。重大新增风险或关键失效可越过普通冷却，常规重复仍合并；摘要频率是上限而非强制每日发送。正常未运行不持续制造故障通知。
- [x] 将通知去重/合并、重复发送风险、失败及送达未知接入 15 的运行审计，保留出站、发送尝试和渠道回执的对应关系；分别统计业务通知与传输尝试，不把一次重试必然当成用户收到两条。联验真实内部出站链的重复/未知记录、异常定位及重启后的计数一致性，外部无法证明的结果继续保持未知。
- [x] 每条通知有有效期。动作通知出队前重新核对最新动作、账户、相应资格、资金和依赖状态；事实、同步与恢复提醒检查自身时效和适用状态，不以模型 grant 存在为前提。过期入场机会仅归档；发送期间撤权保存失效事件并按需追加提醒，已发出的内容不可偷偷改写，不声称可以消除外部传输竞态。
- [x] 深链查询当前状态，能解释旧卡已到期、被替代或撤回；旧消息不能建立新有效意向。研究内容不进入行动通知；客观风险提醒不能夹带未经授权的卖出/持有建议。
- [ ] 选定一个实际可配置渠道并登记版本、认证、内容/长度、超时重试与送达语义；在用户配置的自用验收目标上完成真实受控发送、失败与当前状态链接检查，不联系第三方。无配置或不可达时站内功能继续并明确需打开查看；外部真实验收未完成不得记通过。
- [x] 经 FastAPI 与真实 SQLite/出站记录覆盖 AT-24、撤权竞争、冷却/过期、失败/送达未知；真实进程在出队前后终止并恢复，检查业务记录及供应商未知结果处理。与 26 联验有发送记录但无送达/已读证据、延迟回执和延迟回报的时间链，供 29 验证报告不推定用户响应；浏览器打开旧通知验证当前状态。固定响应检查与实际渠道证据分别记录。
- [x] 遵守目录与实施约束；仅引入本票实际需要的模块、接口和校验，保留 PRD 必需控制，不新增假设性兼容层、审批或泛化框架。用单进程与 SQLite 出站记录解决当前需求，不预建多渠道消息中台。

## Comments

2026-10-07：按已确认拆分发布；尚未实施或验收。本票补全 27 的真实通知出队/在途联验；渠道接入和工程消息不能证明策略通过或真实交易行为发生。

2026-10-07：补齐发送、送达/已读证据及与 26/29 的时间链联验，并将通知指标接入 15 的运行审计；仅补充文档，尚未实施、发送验收消息或取得送达证据。

2026-10-08 本轮依赖前沿核查：未启动本票。27当前撤权/恢复生命周期未完成。保留原分诊标签和全部验收要求，不用合成样例关闭任务；实际解锁后继续。整体执行证据见[实施记录](../execution-status.md)。


2026-10-11 用户明确当前范围：先完成站内通知和外部渠道配置页，实际发送待用户配置。按[范围修订](../notification-scope-2026-10-11.md)完成内部出站/时间链/恢复/深链工程；未配置外部实际验收仍pending，整体不写通过。真实外部发送前不得自行选第三方目标。

2026-10-11 当前内部工程实现：三类站内通知、语义合并及重大变化、不可变来源/消息与追加事件、当前深链、显式站内已读、默认关闭的单ntfy私有配置、SQLite worker出站及唯一显式重试、26时间链已形成；21公开API+2真实自有OS crash单轮23 PASS/130.30s，Chrome1 PASS/14.3s（含失败token脱敏的最终流程另列1/14.3），TS/Vite65模块/2.01s。具体固定输入、方法和实际结果见[工程回执](../evidence/continuation-2026-10-11/ticket28/acceptance.md)。勾选项仅表示当前授权内部工程，尚待独立合并验收；外部用户自用目标未配置、真实发送/外部送达验收均未执行，Completion保持partial，不以Mock/loopback或测试数量关闭原AT-24全部要求。

2026-10-11 最小调用方组合4PASS/1FAIL：既有动作审计重复失效登记在原accepted root也重现，原失败保留并已交上游修复；本票补验同实质失效反复开卡只一条重大通知1PASS/6.87s。运行件六组1,218公开文件100,247,004bytes源/根双侧2,436逐SHA/长度0差，35个精确私有配置/锁只登记排除metadata，未读取/hash/copy。15保护源和原19checksum unchanged；无模型/fit/forecast/SEALED/真实账户授权/外部ntfy调用。最新上游修复接受后最小caller收据将追加，不改旧日志。

2026-10-11 收口长度修正：合法1600中文暂停原因超过渠道4096UTF8 bytes，红灯证实会挡住后续事实提醒。仅出站正文超过限额时改用短当前链接提示，站内原消息/来源不改；不可变attempt显式记录正文投影原因。新源相关出站5PASS/23.16s，2组198公开运行文件15,686,482bytes双侧396逐SHA/长度0差，10个精确私有配置/锁不读取/hash/copy；旧23项源绑定结果保留为历史，不冒充该修正后全量复跑。整体仍partial/真实外发0。

2026-10-11 最终accepted25/30组合：own no-ff a988c93合eb060fd；唯一失效插入seam冲突保留上游首次事实门禁及本票仅首次insert的通知hook。全109当前源/测试身份固定后fresh公开current/outbox2PASS/10.77s/exit0，原current审计红在新上游源修绿，原红/原23项/OS/Chrome/build/长度5项仍各自保留源码版本，不求和。新增72公开运行件5,682,523bytes保全，新与旧完整manifest共1,488文件双侧2,976逐SHA/长度0missing/extra/mismatch，47精确私有配置/锁仅metadata排除；CIM自身0，15保护/原19checksum unchanged，未打开保存SQLite。当前稳定交接供独立内部验收和29调用方接续；真实ntfy0，Completion仍partial，外部实际验收待用户配置。


2026-10-11 内部范围独立接受，可解锁29只读报告caller：stable83c9289d（含accepted25 eb060fd）no-ff1387bdd2，fresh METHOD独立公共API/真实SQLite4 passed/21.30s，核首次失效audit1/CRITICAL notice1/旧message-eval immutable/重复current不追加/重启计数；4800UTF8中文保留站内原文并记录≤4096短投影，不挡后续账户fact；26持久意向的readonly时间链反复GET不advance/不改intent/audit、RESULT_UNKNOWN无自动resend，显式站内read与后late report occurrence/reported/known分列；disabled config保存0发送。3exact保全namespace1488public files121616009B双2976SHA/length0diff，47private路径只metadata不读取/hash/copy，15双树/原19checksum同；合后109source/test root-own raw/Git同。own132public files9481336B仓库外全保全/6自身private配置锁metadata排除/exactCIM0。原23/OS/Chrome与4PASS+1旧FAIL、长度5PASS23.16、当前109源2caller10.77分阶段保留，不改历史或组合计数。Completion仍partial，实际ntfy0/NOT_EXECUTED/PENDING_USER_CONFIGURATION，未知delivery/read不阻29读取已登记内部chain；不把内部接受变成真实外发PASS、G门禁/资格/自然前向成功。未fit/provider/SEALED/真实账户/授权/外部HTTP/push/cleanup，root两dirty docs未stage且merge前后bytes同。详见[独立内部验收](../evidence/continuation-2026-10-11/ticket28-independent/acceptance.md)。
