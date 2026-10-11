# Ticket 25 工程交付与证据

实现与源检查完成，等待父代理独立复验及合入；本记录不签发真实技术资格。原交付 `4fc2403` 经独立31例PASS但因DEC-01/ID10缺五项Decision显式状态而暂停接受；本次source `e3a4a56`补齐状态投影（[形状与来源](decision-state-projection.md)）。先合已接受31/root `7390ccef`，后合30历史来源/root `c3fe7d8d83d05b8579979be3c6b62a5af03103ce`及docs-only `28fd34d`，source merge `1a0a700d`、最终docs merge `b38c9f38`。最终后端指纹见 [source-guard-latest.json](source-guard-latest.json)；修复前及投影阶段记录分别保留在source-guard-handoff/states。原主提交343a53a、数据/名单/过期e8b3a53、浏览器/audit 2d5aa40、receipt/loss 8911282均保留。

## 交付行为

`POST /api/actions/evaluate` 获取 host 证据与账户/资金/能力快照，调用冻结20政策及22独立风险计算，在短写事务内使用同一个具体 `boundary(db)` 复核最新账户、资金、持久资格与恢复状态、已采纳数据/估值/forecast/风险评估、当前有限名单、历史损失峰值和到期；之后归档不可变 evaluation。已有幂等收据同样先复核再查找，计算期间边界改变产生新的不可变拒绝修订，不能返回旧活卡。`GET /api/actions/current` 复用这个边界、检查代码并去重失效事件；原 evaluation 不变，离线 replay 不联网。固定输入每次仍重新 capture/calculate，仅存储返回同一个 ID；输入键纳入已算损失状态，低峰值不能覆盖并发已存高峰值。

新增风险逐项限制账户交易权限、资金开关/暂停、损失起点/估值/外部现金流、用途时点、规则/当前状态/完整日线、技术资格范围、当前有限名单、现有持仓及联合 Decimal 预算。券商可用金额已是净可用，不重复扣冻结；费用与用户保留额计入。冻结稳定排序不扩股票池，最多一条新增卡片；所有已有持仓风险仍保留。风险政策可在 NOT_OPEN/UNKNOWN 购买权限下按确认可卖量减仓，不借收益模型资格放行。

Decision 保存依据、grant、账户/资金/数据/政策/完整实验/代码/规则依赖、当前/目标/本次数量、价格范围、报价与累计量时点、完整日线截止及20交易日期限、触发/失效条件及不确定性。没有真实账本副作用。后继/失效/拒绝与实际动作变化进入运行事件和15审计；指标按实际事件计算，固定输入不重复计数。今天/单股共用当前卡片，METHOD 明示不能用于真实正式建议。

Decision另存account_status/data_status/model_status/execution_eligibility/capability_status。账户保留NEW_RISK或REDUCTION的state与fact_scope_state差异；能力状态按自身grant_id匹配，不取全局selected grant；风险model明确NOT_APPLICABLE。METHOD数据用途通过仍保留METHOD namespace，执行状态只为METHOD_ONLY；预算不足/数据缺口/可卖0保持BLOCKED，不创建伪Decision。状态由既有检查投影，无额外DB/provider读取或资格gate；GET/replay保留字段，旧immutable资料不补写。

## 最终检查

| 层 | 当前结果 | 原件 |
| --- | --- | --- |
| 状态投影源码公共 API、真实 SQLite/隔离原始归档 | 23 actions PASS，134.57秒；五项状态literal、收益/风险、不可执行分列、GET/replay和生产重开拒绝；含原receipt/估值/loss场景。source e3a4a56+31，30历史来源合入前 | [states-final-actions.log](states-final-actions.log) |
| 同阶段 composition | 6 PASS，34.20秒：CODEX-only4 +producer capture1 +API/worker role1 | [states-final-composition.log](states-final-composition.log) |
| 最终source composition | 3 PASS，18.90秒：fresh METHOD收益Decision五状态/预算/GET/replay、历史日线原单位与当前不得借用历史统计单位；合root c3fe7d8后source。未重复未变23/6/浏览器 | [latest-source-composition.log](latest-source-composition.log) |
| 公共审计文字期望 | 1 PASS：一次失效=1、反向变化=0，重复查询不重复计数；未声称已经发生真实反向成交 | [audit-final.log](audit-final.log) |
| 真实 Edge、uvicorn/vite | 1 PASS，17.9秒：无资金无alert、合格METHOD数量/独立时点/中文不确定性、今天及单股、缩权旧卡片失效 | [browser-presented-final.log](browser-presented-final.log)、[结果](browser-presented-results.json)、[今天](actions-current.png)、[单股](actions-stock.png) |
| 真实 Edge 拒绝分支 | 分别1 PASS：陈旧估值28.5秒、UNKNOWN购买权限14.1秒、NOT_OPEN购买权限+确认可卖0股14.7秒。后者使用与API相同的显式METHOD资格时钟，不是实际盘后/市场证明 | [估值](browser-stale.log)、[权限](browser-permission.log)、[可卖](browser-sellable-final.log)、对应PNG/结果JSON |
| TypeScript/Vite | PASS，61 modules、2.12秒 | [build-presented-final.log](build-presented-final.log) |
| 最终源码完整本地性能 | 21个sample，nearest-rank P95 **0.4157914000秒**，30个股+5指数，外部取证0/联网0。投影阶段 .4361794及投影前.4863553、receipt前.4026603均保留对应历史source | [benchmark-results.json](benchmark-results.json)、[最终日志](benchmark-latest-source.log)、[脚本](benchmark.py)、[投影阶段](benchmark-before-final-source-results.json)、[投影前](benchmark-before-decision-states-results.json) |
| 停止档案保全 | 原1934文件不覆盖，状态投影API/6组合/benchmark追加988至2922，最终3组合/benchmark再追加213至**3135**；全部来源/目标SHA256及长度一致，0差异，旧资料每阶段重新核对 | [原1934](runtime-preservation-handoff.json)、[投影2922](runtime-preservation-states.json)、[最终3135](runtime-preservation-latest.json)、[最终日志](preservation-latest.log)、[进程停止](stopped-latest-processes.json) |
| 冻结资料保护 | own/root12源原字节及长度不变；原19 SQLite SHA `ec46257c4420f69c245791778c49079355700615cc3ed7b94d8027bd4dcf66c4`/165814272 bytes不变；三allowed artifacts不变；最终源码fingerprint等于最终benchmark | [source-guard-latest.json](source-guard-latest.json) |

四个真实Edge流程及TypeScript/Vite记录验证展示时的后端源码，前端字节与本次交付相同。后续仅后端边界及producer组合变化，按父代理要求使用上述当前源码API/组合检查收口，没有把旧浏览器后端fingerprint升级为最终源。此前24 API及单独audit检查是当时结果，原件保留；不与新增23项相加冒称同一次suite。

独立审阅31 PASS/201.74秒及其fresh P95 .4603298秒是原4fc2403源码记录，并明确因五状态Spec缺口held；本次不重跑该旧31例suite。状态阶段23+6之后，上游30产品源改变完整source_inventory，所以只做上述最终3例composition及新21sample完整benchmark；不是为了挑选更快收据。新source-guard阶段明确previous-source benchmark equality=false，只有对应阶段的当前source equality=true，避免继承旧记录布尔标签造成错读。

## 性能证据的范围

按父代理 [只读模型指针](../continuation-2026-10-11/frontier24-29/benchmark-artifact-reference.json) 使用实际既有模型16282 bytes、校准器474 bytes、最小配置3971 bytes；没有开真实SQL、fit或持久化 forecast。使用实际冻结 scaler/weights/intercept-only calibrator 和20政策，在21个连续归档 SSE 交易日的 METHOD 特征上重新 features→交易日连续性校验→preprocess/predict/calibrate，每个 sample 随后调用公共 evaluate 的实际数据/资格/预算/发布路径，包含已有收据的最新writer复核；各阶段时间分别保留。9/25休市已排除。精确 METHOD feature-packet 及SHA保存在 benchmark 档案。最终源码只测这一组21 samples；之前收据均保留历史源区分。

真实冻结候选范围仍只有 SSE:600362。用30个合成且确认的初始持仓保留超额资产，保持关注上限20。1只进入数值路径，29只范围外显式拒绝；1只范围内也因已有持仓/阈值拒绝，5指数仅背景。每次实算后只有1个 evaluation ID是幂等存储，不能理解为缓存跳过计算或30只合格股票。METHOD 零现金权益事件下 raw/economic数值相同；特征/报价/账户/资金/资格均合成，校准仍 FITTED_UNVALIDATED，真实资格仍 NOT_GRANTED，不是G1—G7或历史PIT证明。源码变更后的旧真实freeze继续历史状态。

## TDD 与错误账本

| 执行 | 实际结果与解释 |
| --- | --- |
| red-1 → green-1b | 公共动作API真实404失败；随后账户未建立时 fallback时钟破坏幂等，修为稳定epoch，最终1 PASS |
| red-2b → green-2 | 真实合格METHOD未生成预期200 BUY失败；修复联合费用预算，2 PASS；red-2是缺support PYTHONPATH的收集错误 |
| red-3 → green-3 | 缩权旧卡片仍活的真实失败；修复当前复核，3 PASS |
| red-4b → green-4b | 独立风险未生成减仓的真实失败；首次futureclock被账本正确拒绝、一次fixture缺loss_origin_at分别保留；最终针对性1 PASS |
| matrix-2 | 当时12 PASS；matrix-1保留上述fixture错误，不能冒称连续green |
| final-api | 广域103 PASS/1 FAIL/531.67秒；仅既有 review0.15秒heartbeat gap在负载下未观察到。未改阈值或吞错；final-affected原受影响15 PASS含其单独重跑，不能升级旧广域suite为全绿 |
| browser → browser-final | 首弱断言绿但server METHOD无资金实际500已识别，修复并添加noalert断言；后续清洁浏览器PASS |
| composition-api → composition-guard-retry2 | 17 PASS/2 FAIL，均未设置ROLL_ENV=test导致TEST_ONLY gate；保留原红，正确环境两例2 PASS。第一次retry错文件名收集0例，也保留 |
| red-data-list → data-list-final | 移出当前名单仍保留旧卡片真实失败；补同SQLite数据/名单复核，16 PASS；新增UNKNOWN权限/quote采集/列表并发7 PASS有重叠，不相加当suite |
| red-expiry-idempotency → final-current-api | 过期evaluate幂等返回旧活卡真实失败；绑定过期状态，最终当前24 PASS |
| red-existing-receipt-race → boundary-final-api → final-boundary-api → handoff-actions | 已有receipt时缩资/名单并发2 FAIL/18.13秒；将最新writer复核置于prior查找前，先20 PASS/109.12秒，再22 PASS/124.34秒；最终损失键及30producer组合源23 PASS/130.29秒。各阶段非同一源码，不相加 |
| loss-peak-final → loss-peak-corrected → handoff-actions | 首1 FAIL/7.04秒为换METHOD包被CAPABILITY_METHOD_BASIS_CHANGED正确拒绝；次1 FAIL/7.41秒是扩容后allowance期望写0，既有公式10000-6000=4000。保持同一immutable包、公共重启/扩容检查peak6000与triggered/PAUSED，纯数值rebound另层验证loss0/peak6000/allowance4000/PAUSED；最终23项包含该例。不改24保护或10公式，4000算术余额不意味着暂停的新风险可以恢复 |
| 独立Spec缺口 → state-red-profit/risk → state-green-profit/risk | 原31 PASS仍held五状态缺口；profit缺account_status 1 FAIL/7.87秒→1 PASS/6.97秒，risk有可卖量缺model_status及可卖0缺execution_eligibility 4 FAIL/26.90秒→4 PASS/24.21秒；最终投影stage23 PASS/134.57秒。五字段公开literal与GET/replay，原数据/期限六case还检查RESTRICTED/OUT_OF_SCOPE，不补造资格 |
| browser-data-final | 缺默认Chromium是环境失败，改显式已有Edge；最终展示及单股样例PASS |
| browser-sellable → browser-sellable-final | 首次fixture昨日15:05包在真实今日资格clock下正确拒绝 CURRENT_DATA_INCOMPLETE；未重标旧包为当前，改用与API风险测试相同的显式受控METHOD资格clock，2.0秒case/14.7秒run PASS。实际研究/forward/系统时钟均未改，不能提升为真实盘后证明 |
| build-final → build-final-retry | sandbox realpath EPERM环境失败，正常已安装依赖的显式外部构建PASS；展示调整后最终再PASS |
| benchmark | 两次setup路由/关注上限错误均未计时；旧损失资产不一致/旧CODEX源/误含休市日以及最终expiry修复前收据全部保留，均不升级为最终源P95；最终一次当前源21 sample收据独立 |
| preservation-setup-error → preservation-final | METHOD文件package envelope查错发生于复制前；修正后831文件全量一致，无覆盖已有档案 |

## 当前真实限制与接续

真实输入仍存在未授权、实际broker费用未确认、当前状态/完整日线用途验证及研究forecast不能当当前正式输入的限制，本票展示事实与明确拒绝，不造真实正向资格。冻结20没有 ADD/HOLD/判断型WAIT/反向或冷却政策，命名缺口 `POLICY_FOR_ADD_HOLD_WAIT_REVERSAL_COOLDOWN_NOT_FROZEN`；仅已有政策覆盖的动作进入生成器，缺口不替换为默认WAIT。旧 `/api/formal/*` 防护入口继续关闭，当前动作有新的实际评估/查询/replay接口，并非用constant403代替本票。

26/27接入真实意向时仍需在自身账本短事务内复核当前动作、竞争占用、实际成交与部分成交；本票 `current()` 尚没有 caller-db参数，26可在本票新模块上加具体事务 seam，不能跨冻结研究源改写。28按用户要求先站内通知与配置页，实际外部发送等待用户配置。上述后续验收没有提前宣称通过。本票工作树与未提交实验档案保留，待独立接受和哈希保全核验后由父代理按清理流程处理。
