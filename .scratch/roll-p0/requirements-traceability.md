# Roll P0 需求与证据追踪

2026-10-11用户[后端范围修订](provider-scope-2026-10-11.md)覆盖本表旧双后端要求：当前及后续仅CODEX，DeepSeek不测试、不计完成缺口；旧证据按原时点保留。AT-51仍由23负责真实Codex技术审阅，不用METHOD或排除DeepSeek替代Codex证据；其余统计、资金、真实前向及资格门槛不变。

日期：2026-10-07。依据：[PRD V1.3](../../ashare_market_decision_prd.md)、[规格 1.1](spec.md)、[34 票计划](ticket-plan.md)。本表补充原有 90 项 AT 主责任映射，覆盖 14 项 BR、125 项编号 P0 要求、10 项数据不变量及无编号的核心正文/附录约束。摘要用于定位，不缩减 PRD 原文。

## 维护与完成口径

- 主责任票负责对应条款的完整证据索引；票号链接直达该票 Comments。实施时记录条款号、固定输入、预期/实际结果、版本/环境及日志、截图或回放链接，并将本表“待实施”更新为“通过／部分／失败／未执行＋实际证据链接”。这些是验收结果，不替换任务的分诊 Status。
- 联验票承接真实调用方出现后的集成检查；本表不增加 Blocked by。主责任票可先完成自身切片，但整条需求只有必要联验证据齐全后才可关闭，未完成部分须保留。
- 31 核对工程证据；32、33、34 分别补真实启运、协议终点及条件性启用证据。工程样例通过、未来真实验证待执行须分别记录，不以整行“通过”混写。未启用时按 PRD 允许的分支验收，不要求真实下单或伪造长期运行数据。
- 90 项 AT 保持 [任务计划中的唯一主责任](ticket-plan.md#验收主责任映射)。无独占 AT 的条款也须有行为样例；不能以“已引用 PRD”代替通过证据。PRD 后续修订时先核对新增/删除条款，再调整对应责任票。

## 不可变产品边界

| 条款 | 验收关注 | 主责任 | 联验 | 当前证据 |
|---|---|---|---|---|
| BR-01 | A 股范围、无跨市场扩展 | [06] | [31] | 部分：06有限沪深范围、未知北交所和未适配资产完整保留已验；31独立本机安装/worker切片已接受，完整五入口及条款交付仍待完成。[06](evidence/06/acceptance.md)、[31独立](evidence/continuation-2026-10-11/ticket31-independent/acceptance.md) |
| BR-02 | 无券商交易写能力与交易凭据 | [13] | [01]、[31] | 待实施 |
| BR-03 | 真实账户仅确认事实入账 | [01] | [02]、[04] | 通过：01基线、02成交及04现金/权益均经草稿/明确确认写入，外部线索不自动到账；[01](evidence/01/acceptance.md)、[02](evidence/02/acceptance.md)、[04](evidence/04/acceptance.md)。工程账户样例不代表用户财富 |
| BR-04 | 意向和触价不推定成交 | [26] | [25] | 工程通过：26 prepare/外部待结果不改现金或持仓，只有原账户确认链写实际成交；部分/超量/无关联不强行推定执行归因。[26独立](evidence/continuation-2026-10-11/ticket26-independent/acceptance.md)、[分阶段](evidence/ticket26/acceptance.md) |
| BR-05 | 持仓与有限关注，不做全市场选股 | [06] | [07]、[25] | 工程通过：06/07有限范围及25当前名单复核、超额持仓仍可见、最多一条新增卡片已验；移出名单拒绝旧卡，指数不生成个股动作。正向仅METHOD、实际NOT_GRANTED。[25](evidence/ticket25/acceptance.md) |
| BR-06 | 按需/盘后与实际影子记录，缺席不补造 | [15] | [30]、[32] | 部分：15按需/盘后、正常关闭/休眠/恢复不补造通过；30/32实际影子未验；[15证据](evidence/15/acceptance.md) |
| BR-07 | 用户无需选模型或裁决投资观点 | [25] | [15]、[31] | 25工程通过：今天/单股共用宿主当前动作与五项显式状态，不需用户裁决模型观点；实际资格不足明确拒绝。31完整交付联验待完成。[25](evidence/ticket25/acceptance.md)、[五状态独立](evidence/continuation-2026-10-11/ticket25-independent/decision-states/acceptance.md) |
| BR-08 | 量化验证约束概率与判断 | [21] | [19]、[24] | 工程通过：21验证清单区分概率支持、门槛结果与资格；24公共准入拒绝缺项和客户端自签。真实G4/G5 FAIL、其他INCONCLUSIVE/NOT_GRANTED；[21](evidence/21/acceptance.md)、[24独立](evidence/continuation-2026-10-11/ticket24-independent/merge-acceptance.md) |
| BR-09 | 合格条件下允许有依据的无机会结果 | [25] | [20] | 部分：25在冻结BUY/REFUSE政策内给出可追溯拒绝和不足，不造默认WAIT；ADD/HOLD/判断型WAIT/反向/冷却政策尚未冻结，真实资格仍NOT_GRANTED。[25行为及缺口](evidence/ticket25/acceptance.md) |
| BR-10 | 当前动作优先、低噪声与少操作 | [15] | [25]、[28] | 部分：15首屏顺序及25今天/单股共用当前卡片、重复查询不重复计失效事件已验；28通知未验。[15](evidence/15/acceptance.md)、[25](evidence/ticket25/acceptance.md) |
| BR-11 | FAIL/INCONCLUSIVE 可验证交付 | [33] | [23]、[34] | 待实施 |
| BR-12 | 资格、资金、健康分开且可撤回 | [24] | [10]、[27] | 部分：10资金与24确定性资格/健康分列及缩权受限已验；27完整生命周期调用方待验，未启用真实资金。[24独立](evidence/continuation-2026-10-11/ticket24-independent/merge-acceptance.md) |
| BR-13 | 日线范围，不要求分钟路径 | [19] | [07]、[18] | 19工程及限定真实重建通过：固定20交易日日线事件，原价/单位/上下文/已生效现金权益；不引入分钟预测，不代表严格历史PIT或真实前向。[19](evidence/19-reconstruction-2026-10-10/acceptance.md) |
| BR-14 | 可替换取数、按需补查、关键复盘核验 | [08] | [11]、[12]、[14] | 部分：08真实自动换源/缓存/修订及11实际Codex补查/缺口/离线回放已验；12真实另验，14已验关键触发/独立性不足/冲突/复用失效/真实原件及15关联，[14证据](evidence/14/acceptance.md)，[08](evidence/08/acceptance.md)、[11](evidence/11/acceptance.md)；12补充实际SDK受控补查工程/页面方法通过，真实DeepSeek待凭据，needs-info/partial，[12工程证据](evidence/12/acceptance.md) |

## 编号 P0 要求

| 条款 | 验收关注 | 主责任 | 联验/真实证据 | 当前证据 |
|---|---|---|---|---|
| AUTH-01 | 技术资格、资金授权与健康取交集 | [10] | [24]、[25] | 工程通过：10/24交集及25发布前最新资金、名单、到期、估值复核已独立接受；正向仅METHOD_ENGINEERING，生产拒绝，真实NOT_GRANTED。[25最终独立](evidence/continuation-2026-10-11/ticket25-independent/decision-states/acceptance.md)、[25分阶段](evidence/ticket25/acceptance.md) |
| AUTH-02 | 能力绑定指纹、范围、账户与期限 | [24] | [22]、[25] | 工程通过：24逐grant及25自身grant绑定、重启重放、源变更拒绝旧proof已验；风险资格不能充当收益资格，正向仅host METHOD。[24独立](evidence/continuation-2026-10-11/ticket24-independent/merge-acceptance.md)、[25最终独立](evidence/continuation-2026-10-11/ticket25-independent/decision-states/acceptance.md) |
| AUTH-03 | 授权生命周期、到期与后继记录 | [27] | [24]、[28] | 待实施 |
| AUTH-04 | 确定性准入、用户启用及缩权 | [24] | [27]、[34] | 部分：24客户端自签拒绝、host METHOD逐条件准入、资金缩权与生产METHOD拒绝已验；27恢复生命周期及34实际条件启用未完成。[24](evidence/24/acceptance.md) |
| ACC-01 | 现金、可用、冻结、持仓和批次分列 | [01] | [02]、[09] | 通过：01字段分列、02实际FIFO批次、09原价估值和冻结不重复扣已联验；[01](evidence/01/acceptance.md)、[02](evidence/02/acceptance.md)、[09](evidence/09/acceptance.md) |
| ACC-02 | 手工/文件先草稿再确认原子提交 | [03] | [01]、[04] | 通过：03整批原子确认、04配股CSV2及05更正CSV3后继已联验，三版本语义保留；[03](evidence/03/acceptance.md)、[04](evidence/04/acceptance.md)、[05](evidence/05/acceptance.md) |
| ACC-03 | 精确金额、数量与舍入守恒 | [01] | [02]、[09] | 通过：字符串精度、费用前FIFO/单扣费用、送转/配股/迟补费及净资产恒等式已联验；[02](evidence/02/acceptance.md)、[09](evidence/09/acceptance.md) |
| ACC-04 | 存量基线与历史/可卖未知 | [01] | [09]、[25] | 工程通过：01/09未知保留及25按确认可卖量限制独立风险动作；可卖0或未知不猜数量、不造Decision。正向仅METHOD。[09](evidence/09/acceptance.md)、[25独立](evidence/continuation-2026-10-11/ticket25-independent/decision-states/acceptance.md) |
| ACC-05 | 逆建议成交受理、矛盾输入隔离 | [02] | [26] | 工程通过：02实际事实不从建议推定；26明确多对多分配、超量/无关联及UNKNOWN/CONTRARY关联不强行归因，实际成交仍由原确认链受理，过量分配整笔回滚。正向为隔离METHOD。[02](evidence/02/acceptance.md)、[26分阶段](evidence/ticket26/acceptance.md)、[26独立](evidence/continuation-2026-10-11/ticket26-independent/acceptance.md) |
| ACC-06 | 已确认成交与暂估费用分开 | [02] | [09]、[26] | 工程通过：02暂估/追加费用与09费用前估值、未知费用不当零已联验；26部分成交分配保留原费用对象及实际事件/回执，费用不代替成交关联。29后续偏差报告仍待实际调用方验收。[02](evidence/02/acceptance.md)、[09](evidence/09/acceptance.md)、[26](evidence/ticket26/acceptance.md) |
| ACC-07 | 分红、税费、利息、送转确认与对账 | [04] | [05]、[09] | 部分：04现金/权益、05分项对账及09净资产/绩效已联验；09修复应付10/支付10双更正8的实际关联路径，旧知识和原件保持10，CSV/真实崩溃通过；14独立性/原公告单源不足与无账户写门禁已验；真实个人外部权益双源未建立仍不得确认到账，[14](evidence/14/acceptance.md)；[04](evidence/04/acceptance.md)、[05](evidence/05/acceptance.md)、[09](evidence/09/acceptance.md) |
| ACC-08 | 分笔身份、导入去重与歧义 | [03] | [02] | 通过：文件SHA/原行、可靠分笔去重/原回执、同价同量分笔与无标识跨文件歧义均实测，[03证据](evidence/03/acceptance.md) |
| ACC-09 | 幂等、版本竞争和原子回执 | [01] | [03]、[26] | 工程通过：26在账户writer同事务写事实/分配/余量/版本/回执/动作失效，独立reader提交前仍见旧版；过量分配整笔回滚，实际before/after_commit恢复及重试唯一。[26独立](evidence/continuation-2026-10-11/ticket26-independent/acceptance.md) |
| ACC-10 | 双时间、当前重建和旧动作失效 | [05] | [26]、[27] | 部分：05双时间及26实际发生/草稿回报/系统获知分源保存，旧卡同writer失效且不可变日志可追溯；27撤权/恢复生命周期待验。[05](evidence/05/acceptance.md)、[26独立](evidence/continuation-2026-10-11/ticket26-independent/acceptance.md) |
| ACC-11 | 外部委托待结果不推成持仓 | [26] | [27] | 26工程通过：显式外部order identity/待结果/对账不足保留，不假定撤单；已反映冻结随账户版本变化转UNKNOWN并保守占用。27暂停后仍可见待联验。[26](evidence/ticket26/acceptance.md)、[独立](evidence/continuation-2026-10-11/ticket26-independent/acceptance.md) |
| ACC-12 | 确认截至时点与新风险入口声明 | [05] | [26] | 工程通过：26 prepare在同writer使用用途/截至时点声明及最新账户、资金、grant、价格/动作条件；失效旧prepare重试先拒绝再查prior，不借旧回执放行。[26独立](evidence/continuation-2026-10-11/ticket26-independent/acceptance.md) |
| ACC-13 | 现金、可用、数量、可卖分别对账 | [05] | [09] | 通过：05分项对账/未知差异与09对账现金不猜利润、部分结算/双税更正联合守恒已验；[05](evidence/05/acceptance.md)、[09](evidence/09/acceptance.md) |
| ACC-14 | 账户未知仍展示事实、不猜动作数量 | [25] | [05]、[22] | 工程通过：25未知购买权限阻断新增风险，客观事实及持仓风险可见；确认可卖量独立检查，不以购买权限关闭自动抹去风险，不猜未知可卖量。[25](evidence/ticket25/acceptance.md)、[独立](evidence/continuation-2026-10-11/ticket25-independent/decision-states/acceptance.md) |
| ACC-15 | 估值时点、冻结不重复扣、应收应付单列 | [09] | [04] | 09范围PASS：原价/独立报价时点、冻结不重复扣、未结单列与部分结算/税费双更正守恒；真实旧价STALE，API/Chrome/OS证据见[evidence/09](evidence/09/acceptance.md) |
| ACC-16 | 可用资金、意向和授权保留额去重 | [26] | [25] | 工程通过：26券商净可用不再扣已反映冻结；未反映意向/用户保留额联合限制新增风险，partial100剩余100占用15002.50；REDUCE不误用BUY现金门槛，未知不当零。[26独立](evidence/continuation-2026-10-11/ticket26-independent/acceptance.md) |
| ACC-17 | 成本、费用、净投入与现金流调整绩效 | [09] | [02]、[04] | 09范围PASS：费用前FIFO/送转/配股/迟补费、外部流与收入独立、修正Dietz及NAV恒等；[evidence/09](evidence/09/acceptance.md)。25/27正式消费仍PARTIAL |
| ACC-18 | 基线前未知不伪造收益或隐藏资产 | [09] | [01] | 09范围PASS：未知历史/期初价格/费用保留null，当前资产有依据时可见，资金起点/旧版本不可改；[evidence/09](evidence/09/acceptance.md) |
| ACC-19 | 连续影子不被真实账本重置 | [20] | [29]、[30] | 部分：20连续影子、非空基线与实际账户补录隔离已公开API/重启重放验收；29分类出口未验，30有限归档不代表真实完整前向。[20](evidence/20/acceptance.md)、[独立20](evidence/continuation-2026-10-11/merge20.md) |
| ACC-20 | 账户条件诊断与四类结果隔离 | [29] | [20] | 待实施 |
| MON-01 | 交易日历、时区、休市与停牌区别 | [06] | [15] | 06完成：沪深2026原件/上海时区/休市阶段及未知范围通过；15消费年度与临时停市区别，[证据](evidence/06/acceptance.md) |
| MON-02 | 触发不等于数据齐全，补查/缺口显式 | [15] | [08]、[13] | 部分：15/08实际未齐/有限补查、原件/知识截止及局部缺口通过；13最终预算交付未验；[15证据](evidence/15/acceptance.md) |
| MON-03 | 能力先查、持仓风险与有限新增机会 | [25] | [07]、[15] | 工程通过：25先查自身grant与用途，再查当前数据/账户/资金/规则；独立风险不借收益资格，超额持仓保留、最多一条新增卡。实际正式资格未授予。[25](evidence/ticket25/acceptance.md)、[独立](evidence/continuation-2026-10-11/ticket25-independent/decision-states/acceptance.md) |
| MON-04 | 盘前只用当时可得输入与原预测时点 | [15] | [19]、[25] | 部分：15实际事件/可得截止和原记录不改通过；19/25真实概率时点/资格未验；[15证据](evidence/15/acceptance.md) |
| MON-05 | 报价、条件观察、预测和训练分开 | [15] | [19]、[25] | 工程通过：15分列输入，25保存报价/累计量时点和完整日线截止，研究概率不当正式当前预测。25性能检查仅用既有冻结模型与METHOD特征，无新拟合。[25](evidence/ticket25/acceptance.md)；真实资格仍NOT_GRANTED |
| MON-06 | 未完成日线不进模型、概率时点不偷换 | [25] | [07]、[15]、[19] | 工程通过：25未完整日线/用途过期/原forecast依赖不足显式拒绝，报价及盘中累计量不当完整日线；固定输入每次重新捕获/计算，发布前短事务复核。[25分阶段](evidence/ticket25/acceptance.md) |
| MON-07 | 触价不入账，失效条件限制旧动作 | [25] | [26] | 工程通过：25条件/最新版本复核及26prepare不入账；确认实际partial成交后旧卡同事务失效，旧prepare409，余量要求重新评估。[26独立](evidence/continuation-2026-10-11/ticket26-independent/acceptance.md) |
| MON-08 | 重复状态合并与重大风险越过冷却 | [28] | [15]、[25] | 待实施 |
| MON-09 | 盘后变化/执行/账户/成熟结果分列 | [15] | [18]、[26]、[29] | 部分：15盘后市场/账户/实际运行审计分列；18执行标签服务已合但26/29真实结果消费者仍未联验；[15证据](evidence/15/acceptance.md) |
| MON-10 | 阶段前后继时间线与无实质变化 | [15] | [25] | 部分：15保存前后快照/无实质变化/不猜未观察顺序通过；25正式动作时间线未验；[15证据](evidence/15/acceptance.md) |
| MON-11 | 离线覆盖缺口与过期机会不补发 | [15] | [28]、[30] | 部分：15实际OS正常关闭/崩溃、存活心跳缺口、恢复事实不造预测通过；28/30实际通知/前向样本未验；[15证据](evidence/15/acceptance.md) |
| MON-12 | 任务幂等与确认性样本唯一 | [30] | [15]、[28] | 待实施 |
| DAT-01 | 可复现量价背景，额外特征须增量证据 | [19] | [07]、[21] | 待实施 |
| DAT-02 | 聚合背景不扩股票池，降级只用合格版本 | [08] | [07]、[19]、[25] | 待实施 |
| DAT-03 | 实际来源能力、工具与失败语义登记 | [07] | [08]、[11]、[12] | 部分：07真实registry/实际调用及失败语义通过；11锁实际SDK/runtime/model/工具并验证真实多轮/错误；12另验，[07证据](evidence/07/acceptance.md)、[11证据](evidence/11/acceptance.md)；12实际Agents0.23.1/OpenAI3.26.0/DeepSeek固定协议与有限工具已登记；实际服务权限/模型未验，[12工程证据](evidence/12/acceptance.md)。2026-10-10新增CNEquity固定源码／隔离运行时、来源策略审计／健康／冷却与实际成功失败分列，[接入证据](evidence/cnequity-integration-2026-10-10/acceptance.md) |
| DAT-04 | 当前名单/指数正常与异常样例验收 | [07] | [06]、[08] | 部分：07有限名单/三固定背景真实样例、异常METHOD_CASE与当前UNKNOWN通过；待08用途检查，[证据](evidence/07/acceptance.md) |
| DAT-05 | 事实对象、时间、口径与原始出处 | [07] | [11]、[12] | 部分：07对象/事实时间精度/原件SHA/快照/观察通过；11同DataRequest/Run接入，实际网页原文/候选原件/时点/宿主校验、Sina选择与必需字段继承通过；12另验，[07证据](evidence/07/acceptance.md)、[11证据](evidence/11/acceptance.md)；12同DataRequest/Run、SINA与必需字段继承/候选SHA短引校验方法通过；实际外部取证未验，[12工程证据](evidence/12/acceptance.md) |
| DAT-06 | 原始归档先行、版本修订与离线重放 | [08] | [07]、[14] | 部分：08真实两源原件/修订记录、Observation依赖失效、原07版本及ReplayRun零联网重放通过；14已验核验原值/原字节修订失效/旧UUID与原Parquet复放，后续完整后端隔离另验，[14](evidence/14/acceptance.md)，[证据](evidence/08/acceptance.md)。2026-10-10前向CNEquity实际响应先归档、清洗隔离／源值冲突／修订和中断登记／SQLite-Parquet篡改拒绝／一致备份通过，当前取得不补旧PIT，[新证据](evidence/cnequity-integration-2026-10-10/acceptance.md) |
| DAT-07 | 标识、单位、缺失、零值和日线完成度 | [07] | [19] | 部分：07显式身份单位/零与缺失/日历/完成度/必需字段边界通过；新增SOHU RAW手/万元转换、冲突限制与SSE历史日历，历史阶段未知；待19真实模型输入，[07证据](evidence/07/acceptance.md)、[公共来源续推](evidence/continuation-2026-10-09/acceptance.md) |
| DAT-08 | 原价/调整价及行情调整/实际到账分开 | [07] | [04]、[09] | 部分：07原价/qfq版本与分派待核分离、实际除息上下文通过；待09真实权益核对联验，[证据](evidence/07/acceptance.md) |
| DAT-09 | 用途新鲜度与原预测截止时点 | [08] | [15]、[25] | 部分：08真实缓存不刷新年龄、消费自己的知识截止/用途及交易所session、局部缺口/当前监控限制通过；待15/25真实预测与动作截止联验，[证据](evidence/08/acceptance.md) |
| DAT-10 | 换源语义一致、独立性不按工具计票 | [08] | [14] | 部分：08实际Sina/Tencent报价逐对象/日/Decimal字段及单位依据比较、有界自动日线补查通过；14已验两工具原链未证仍不足、同源只算一次、时点/口径门禁及METHOD正例，不把真实价格相同签独立，[14](evidence/14/acceptance.md)，[证据](evidence/08/acceptance.md) |
| DAT-11 | 日期粒度保守可用时点、占位不当价格 | [07] | [17]、[19] | 19重建用途边界通过：原接收/发布时间与研究完成假设分列，空价停牌/缺行不压缩，严格PIT仍拒绝；不扩大07正式资格。[19实际证据](evidence/19-reconstruction-2026-10-10/acceptance.md)，[07旧证据](evidence/07/acceptance.md)保留 |
| DAT-12 | 可用联网工具补查、无能力如实缺失 | [13] | [11]、[12]、[15] | 部分：11实际受控GET补充茅台官方网页、其他对象/事项与时点如实缺口；12/13/15另验，[11证据](evidence/11/acceptance.md)；12固定HTTP三轮工具接续与无能力缺口方法通过；真实DeepSeek补查未执行，[12工程证据](evidence/12/acceptance.md) |
| DAT-13 | 最小取证上下文、结果证据与权限边界 | [13] | [07]、[11]、[12] | 部分：11独立配置/认证、技能0/空指令源、有限工具/进程预算、真实敏感能力对抗/取消/崩溃通过；12/13共同边界另验，[11证据](evidence/11/acceptance.md)；12独立空home/cwd、最小工具/上下文、脱敏与有限Job取消/崩溃工程通过；真实模型和13共同边界仍待验，[12工程证据](evidence/12/acceptance.md) |
| DAT-14 | 证据复用、限额停止与局部缺口 | [13] | [08]、[15] | 待实施 |
| DAT-15 | 仅关键复盘触发独立核验 | [14] | [15] | 已验：明确三类关键触发，普通观察/日审计不升级；15冻原对象/事实/知识截止，14显式消费同ID原子关联audit；共享输入限制及旧命令可行动拒绝[修复](evidence/review/fixes.md)，真实原件Chrome及METHOD/OS分层，[14证据](evidence/14/acceptance.md) |
| DAT-16 | 至少两个独立原始依据而非 Agent 计票 | [14] | [13] | 已验：原始生产链门禁/同源只计一次，至少两独立可比依据；真实Sina/Tencent原链未证/原公告单源均不足，METHOD一致正例隔离，不按工具或Agent计票；13另验，[14证据](evidence/14/acceptance.md) |
| DAT-17 | 原值保留、冲突/不足与局部暂缓 | [14] | [08]、[15] | 已验：时点/口径/单位/源基本校验先行，原值保留，CONFLICT与INSUFFICIENT分开、逐字段暂缓，其他已核部分继续；原字节修订失效/原件损坏和零联网复放通过，[14证据](evidence/14/acceptance.md) |
| DAT-18 | 账户事实由用户确认，补查不改过去输入 | [14] | [04]、[05] | 已验：14核验不签账户/到账成交/模型资格，真实联合账户与原观察不变；原可得时点/知识截止和修订前输入保留，后知材料不足，04/05事实确认责任不变，[14证据](evidence/14/acceptance.md) |
| MOD-01 | 一个透明候选与必要简单基线 | [19] | [17]、[21] | 19通过：真实固定四特征/λ1/20日，CASH/DEV基础发生率/单机会持有/MA5/20；连续NAV/确认性优势另待后续。[证据](evidence/19-reconstruction-2026-10-10/acceptance.md) |
| MOD-02 | 预测绑定事件、期限、交易方案和适用域 | [19] | [17]、[20] | 19通过：真实重建Forecast绑定证券/20日/两种时钟/模型/CAL/执行/现金/费用/范围/支持及不确定性，重启0外网重放；不授正式能力、不冻结完整政策。[证据](evidence/19-reconstruction-2026-10-10/acceptance.md) |
| MOD-03 | 固定日线费用后事件与收益情景 | [19] | [18] | 19通过：实际成熟单机会经济标签、历史法定费用+明确佣金滑点+现金税负、DEV逐机会情景；未定不标负、不拼NAV。[证据](evidence/19-reconstruction-2026-10-10/acceptance.md) |
| MOD-04 | 日线歧义、未成交/部分/未退出结果定义 | [18] | [20] | 18工程通过：保守/区间/T+1/停牌零量/终止现金；真实120不可评分，20联验待执行。[证据](evidence/18/acceptance.md) |
| MOD-05 | 训练/校准/测试时间隔离及可靠性 | [19] | [21] | 19真实DEV1148/CAL444时间隔离拟合与工件冻结、21验证清单及独立重放工程已验；CAL拟合不等于独立校准有效性，FITTED_UNVALIDATED。实际G4/G5 FAIL、其他INCONCLUSIVE/NOT_GRANTED。[19](evidence/19-reconstruction-2026-10-10/acceptance.md)、[21独立](evidence/continuation-2026-10-11/merge21.md)；旧失败保留 |
| MOD-06 | 评分、校准、入选子集和支持度 | [21] | [19]、[29] | 待实施 |
| MOD-07 | 不合格概率隔离与独立回退资格 | [25] | [19]、[22]、[29] | 待实施 |
| MOD-08 | 收益、尾部、回撤、占用及覆盖联合评价 | [21] | [17]、[20] | 待实施 |
| MOD-09 | 市场状态与未来收益预测分开 | [25] | [15]、[19] | 待实施 |
| DEC-01 | 动作与账户/数据/资格状态分别保存 | [25] | [10] | 工程通过：五项状态分别持久化、公开GET/replay及重启一致；风险模型NOT_APPLICABLE，零可卖量BLOCKED且无伪Decision。[25最终独立](evidence/continuation-2026-10-11/ticket25-independent/decision-states/acceptance.md) |
| DEC-02 | 确定性顺序与发布前权限检查 | [25] | [20]、[24]、[27] | 部分：25按冻结顺序检查且已有幂等回执不能绕过最新资金/名单/到期/估值；27生命周期调用方待验，实际未授权。[25分阶段](evidence/ticket25/acceptance.md) |
| DEC-03 | 新增风险硬约束与有依据的 WAIT | [25] | [10]、[20] | 部分：冻结BUY/REFUSE及权限、资金、名单、数据硬门禁已验；ADD/HOLD/判断WAIT/反向冷却政策未冻结，明确命名缺口，不造默认WAIT。[25分阶段](evidence/ticket25/acceptance.md) |
| DEC-04 | 联合数量、损失预算与压力假设 | [25] | [09]、[10]、[18]、[22] | 工程通过：25联合Decimal现金/费用/保留额、损失起点与cashflow、陈旧估值拒绝、并发loss peak及独立风险压力已验；暂停不因反弹或扩容自动恢复。[25分阶段](evidence/ticket25/acceptance.md)、[较早独立固定输入](evidence/continuation-2026-10-11/ticket25-independent/acceptance.md) |
| DEC-05 | 有限名单稳定排序及联合资金约束 | [20] | [25]、[26] | 部分：20/25冻结排序与最多一新增卡、两机会共同预算、全部已确认持仓风险和列表移除失效已验；26意向竞争/占用联验进行中。[25分阶段](evidence/ticket25/acceptance.md) |
| DEC-06 | 动作卡完整条件、版本、依据与未知 | [25] | [28] | 部分：25卡片依赖、时间/期限、条件、自身依据、未知及五状态持久化/重放已验；28通知调用方待验。[25最终独立](evidence/continuation-2026-10-11/ticket25-independent/decision-states/acceptance.md)、[25分阶段](evidence/ticket25/acceptance.md) |
| DEC-07 | 执行意向不入账、未回报抑制冲突 | [26] | [25] | 待实施 |
| DEC-08 | 部分成交后余量重算或终止 | [26] | [02]、[25] | 待实施 |
| DEC-09 | 卡片到期不释放外部待结果约束 | [26] | [27] | 待实施 |
| DEC-10 | 市场/板块规则版本与当前异常限制 | [06] | [18]、[25] | 06完成：沪主板/科创板、深主板/创业板基本规则版本与未知当前状态分离，北/其他日期类型受限；18/25消费实际范围，[证据](evidence/06/acceptance.md) |
| DEC-11 | 存量风险完整展示与合格回退 | [22] | [25] | 22独立政策工程/事实与未知/数量压力/重放已验；实际授权不足INCONCLUSIVE、未授资格，25正式正向链待实施 |
| DEC-12 | 同一政策抑制翻转、变更有迁移记录 | [20] | [25]、[27] | 待实施 |
| UI-01 | 五入口、今天优先、诊断折叠 | [15] | [29]、[31] | 部分：15五入口/今天持仓事实优先/原文与诊断折叠，真实Chrome无交易流程与20成员P95通过；29/31最终交付未验；[15证据](evidence/15/acceptance.md) |
| UI-02 | 单股状态/条件/时间线优先，诊断展开 | [25] | [15]、[29] | 待实施 |
| UI-03 | 同步四入口、差异预览与持久回执 | [05] | [01]、[02]、[03]、[04]、[26] | 待实施 |
| UI-04 | 用户只设事实/资金/连接等产品设置 | [15] | [10]、[13]、[16] | 部分：15维护时间/频率设置与既有事实/资金路径真实Chrome通过，无统计参数选择；13/16正式连接/安全交付未验；[15证据](evidence/15/acceptance.md) |
| UI-05 | 通知分类与实质变化，摘要为上限 | [28] | [15] | 待实施 |
| UI-06 | 去重、冷却例外、有效期和不补发 | [28] | [27] | 待实施 |
| UI-07 | 站内及一个外部渠道、失败与送达未知 | [28] | [31] | 待实施 |
| UI-08 | 研究跨出口隔离、不追认正式资格 | [29] | [26]、[28] | 待实施 |
| UI-09 | 资格范围/依据/复核与无人工复核说明 | [24] | [27]、[34] | 24工程通过：资格、范围、期限、资金与证据分列，Chrome显示未经人工独立复核及METHOD边界；当前真实资格NOT_GRANTED。[24截图与验收](evidence/24/acceptance.md) |
| FLOW-01 | 动作成交显式多对多分配、未知保留 | [26] | [29] | 待实施 |
| FLOW-02 | 已发历史不可改、实际时间链与未知 | [28] | [25]、[26]、[29] | 待实施 |
| FLOW-03 | 三种暂停范围，保留对应事实提醒 | [27] | [28] | 待实施 |
| FLOW-04 | 各动作节点服务端复核、原子失效 | [27] | [24]、[25]、[26]、[28] | 待实施 |
| FLOW-05 | 在途失效提醒与深链当前状态 | [28] | [27] | 待实施 |
| FLOW-06 | 按原因暂停/恢复，历史结论不倒改 | [27] | [10]、[21] | 待实施 |
| FLOW-07 | 撤权不清持仓、未决或实际成交 | [27] | [22]、[26] | 待实施 |
| EVAL-01 | 冻结全链条协议与可比对照 | [17] | [20]、[21] | 部分：17固定M0登记/指纹缺口与完整manifest拒绝通过；20完整协议冻结、21真实检验待联验，[17证据](evidence/17/acceptance.md) |
| EVAL-02 | 研究范围、当前名单回溯及迁移局限 | [17] | [19]、[21]、[24] | 17工程完成：HISTORICAL今天名单条件性、真实覆盖/身份/分片、未知域不继承资格；19/21/24实际模型/迁移待联验，[证据](evidence/17/acceptance.md) |
| EVAL-03 | 时间滚动、拟合窗口与重叠标签 | [19] | [17]、[21] | 部分：19固定DEV/CAL、成熟跨窗purge/历史上下文/重复日拒绝/缺行日历/时点控制已验，禁止SEALED；实际零标签未实现真实时间外滚动预测，METHOD不能授资格，[19证据](evidence/19/acceptance.md) |
| EVAL-04 | 成熟度、依赖结构与有效样本区间 | [21] | [18]、[33] | 待实施 |
| EVAL-05 | 人工执行延迟、价窗、费用和缺口 | [18] | [20]、[21] | 18工程通过：固定日线/延迟价窗/费用压力/原输入重放；真实照做分布与20/21联验待执行。[证据](evidence/18/acceptance.md) |
| EVAL-06 | 策略/实际/执行偏差分报及拒绝机会诊断 | [29] | [20]、[26]、[28]、[30] | 待实施 |
| EVAL-07 | 完整机器可读验证清单，缺字段拒绝资格 | [21] | [24]、[33] | 部分：21持久化清单/方法与结果指纹、24必需字段及门槛/审阅阻断缺项拒绝已验；真实G4/G5 FAIL、其余不足，33最终检验/结项未执行。[21](evidence/21/acceptance.md)、[24](evidence/24/acceptance.md) |
| EVAL-08 | 风险可比、覆盖/换手/损失完整报告 | [21] | [20]、[29] | 待实施 |
| EVAL-09 | 全部尝试、资源限制和三自然月终点 | [17] | [30]、[32]、[33] | 部分：17全部失败/中止/重启中断/谱系manifest、预算/三自然月预览通过；审阅补共同根分叉累计预算/失败及活peer恢复[修复](evidence/review/fixes.md)；19执行拟合计时、30/32实际前向终点后续，[证据](evidence/17/acceptance.md) |
| EVAL-10 | 封存查看留痕与后继实验 | [17] | [19]、[21] | 部分：17封存输入/原件/市场与模型实际送入审计、同窗关联与UNPROVEN通过；19/20/21真实结果与冻结后联验后续，[证据](evidence/17/acceptance.md) |
| EVAL-11 | 确认性判定点与反复查看控制 | [21] | [17]、[27]、[33] | 待实施 |
| EVAL-12 | 事前预测/拒绝归档与 G6/G7 分开 | [30] | [21]、[32]、[33] | 待实施 |
| EVAL-13 | PASS/FAIL/INCONCLUSIVE 与未完成区分 | [21] | [23]、[33] | 待实施 |
| EVAL-14 | 技术审阅材料、复现、异议与局限 | [23] | [13]、[33] | 当前CODEX工程与真实接入通过：精确95ddbd52…abfbfba1批准包7核验读取/1离线复算、完整Record/四BLOCKING/两MAJOR与截断局限保存；历史Record不被后续源码修复改写。DeepSeek EXCLUDED。[执行](evidence/continuation-2026-10-11/review-fixes/codex-execution-receipt.md)、[验收](evidence/continuation-2026-10-11/review-fixes/actual-codex-continuation-acceptance.json) |
| EVAL-15 | 门槛/审阅/部署/用户资金的确定性准入 | [24] | [34] | 部分：24全部必需门槛、CODEX审阅/未解决异议、部署、时效、资金/账户与恢复锁交集已公共API验；生产缺有效最终资格继续拒绝，34实际启用未执行。[24独立](evidence/continuation-2026-10-11/ticket24-independent/merge-acceptance.md) |
| EVAL-16 | 有限启用、实际执行/数据漂移持续对照 | [27] | [17]、[20]、[21]、[26]、[29]、[34] | 待实施 |
| EVAL-17 | 操作暂停与统计检查点分开 | [27] | [21]、[34] | 待实施 |
| RUN-01 | 冻结输入、命名空间、发布复核及可恢复 | [25] | [15]、[20]、[28] | 待实施 |
| RUN-02 | 运行日审计、异常定位与关键复盘关联 | [15] | [14]、[26]、[28]、[31] | 部分：15实际运行日/按需审计、错误与原任务版本定位通过；14已实际显式消费原疑点并原子关联verification_id/audit，原观察不变及修订动态失效、真实原件Chrome与联合OS故障通过；26/28/31消费者另验，[14](evidence/14/acceptance.md)；[15证据](evidence/15/acceptance.md) |
| RUN-03 | 日历维护、成熟标签/资格/新实验检查 | [27] | [15]、[17] | 待实施 |
| RUN-04 | 错误来源、改善预期、模块与修正验证方案 | [27] | [08]、[17]、[21]、[29] | 待实施 |
| RUN-05 | 候选到条件发布，失败可结束 | [34] | [17]、[23]、[24]、[33] | 待实施 |
| RUN-06 | 保留旧依赖、回滚不复活资格与迁移记录 | [27] | [16]、[20]、[26] | 待实施 |
| RUN-07 | 来源/结果/实验记忆与依赖失效 | [08] | [20]、[29] | 待实施 |
| RUN-08 | 获取解析失败、局部降级与无模型仍可用 | [13] | [08]、[15]、[25] | 待实施 |
| OPS-01 | 实测首页/入账/名单评估 P95 与环境 | [31] | [02]、[15]、[25] | 部分：25对应冻结源码实测21个完整数值/应用/写入sample，30持仓+5指数 P95 0.4157914秒；仅一只实际冻结模型范围内METHOD数值，29只范围外，不称30只合格机会。31待后续源码完成后核对完整五入口/当前性能，不继承旧源P95。[25性能范围](evidence/ticket25/acceptance.md) |
| OPS-02 | 外部/补查/本地计时分列且不阻塞确认 | [15] | [02]、[08]、[13]、[25] | 部分：15共用事实补查的外部调用/取数/本地计时、缓存API与ChromeP95分列通过；13/25真实下游预算联验未验；[15证据](evidence/15/acceptance.md) |
| OPS-03 | 超时退避、限额深度、积压与任务不重入 | [15] | [13]、[30] | 部分：15持久单worker、活线程租约、真实退避/超时/取消/中断最多3次通过；13/30实际消费者容量未验；[15证据](evidence/15/acceptance.md) |
| OPS-04 | 真实提交/回执崩溃后可靠持久化 | [01] | [02]、[03] | 部分：01三个实际进程故障边界通过；待02/03新增事件与批次联验，[证据](evidence/01/acceptance.md) |
| OPS-05 | 运行日备份、哈希/投影校验、恢复锁 | [16] | [27]、[31] | 16 COMPLETE：完整SQLite/raw/Parquet/CSV/研究工件、恢复点/replay校验、迁移前备份/回滚、RECOVERY_LOCK/运行日补做与真实Chrome已验；27真实ACTIVE/遗漏撤权/通知/解除锁、31打包仍PARTIAL。见[16证据](evidence/16/acceptance.md) |
| OPS-06 | 本地访问、权限、密钥及私人数据脱敏 | [13] | [01]、[16]、[29]、[31] | 待实施 |
| OPS-07 | 架构和工具证明无交易写能力 | [13] | [03]、[31] | 待实施 |
| OPS-08 | 网页/上传为数据、受控工具不越权 | [13] | [03]、[11]、[12] | 部分：11实际网页数据化、工具面/Node import拒绝、账户/私文件/写哨兵/POST无副作用；有限允许clock透明登记，12/13另验，[11证据](evidence/11/acceptance.md)；12未知账户写工具拒绝、外部文本不增权与零账户变化方法通过；真实提供方对抗未验，[12工程证据](evidence/12/acceptance.md) |
| OPS-09 | 各健康状态独立、重启先恢复权限 | [27] | [10]、[15]、[28] | 待实施 |

## 数据不变量

| 条款 | 验收关注 | 主责任 | 联验 | 当前证据 |
|---|---|---|---|---|
| DATA-INV-01 | 真实账户仅由已确认事件构建 | [01] | [26] | 工程通过：26prepare/声明不改现金/持仓/版本；partial只写已确认100，不把proposal200或外部pending当成交，分配不足/过量按事实与事务规则处理。[26独立](evidence/continuation-2026-10-11/ticket26-independent/acceptance.md) |
| DATA-INV-02 | 动作依赖与正式资格版本完整 | [25] | [24] | 工程通过：25动作固定账户/资金/数据/模型/政策/规则及自身grant版本，生产拒绝METHOD、资格不跨依据借用，实际NOT_GRANTED。[25最终独立](evidence/continuation-2026-10-11/ticket25-independent/decision-states/acceptance.md) |
| DATA-INV-03 | 旧预测/动作不可变，修订有后继 | [25] | [08]、[28] | 部分：08原档案及25后继拒绝/失效、固定输入重放已验；28已发通知历史链待验。[25分阶段](evidence/ticket25/acceptance.md) |
| DATA-INV-04 | 实际、历史、影子收益可区分 | [29] | [09]、[20] | 待实施 |
| DATA-INV-05 | 账户、成交及送达等未知不补造 | [26] | [01]、[02]、[28] | 部分：26实际成交/显式分配/不匹配/通知UNKNOWN分列，发生/回报/获知各有来源；无通知证据不猜送达或已读。28真实出站与回执链待联验。[26独立](evidence/continuation-2026-10-11/ticket26-independent/acceptance.md) |
| DATA-INV-06 | 回执重试/重启/恢复不丢不重 | [16] | [01]、[03] | COMPLETE（当前已实现账本范围）：9真实OS路径含schema1前DDL/后DDL/异常回滚、包发布前死亡、活peer、坏库CLI、恢复三阶段死亡；原事件/账户/基线与已确认CSV回执/原字节不丢不重；[16证据](evidence/16/acceptance.md) |
| DATA-INV-07 | 研究不签资格，PASS/回滚不自动激活 | [24] | [13]、[27]、[34] | 工程通过：24研究/HTTP PASS不能签资格、生产METHOD拒绝，新部署拒绝旧证明并保留旧grant/proof原行；27回滚/恢复调用方仍待联验。[24](evidence/24/acceptance.md)、[部署拒旧证明](evidence/continuation-2026-10-11/codex-only-independent/acceptance.md) |
| DATA-INV-08 | 连续影子与真实/条件诊断隔离 | [20] | [29] | 部分：20及后继算法修复已验独立连续账本、条件诊断与真实补录不改影子；29跨页面/报告/导出待调用方。[20](evidence/20/acceptance.md)、[算法修复独立验收](evidence/continuation-2026-10-11/codex-review-independent/merge-acceptance.md) |
| DATA-INV-09 | 撤权失效不抹去持仓及外部未决 | [27] | [26]、[28] | 待实施 |
| DATA-INV-10 | 工具可换，事实与历史证据不丢 | [08] | [07]、[13] | 待实施 |

## 无编号正文与附录约束

这里使用原章节位置定位，不新增 PRD 需求编号。已有编号覆盖的细节仍以原文为准；本表尤其保留不能仅从 AT 数量判断的事项。

| PRD 位置 | 验收关注 | 主责任 | 联验/真实证据 | 当前证据 |
|---|---|---|---|---|
| 1.3、12.1 Account | 账户 permission_profile 用户确认、未知、变更及新增动作限制 | [01] | [06]、[25]、[26] | 部分：01三态确认/版本历史API及页面通过；待06/25/26动作限制联验，[证据](evidence/01/acceptance.md) |
| 1.4、13.5、17.1 | 工程/验证/正式三种结果，非 PASS 可结项 | [31] | [32]、[33]、[34] | 待实施 |
| 2.1—2.3 | 单账户、沪深北逐项范围、指数用途、有限名单与研究迁移 | [06] | [01]、[17]、[25] | 06完成：有限名单/版本、超额不隐藏、明确身份、沪深北范围和指数背景限制；17/25继续研究/动作门禁，[证据](evidence/06/acceptance.md) |
| 2.4、3.3 | 三种模式与写入职责，独立风险回退资格 | [24] | [10]、[13]、[22]、[29] | 待实施 |
| 3.1—3.2 | 初始化、按需、部分成交、补录与中断日常路径 | [31] | [01]、[05]、[15]、[26] | 待实施 |
| 4.2、4.5 | 利息与待结算项确认、到账去重、估值/可用分开 | [04] | [05]、[09] | 待实施 |
| 5.1、9.1 | 可选阶段、运行中盘后检查点与今天首屏顺序 | [15] | [25]、[30] | 部分：15独立可选阶段/运行中维护检查点、今天能力/时间/事实优先与Chrome通过；25/30正式消费者未验；[15证据](evidence/15/acceptance.md) |
| 6.1 | 宽基/行业背景、当前异常/公司行动、公告业绩重大事项逐组取证与风险展示 | [07] | [06]、[08]、[15] | 部分：07七组逐组真实取证/原文/客观观察与三固定背景通过，STATUS真实UNKNOWN且方法样例明确；待08/15消费联验，[证据](evidence/07/acceptance.md) |
| 7.3、13.1 | 必要基线与可比条件，组合仅在采用时检查 | [19] | [17]、[21] | 待实施 |
| 8.1、10.1—10.2 | 动作定义、状态流转与异常处置矩阵 | [26] | [25]、[27]、[28] | 待实施 |
| 11.1—11.4 | 单体/单权威、模块与服务契约、两后端及组件适配 | [31] | [01]、[07]、[13]、[20]、[24] | 待实施 |
| 12.1 | 各必需实体、双时间/依赖/结果命名空间字段归属 | [31] | [01]、[07]、[17]、[20]、[24]、[26]、[29] | 待实施 |
| 13.4 G1—G7 | 所有门槛分项、G6 与真实 G7 分开、政策独立协议 | [21] | [22]、[23]、[32]、[33] | 待实施 |
| 13.4 G5 | 跨时段/成本/延迟/参数邻域、迁移范围及事后缩域 | [21] | [17]、[20] | 待实施 |
| 16 | 90 项 AT 及条款级固定输入和实际证据 | [31] | [32]、[33]、[34] | 待实施 |
| 17.2 | P1/P2 与明确排除项保持边界 | [31] | [06]、[19] | 待实施 |
| 17.3 | 摘取资产保留来源/映射，缺事件的旧余额仅作基线 | [03] | [01]、[07]、[31] | 部分：03原CSV/映射/基线历史未知及固定候选登记通过；07市场摘取与31整体核对待联验，[03证据](evidence/03/acceptance.md) |
| 18.1 | 建议默认、必须冻结值与实际配置区分 | [31] | [06]、[10]、[17]、[28]、[30] | 待实施 |
| 18.3 | 应用/迁移恢复/手册、验证包、条件性正式交付 | [31] | [23]、[33]、[34] | 待实施 |
| 附录 A、D | 账本守恒、部分成交余量、撤权恢复最小样例 | [26] | [02]、[09]、[27] | 待实施 |
| 附录 B 数据与联网 | 数据规则、任务停止及复盘判据冻结 | [07] | [06]、[13]、[14] | 部分：07有限scope/有界停止/来源缺口及零联网回放通过；14关键复盘链/15实际关联与原知识/失效门禁已验，13后端工具组合另验，[14](evidence/14/acceptance.md)，[证据](evidence/07/acceptance.md) |
| 附录 B 账户授权/损失口径 | 范围、起点、现金流、实现/未实现、陈旧估值、额度与禁止每日重置 | [10] | [09]、[20]、[25]、[27] | 部分：10授权持久化/固定方法口径及不重置通过；待09/20实际事实和25/27真实触发链，[证据](evidence/10/acceptance.md) |
| 附录 B 实验/资源/结项 | 冻结目标/窗口/方法/最少证据及自然月边界 | [17] | [20]、[30]、[32]、[33] | 部分：17真实覆盖驱动M0目标/窗口/支持/方法/预算/三自然月设计、缺项拒绝与全部尝试通过；20/30/32/33实际冻结/前向结项待联验，[证据](evidence/17/acceptance.md) |
| 附录 B 资格与恢复 | 门槛、审阅、监测复核及按原因恢复 | [27] | [17]、[21]、[22]、[23]、[24]、[34] | 待实施 |
| 附录 B 运行与通知 | 按需/检查点、覆盖、渠道、后端与研究隔离 | [15] | [13]、[28]、[29]、[30] | 部分：15普通事实独立、覆盖/历史/任务审计/维护持久通过；13/28/29/30后端/渠道与样本联验未验；[15证据](evidence/15/acceptance.md) |

[01]: issues/01-account-baseline.md#comments
[02]: issues/02-actual-fills.md#comments
[03]: issues/03-csv-import.md#comments
[04]: issues/04-cash-corporate-actions.md#comments
[05]: issues/05-reconcile-account.md#comments
[06]: issues/06-watchlist-calendar.md#comments
[07]: issues/07-market-evidence.md#comments
[08]: issues/08-source-fallback.md#comments
[09]: issues/09-valuation-performance.md#comments
[10]: issues/10-funding-boundaries.md#comments
[11]: issues/11-codex-evidence.md#comments
[12]: issues/12-deepseek-evidence.md#comments
[13]: issues/13-backend-switch-isolation.md#comments
[14]: issues/14-independent-verification.md#comments
[15]: issues/15-on-demand-review.md#comments
[16]: issues/16-backup-recovery.md#comments
[17]: issues/17-research-protocol.md#comments
[18]: issues/18-daily-execution-labels.md#comments
[19]: issues/19-transparent-model-freeze.md#comments
[20]: issues/20-policy-continuous-shadow.md#comments
[21]: issues/21-validation-evidence.md#comments
[22]: issues/22-independent-risk-policy.md#comments
[23]: issues/23-technical-review-delivery.md#comments
[24]: issues/24-capability-grant.md#comments
[25]: issues/25-current-actions.md#comments
[26]: issues/26-execution-intents.md#comments
[27]: issues/27-suspend-revoke-recover.md#comments
[28]: issues/28-notifications.md#comments
[29]: issues/29-research-isolation.md#comments
[30]: issues/30-forward-archive-deadline.md#comments
[31]: issues/31-engineering-delivery.md#comments
[32]: issues/32-first-real-forward-archive.md#comments
[33]: issues/33-real-validation-delivery.md#comments
[34]: issues/34-conditional-formal-activation.md#comments


### 2026-10-09 Ticket 19公开原件与历史费用续推

DAT-11、MOD-02、MOD-05的真实验收仍为部分。新增逐年权益/14次现金实施和40业务日历史quote原件，实际历史版本连续日覆盖最长1日；未以当前K线、盘中quote或报纸成交笔数代替所需21行回看。18执行费用改为逐边生效版本与原件/代码指纹，不再把当前费用无条件回填旧年。最终相关47项应用检查通过，真实模型/校准冻结、可比基线、完整输入处理及实现缺口保留；没有提前查看SEALED或解锁20/21。详见[本轮验收](evidence/19-completion-2026-10-09/acceptance.md)、[真实训练路径审计](evidence/19-completion-2026-10-09/real-training-audit.md)。

### 2026-10-09 Ticket 19不消耗预算的来源/训练缺口预检

补齐只读metadata诊断及全family预算查询，避免为看缺项误调用拟合。实际600362登记家族保留两次FAILED，当前三次主拟合及一次CAL剩余；该快照非额度预约。21项相关应用回归及实际元数据重复/manifest核对通过，未读实际标签/SEALED、未拟合或授权来源/窗口；models/registry/execution原字节不变。DAT-11、MOD-02、MOD-05仍partial，真实候选/独立校准/模型冻结/必要基线尚未验收；20/21不提前解锁，后续开发和取证由代理负责。见[本轮验收](evidence/19-training-preflight-2026-10-09/acceptance.md)。

### 2026-10-11 Ticket 20 当前验收与前置更新

本节更新当前状态，不改写上文历史记录。19已在集成基线 `eabc7a3` 完成当前真实历史量价重建训练、时间隔离CAL拟合及模型工件冻结；[真实验收](evidence/19-reconstruction-2026-10-10/acceptance.md)取代旧时点“尚无真实模型/工件冻结”的当前解释。严格历史PIT、独立校准有效性、确认性/前向证据和正式资格仍未由此成立。

| 范围 | 当前结论 | 证据与后续边界 |
|---|---|---|
| AT-39、AT-62 / EVAL-16 | 20工程隔离通过 | 真实账户逆向成交、补录、费用与更正不重置保存的影子；四命名空间查询/网页分别显示。27实际正式期监测与29归因展示仍待各票，不由METHOD替代 |
| AT-63 / ID-15 | 20连续资金与持仓守恒通过 | 联合预算和稳定排序保留动作/拒绝，非空基线多日数量守恒；成熟拒绝反事实仅作诊断，不相加为策略收益 |
| AT-74 / EVAL-01 | 20完整冻结与后继工程通过 | 模型、政策、基线、规则、费用、执行/缺失、G5、监测/统计方法、全部尝试与代码/数据指纹绑定；冻结修改拒绝、关联后继独立，损坏原协议归档拒绝消费。21真实确认性/可比验证仍待联验 |
| EVAL-12 / ID-15 | 20历史研究机会归档工程通过，真实前向待30/32/33 | 保存所有历史机会及拒绝原因，当前HTTP仅冻结CAL；不读取保护SEALED，不启动真实前向或补造旧时点预测 |
| EVAL-16、EVAL-17 / ID-14 | 20事前方法冻结工程通过 | G5和正式期执行/数据漂移/成熟结果监测配置已绑定；数值方法算例只验证计算，实际监测与统计证据由21/27等后续票负责 |

[20逐场景验收](evidence/20/acceptance.md)与[独立合并验收](evidence/continuation-2026-10-11/merge20.md)对应修正版源合入 `b321f40`。7项API、1次实际浏览器、构建及另一独立公共API案例分开报告；非空持仓缺陷的红记录保留，修正后同案例通过。12个19模型指纹依赖源码未变。当前01—20及22共21票完成；21已启动，23等待21，30的20依赖已解除但本轮按顺序先推进21→23。完整规格、真实G1—G7、正式能力及实际长期证据尚未完成。

### 2026-10-11 Ticket 21 当前验证能力与证据边界

| 范围 | 当前结论 | 证据及责任边界 |
|---|---|---|
| AT-38 / ID-14、ID-21 | 完整冻结输入、当前宿主确认性准入和版本拒绝工程通过 | 真实独立材料不足，读取SEALED内容前409并审计；没有实际确认性PASS，33仍负责真实统计 |
| AT-52 / MOD-06、MOD-08 / EVAL-07、13 | 清单、G1—G7、输入方法结果指纹、实验/验证/审阅/能力独立状态通过 | 自动初步结论不得替代技术审阅；当前真实G4/G5 FAIL，其余不足；G2仅重放子检查PASS |
| ID-15 / G4 / EVAL-04、07、08、11 | 连续受约束NAV/基线、尾部风险、占用/持有/覆盖、概率损失/可靠性/区分/子集/支持/相关区间工程通过 | 空输入与已观察全拒绝分离、硬FAIL优先；真实依赖假设/独立校准不足，不能统计PASS |
| ID-16 / G5 / EVAL-16、17 | 时间、费用、执行延迟/部分成交、已冻结阈值邻域逐分项通过 | penalty/lookback冻结工件缺失明确INCOMPLETE，未追加拟合或消费预算；禁止测试后缩域改判 |
| AT-56 / 正式期方法 | 固定输入执行、DEV冻结漂移分位、30日相对检查点、缺失/未成熟/到期方法通过 | 供27实际持久检查点消费；不代表真实漂移/用户行为/G7，不增PASS点 |
| G6、G7 / EVAL-12 | 本票仅当前不足清单完成 | 原账户与预算保持，无真实前向起点；真实工程/成熟前向由后续票取证 |

[21逐场景验收](evidence/21/acceptance.md)提供API/SQLite、Chrome、真实一致副本和方法算例的分层证据。本节更新当前状态，上文旧快照不改写。

2026-10-11独立合并验收补充：源 `aef9b27` 合入 `4f24dac6c18071309107a8a03b968395de44a710`。另一新METHOD公共API案例与实际一致副本已有清单读取/重放分别PASS，原始机会2/唯一1/入选1、分段平仓1、空输入INCONCLUSIVE、已观察资金不足硬FAIL、三清单持久化重放及归档损坏拒绝有独立结构化收据；实际旧方法重放409、最终方法0联网一致。G2整体仍INCONCLUSIVE，重放子检查PASS不扩大成部署证据；G7不足、未授予能力。见[独立21验收](evidence/continuation-2026-10-11/merge21.md)。当前01—22共22票工程完成，23按顺序进入可行前沿；真实统计及生产资格继续保留，不改写旧时点记录。

### 2026-10-11 Ticket 23 当前审阅与交付证据边界

| 范围 | 当前结论 | 证据及责任边界 |
|---|---|---|
| AT-51 / ID-08、ID-16、ID-17、ID-21 | partial，本地工程通过 | 最终39项API/SQLite，浏览器和build通过；真实CODEX和DeepSeek此批材料外发自动审批拒绝，0次外发，待明确授权，固定worker/SDK loopback不替代 |
| ReviewRecord / MOD-06、EVAL-07 | 冻结、引用、宿主复现、拒绝/重试及并发通过 | 模型赞同不能清除宿主未完成检查与非PASS证据；异议处理不接受未经核实的文字；记录完整与阻断已解决独立 |
| 验证交付 / ID-21 | METHOD终点FAIL/INCONCLUSIVE完整交付路径通过 | 实际endpoint和必需检查仍缺，不因审阅生成成功升级；真实实验由33，正式能力NOT_GRANTED |
| Risk-policy 审阅接缝 | 固定evaluation/input/code与本协议五门槛绑定通过 | 独立risk材料，不借profit G3/G4/G7审阅；24须消费具体可重放证据及自己的资格条件 |
| 全量本地export及外发精简材料 | 可追溯归档与边界通过 | 未准入SEALED只保留metadata/原因，不读内容；完整输入不外发。根永久审批packet/实际copy/METHOD保全见[23验收](evidence/23/acceptance.md) |

### 2026-10-11 Ticket 30 当前前向归档边界

| 范围 | 当前结论 | 证据及责任边界 |
|---|---|---|
| AT-58 / ID-09、ID-15 / EVAL-12 | partial；工程唯一归档/缺日/拒绝诊断通过 | 公共API真实账户/新快照改版仍同sample；五OS故障/并发重启通过；共享既有worker，无补写历史预测。真实当前完整Host producer欠项明确，32未执行 |
| AT-88 / ID-14、ID-16 | 三自然月/停止/截止/成熟分类工程通过 | 月末及闰年、恢复锁、关闭claim中断原截止恢复；METHOD仅算法证据，真实起点registry/public均null，期限不延长 |
| 当前特征/源可得性 | 窄adapter数值及receipt/effective核验通过 | 冻结四特征按重建经济现金链计算；未来日历只开闭日期，同日未确认bar/未知状态权益拒绝。现parser/prospective无法装配完整execution packet，非客户端complete/PASS writer |
| 终点 / G1—G7 / 审阅 | 不足INCONCLUSIVE、INCOMPLETE/PENDING | 30不增加PASS点、不授予能力；实际材料、独立checkpoint、32首次实存及33成熟终点仍pending；既有20分红时序P2由根修复后关联回归 |

[30逐层验收](evidence/30/acceptance.md)保留最终单轮22绿/1夹具失败及修正版同案1绿、Chrome/build、source SHA、实际metadata只读和八METHOD运行件保全收据；不跨运行改写为单轮全绿，不把完整工程时间算法升级成实际研究证据。30 partial/ready-for-agent，原19/23实际资料未修改，未推送。

30最终等价时区收口：新增公共API red1→datetime比较修正，最终9API/96.84s、Chrome1/48.0s、59模块build/1.90s通过，最终11文件SHA/长度前后相同，11METHOD目录保全。原核心收据保持原版本；30 partial真实输入生产链欠项、32实际首次归档及33自然月终点责任不变。


### 2026-10-11 AT-51 当前CODEX-only完成

用户批准新材料95ddbd52…abfbfba1并排除DeepSeek。23的AT-51工程与一次真实CODEX接入完成：实际run ed0d834e-049b-4356-b5a7-1ff5bc853aef，ReviewRecord 2c05d94c-33a0-4353-9078-aed0060d7c6e，7原文读取SHA匹配/1离线宿主复算、独立持久化验收PASS。完整Record不清除四项BLOCKING及两项MAJOR；模型大文件截断、上游材料宿主绑定、实际诊断未结项的限制保留。真实交付INCOMPLETE/NOT_GRANTED，G4/G5 FAIL及其他INCONCLUSIVE不变。上文双后端待批准为旧时点记录；DeepSeek当前EXCLUDED/0 CALLS，不能写为PASS。详见[当前独立收据](evidence/continuation-2026-10-11/review-fixes/actual-codex-continuation-acceptance.json)及[执行记录](execution-status.md)。AT-53/73/75由已解锁24实施，统计真实结项/资金/范围条件未被跳过。

### 2026-10-11 Ticket 24 准入与独立验收

| 条款 | 当前结果 | 实际证据与限制 |
|---|---|---|
| AT-53 / EVAL-14、EVAL-15 | 工程通过 | 必需门槛、证据、完整审阅/异议、协议、时效、资金/账户不完整及客户端自签均拒绝；仅显式宿主METHOD正向，不能变为生产PASS。36同源公共API与6独立公共API分别留存，不合并计数 |
| AT-73 / AUTH-02、EVAL-15 | 工程通过 | 部署/原材料/原件/ReviewRecord/proof源变化拒绝并查询受限；生产载入或恢复METHOD拒绝。12原模型依赖保持原字节，实际旧批准包随已确认缺陷修复成为历史 |
| AT-75 / AUTH-04 | 确定性资格机制与披露工程通过；正式动作由25接续 | 无人工独立复核不增加额外否决；METHOD已核全部条件后登记精确范围/动作/期限，system_usable=false；Chrome核可读披露。实际G1—G7/资金启用缺项未解决，不能写实际正式建议已启用 |
| 逐grant用途、资金/账户、短事务 | 工程通过；真实性能未测 | 多范围重启、NOT_OPEN/UNKNOWN下已有可卖量EXIT与新增BUY/ADD分开；未知可卖拒绝。慢数值证明期间资金缩减，writer读最新版本拒绝；保存证明复用仍核原件/源。该受控时延不是实际P95 |

详见[24独立验收](evidence/continuation-2026-10-11/ticket24-independent/merge-acceptance.md)及[同源分阶段记录](evidence/24/acceptance.md)。25/26/27/28/29调用方联验仍各留责任。审阅两项MAJOR实现修复60项相关回归及独立METHOD后继重放完成，原审阅记录和四项真实BLOCKING原样保留；新实现不继承旧包当前资格。[独立修复验收](evidence/continuation-2026-10-11/codex-review-independent/merge-acceptance.md)只证明修复行为，不新增实际统计/前向/模型审阅。
