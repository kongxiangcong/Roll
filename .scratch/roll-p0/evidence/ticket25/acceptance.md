# Ticket 25 工程交付与证据

实现与最终源检查完成，等待父代理独立验收及合入；本记录不签发真实技术资格。源码主提交 `343a53a`，当前数据/名单/过期修复 `e8b3a53`，追加浏览器拒绝/audit测试 `2d5aa40`；已合 root `580b801ce25bb4ae13b4335d61d90db64d444a23`（仅 trace 文档，与先前接受 CODEX-only 源相同）。源码指纹见 [source-guard.json](source-guard.json)、[验收seams](verification-support.json)。

## 交付行为

`POST /api/actions/evaluate` 获取 host 证据与账户/资金/能力快照，调用冻结20政策及22独立风险计算，在短写事务内复核同一 SQLite 中最新账户、资金、资格、已采纳数据及当前有限名单；之后归档不可变 evaluation。`GET /api/actions/current` 同快照复核依赖/到期/代码，失效事件去重；查询原 evaluation 不改其内容，离线 replay 不联网。重复固定输入仍重新 capture/calculate，只有存储返回同一个 ID。过期状态改变输入键，不能返回先前的有效旧卡片。

新增风险逐项限制账户交易权限、资金开关/暂停、损失起点/估值/外部现金流、用途时点、规则/当前状态/完整日线、技术资格范围、当前有限名单、现有持仓及联合 Decimal 预算。券商可用金额已是净可用，不重复扣冻结；费用与用户保留额计入。冻结稳定排序不扩股票池，最多一条新增卡片；所有已有持仓风险仍保留。风险政策可在 NOT_OPEN/UNKNOWN 购买权限下按确认可卖量减仓，不借收益模型资格放行。

Decision 保存依据、grant、账户/资金/数据/政策/完整实验/代码/规则依赖、当前/目标/本次数量、价格范围、报价与累计量时点、完整日线截止及20交易日期限、触发/失效条件及不确定性。没有真实账本副作用。后继/失效/拒绝与实际动作变化进入运行事件和15审计；指标按实际事件计算，固定输入不重复计数。今天/单股共用当前卡片，METHOD 明示不能用于真实正式建议。

## 最终检查

| 层 | 当前结果 | 原件 |
| --- | --- | --- |
| 公共 API、真实 SQLite/隔离原始归档 | 24 PASS：20 actions +4 CODEX-only composition，132.42秒 | [final-current-api.log](final-current-api.log) |
| 公共审计文字期望 | 1 PASS：一次失效=1、反向变化=0，重复查询不重复计数；未声称已经发生真实反向成交 | [audit-final.log](audit-final.log) |
| 真实 Edge、uvicorn/vite | 1 PASS，17.9秒：无资金无alert、合格METHOD数量/独立时点/中文不确定性、今天及单股、缩权旧卡片失效 | [browser-presented-final.log](browser-presented-final.log)、[结果](browser-presented-results.json)、[今天](actions-current.png)、[单股](actions-stock.png) |
| 真实 Edge 拒绝分支 | 分别1 PASS：陈旧估值28.5秒、UNKNOWN购买权限14.1秒、NOT_OPEN购买权限+确认可卖0股14.7秒。后者使用与API相同的显式METHOD资格时钟，不是实际盘后/市场证明 | [估值](browser-stale.log)、[权限](browser-permission.log)、[可卖](browser-sellable-final.log)、对应PNG/结果JSON |
| TypeScript/Vite | PASS，61 modules、2.12秒 | [build-presented-final.log](build-presented-final.log) |
| 完整本地性能 | 21个sample，nearest-rank P95 **0.4026603000秒**，30个股+5指数，外部取证0/联网0 | [benchmark-results.json](benchmark-results.json)、[最终日志](benchmark-final-current.log)、[脚本](benchmark.py) |
| 停止档案保全 | 首批831文件，加三个拒绝浏览器/审计146文件，总计977；来源/目标 SHA256及长度逐一一致，0差异，首批未覆盖 | [初始清单](runtime-preservation.json)、[全量清单](runtime-preservation-all.json)、[追加日志](preservation-additional.log) |
| 冻结资料保护 | own/root12源原字节及长度不变；原19 SQLite SHA `ec46257c4420f69c245791778c49079355700615cc3ed7b94d8027bd4dcf66c4`/165814272 bytes不变；三allowed artifacts不变 | [source-guard.json](source-guard.json) |

## 性能证据的范围

按父代理 [只读模型指针](../continuation-2026-10-11/frontier24-29/benchmark-artifact-reference.json) 使用实际既有模型16282 bytes、校准器474 bytes、最小配置3971 bytes；没有开真实SQL、fit或持久化 forecast。使用实际冻结 scaler/weights/intercept-only calibrator 和20政策，在21个连续归档 SSE 交易日的 METHOD 特征上重新 features→交易日连续性校验→preprocess/predict/calibrate，每个 sample 随后调用公共 evaluate 的实际数据/资格/预算/发布路径，各阶段时间分别保留。9/25休市已排除。精确 METHOD feature-packet 已按原 cutoff重建并核对同一SHA，保存在 benchmark 档案；没有补算新计时样本。

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
| browser-data-final | 缺默认Chromium是环境失败，改显式已有Edge；最终展示及单股样例PASS |
| browser-sellable → browser-sellable-final | 首次fixture昨日15:05包在真实今日资格clock下正确拒绝 CURRENT_DATA_INCOMPLETE；未重标旧包为当前，改用与API风险测试相同的显式受控METHOD资格clock，2.0秒case/14.7秒run PASS。实际研究/forward/系统时钟均未改，不能提升为真实盘后证明 |
| build-final → build-final-retry | sandbox realpath EPERM环境失败，正常已安装依赖的显式外部构建PASS；展示调整后最终再PASS |
| benchmark | 两次setup路由/关注上限错误均未计时；旧损失资产不一致/旧CODEX源/误含休市日以及最终expiry修复前收据全部保留，均不升级为最终源P95；最终一次当前源21 sample收据独立 |
| preservation-setup-error → preservation-final | METHOD文件package envelope查错发生于复制前；修正后831文件全量一致，无覆盖已有档案 |

## 当前真实限制与接续

真实输入仍存在未授权、实际broker费用未确认、当前状态/完整日线用途验证及研究forecast不能当当前正式输入的限制，本票展示事实与明确拒绝，不造真实正向资格。冻结20没有 ADD/HOLD/判断型WAIT/反向或冷却政策，命名缺口 `POLICY_FOR_ADD_HOLD_WAIT_REVERSAL_COOLDOWN_NOT_FROZEN`；仅已有政策覆盖的动作进入生成器，缺口不替换为默认WAIT。旧 `/api/formal/*` 防护入口继续关闭，当前动作有新的实际评估/查询/replay接口，并非用constant403代替本票。

26/27接入真实意向时仍需在自身账本短事务内复核当前动作、竞争占用、实际成交与部分成交；本票 `current()` 尚没有 caller-db参数，26可在本票新模块上加具体事务 seam，不能跨冻结研究源改写。28按用户要求先站内通知与配置页，实际外部发送等待用户配置。上述后续验收没有提前宣称通过。本票工作树与未提交实验档案保留，待独立接受和哈希保全核验后由父代理按清理流程处理。
