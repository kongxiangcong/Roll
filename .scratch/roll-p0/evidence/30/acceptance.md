# Ticket 30 — 前向归档与研究终点

2026-10-11；Completion **partial**；Status 保留 `ready-for-agent`。已合入23产品集成 `676b5ff` 和独立证据 `4646202`，本票源码/证据仅本地提交，未推送。

## 已实现的工程

`ForwardArchive` 使用既有 Reviews 单后台 worker/租约、SQLite 登记和共同应用用例，无新调度框架。身份固定为 protocol/checkpoint/trading_date；账户、快照、重试依据不进入身份。保存冻结模型预测、特征可得性、动作/拒绝、独立连续影子、费用/规则/输入与归档指纹。文件先保存，首次样本与起点在同一 SQLite 事务提交；崩溃孤儿文件不代表成功。起点取首次成功事务的 Host 时钟，三自然月截止复用登记算法，月末夹紧，不用90天。

METHOD 与真实前向使用同一存储、身份、截止和结算算法，METHOD 仅测试环境，公开命令没有输入日期/资格/PASS覆盖。METHOD plan 的工程起点从不写入真实 `research_protocols.forward_started_at/forward_deadline`。前向消费当前实际已知的21完整日线上下文；今日取得旧日线不能成为旧预测。新增纯适配器按冻结特征顺序复用四项数学计算，重建研究用途按生效现金权益计算经济回报，避免除息成为虚假alpha。receipt、available、known 时点均不得晚于消费时点，完整RAW/SHARE、有效现金来源和数值必须通过；主入口复核既有交易日历、规则和冻结源码。

20交易日未来市场日历是已登记的开闭日期，真实分支不读取未来行情/标签。NEXT_OPEN 未观察仍pending；停机恢复只采当前合法检查点，不补旧预测。已有拒绝机会独立固定手数反事实诊断不计入连续策略收益。成熟、未成熟、成熟证据不足分开，未成熟标签保持null。截止结算只使用原截止已知的输入；关闭事务先登记 CLOSING 及原截止，阻止并发采样，进程中断后继续同一关闭。USER_STOP/SAFETY_STOP 保留依据和原最迟期限，没有 EARLY_PASS 命令或新增统计PASS检查点。未知年份日历保留缺口，不能伪造工作日或阻止期限关闭。

终点保存 INCONCLUSIVE、validation INCOMPLETE、review PENDING 及具体21/23/G1—G7缺口，NOT_GRANTED；30不生成实际确认性统计PASS，也不代替33。恢复锁在同一公共/后台采样入口拒绝补写起点。离线重放核样本/评估/终点绑定、重算冻结预测及连续模拟，0联网。

## 分层验收

逐步纵向公共 API 红→绿日志：`forward-red1-elevated/green1b`（入口404→归档）、red2/green2（成熟日历）、red3/green3（独立纯适配器）、red4/green4（成熟结果入口）、red5/green5（用户停止）、red6/green6（真实备份恢复锁）。独立adapter测试是获准的算法边界，不是客户端资格writer。`environment-red1.txt` 是Windows pytest私有目录权限错误，不列为业务红。

核心工程单轮 [forward-final-tests.txt](forward-final-tests.txt) 为 **22 passed、1 failed /221.09s**：15个公共/算法案例中账户快照改版用例的新增夹具没有提供证券列表/身份，`request_id`读取失败。仅测试前置修正为通过既有公共账户和市场身份入口后，同一用例 [forward-final-revision-fixed.txt](forward-final-revision-fixed.txt) **1 passed /16.47s**；实际账户版本0→1、实际新快照id存在，原前向sample与影子revision仍1。两个运行分开保留，不表述为一轮23全绿，不重复已通过的故障/租约回归。

该核心单轮其余覆盖：METHOD唯一身份/重启；缺日、原期限、未成熟分类；成熟拒绝及收益隔离；用户停止；四个月末/闰年边界；真实备份恢复锁；6项纯adapter值/可得性；5项真实Uvicorn进程检查（archive后、commit前、commit后以退出码86中断、4路HTTP并发/强制杀进程重启、close-claim中断恢复原截止）；既有Reviews取消/lease交接两项与23跨审阅/取证入场一项。未重复根全量后端回归。

收口重放发现 ISO 字符串比较会错排同一截止时点的上海/UTC offset，[公共API红](forward-offset-red.txt) **1 failed /14.85s**。改为带时区datetime比较，稳定最终源码 `11df4e367f82b8970b1af1e7346225d990dd456a` 的 [9项公共API](forward-offset-final.txt) **9 passed /96.84s**；包含上述账户/快照改版与成熟/未成熟、等价UTC截止重放及恢复锁。仅此重放过滤行改变，不将先前5进程/3worker/6算法收据称为修正后重跑；根后续影子财务修正者还会关联forward回归。

最终 [Chrome](forward-offset-browser.txt) **1 passed /48.0s**，新独立METHOD运行目录、真实React/FastAPI/Chrome，唯一归档1、实际起点未启动、工程期限、重放0联网，正式操作按钮0。[截图](forward-method.png)已目视核对。最终 [TypeScript/Vite](forward-offset-build.txt) **59模块 /1.90s**。核心版48.1s/2.05s、原浏览器红、早期绿/build及早期进程收据保留各自版本，不提升为最终实际研究证据。

[原始SQLite与公共查询](method-integrity.json) 确认 METHOD browser 的 registry 三个真实前向时间字段均null，唯一SQL身份count1，公共协议同样null，公共模型 METHOD_CASE、capability NOT_GRANTED；模型没有system_usable字段（JSON显示null不表示授予）。测试工件和历史样例均不启动真实研究计时。

[核心source-before](source-before-final.json) 与 [核心source-after](source-after-final.json) 的10个产品/其他测试文件SHA相同，仅账户快照用例因夹具修正变化。[最终source-before](source-before-offset-final.json) 与 [最终source-after](source-after-offset-final.json) 全11文件SHA及长度完全一致。12个原19模型指纹依赖与原集成 `eabc7a3` 规范化字节一致；5个23待审批provider源码与 `676b5ff` 一致，本票未修改任一保护文件。后续审阅发现20既有影子登记日分红/同日卖出时序P2，由根安排另一独立修复者处理；本票此版收据不冒充修复后的收据，既有METHOD工件按原时点保留，修后需关联回归。

## 当前真实缺口与32边界

获根明确授权，对21 `actual-current-copy/roll.sqlite3` 仅URI mode=ro读取已登记collection plan/batch及snapshot元数据；未打开实际App、raw、SEALED、账户或凭据，没有取数或写库。[metadata](actual-metadata.json) 前后SHA均 `c8d2a7f55e69718371e6c697635ad14471649b7fc01b1a6483fb1a11b54577d1`。该副本prospective plans/batches各0。历史量价/状态快照（例如 `fae0ea6b-59d1-4182-953b-deba223f0b55`）可含完整历史日线，但 complete_status_verified、完整company_actions证明均0，上市/除权未知；不等于当前盘后输入。

外部事实不足：当前完整量价/状态的真实effective及available时间、完整公司行为生命周期/比例/现金权益及来源审计，独立已知市场日历与合法预登记检查点。当前源码具体限制：`market/baostock.py` 12字段状态只给trade/ST，listing_stage/current_ex_rights UNKNOWN、historical_complete_status_verified false；`market/evidence.py` 当前普通状态parser保留UNKNOWN，同日未确认bar不允许模型输入；现金/复权来源不能从“没有事件”推断生命周期完整。旧研究原件/重建经济回报可以成为当前取得的上下文，不能替代新完整当前状态权益取证。

内部能力缺口：新增适配器的数值及可得性计算和宿主拒绝路径已经实现；现有Host producer仍没有将经实取完整状态、公司行为生命周期和源绑定规则装配为前向所需完整execution packet的闭合路径。没有增加客户端自报complete_status_verified/PASS入口，没有为了验收补造状态。条件消费分支不等于完整真实writer；这是30 partial的实质欠项，并非全部责任归为外部等待。最小映射不能从现有UNKNOWN原件推导必要事实，须新增有依据的来源与核验装配后再闭合实际输入验收。

现20真实候选仍是RECONSTRUCTED_RESEARCH，当前20 API仅历史CAL，不能改名为真实前向；已演化历史影子不得重置。本票不做新真实拟合/预算消费、不读取SEALED、不修改原19 `.roll-data/reconstructed19-v1` 或23profile、审批packet，不执行32、不外发。32还需明确后继实验与当前完整冻结/隔离基线（如现历史影子已演化）、真实合法未来检查点事前登记、实际当前可得完整输入与20-session日历；满足后首次实存才有真实起点。今天2026-10-11上海周日不伪造合法盘后预测；33等待实际自然月/成熟证据。

## 保全

[runtime-preservation-manifest.json](runtime-preservation-manifest.json) 保存已停止的核心版与最终offset修正版METHOD浏览器、五真实进程场景、恢复锁、两版账户快照及最终等价时区成熟场景，共11目录到根 `.roll-data/implementation-evidence/30/`；逐文件SHA256/长度相同、mismatches0。[核心8目录清单](runtime-preservation-core-manifest.json)保留原时点。运行DB/raw不入Git，必要资料在清理工作树前已保全。未删除任意根初始未跟踪资料、未reset/stash/clean，未推送。
