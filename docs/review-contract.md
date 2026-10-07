# 按需观察、覆盖与维护契约

15 提供普通事实的独立路径。没有资金授权、模型凭据或技术资格仍可观察、回看和同步账户。不会发布 BUY/HOLD、概率、动作、通知或前向样本。未来消费者未接入的指标为 `NOT_CONNECTED/value:null`，影子版本为 null。

## 公共入口

- `POST /api/reviews/tasks`：`mode=ON_DEMAND|POST_CLOSE|HISTORICAL|RECOVERY`、可选带时区 cutoff、`refresh_missing`。盘后须为已适配日历的 AFTER_CLOSE/CLOSED；其它阶段可按需观察。HISTORICAL 明示实际运行时的历史回看及当前账户依据，不把当前账户伪称过去快照。
- `GET /api/reviews/tasks/{id}`、history、summary、health；`POST .../{id}/cancel`、`.../{id}/replay`；`POST /api/reviews/recover`。
- `GET /api/reviews/audits`、`/audits/{id}`、coverage；`POST /api/reviews/maintenance`、GET 同路径、GET `/maintenance/checks`、POST `/maintenance/check`。
- `POST /api/reviews/tasks/{id}/verification-request`、GET `/api/reviews/verification-requests/{request_id}`：明确重点复盘冻结 USER_SELECTED/MATERIAL_DOUBT/CRITICAL_CONFLICT、疑点理由、最多10项决定性字段及每项最多6个原快照/事实下标。字段必须属于原观察对象与事件/知识截止；请求关联 task、snapshot、audit 和原值/原件 SHA。知识截止保持原观察值。普通审计不自动触发。

当前14真实核验调用尚待其源合入及联合调用；已冻结14-compatible payload，状态 `PENDING_CONSUMER_14`、verification_id=null，不代表核验通过。14完成后消费原 request 创建真实核验并追加关联，不能伪造 ID 或放宽知识截止。

## 原事实与时间

Asia/Shanghai 和06原件支持的沪深2026交易所日历决定阶段；未知年份/交易所继续 UNKNOWN，不按工作日推断。报价供应商时点、累计量及单位、日线完成状态、披露/事件日期、实际 available_at、快照和原件 SHA 分列。当前未完整日线不能代替最近完整 RAW 日线，昨日日线不冒充当日已齐；固定背景保留未知量纲，不合成情绪分数。

缓存选择受事件 cutoff 与知识截止共同约束。联网后新事实用实际完成时知识截止，保留请求事件 cutoff，不将稍后获得的事实写成提交时已知。HISTORICAL 为 `RETROSPECTIVE_ACTUAL_RUN`，不产生原时点前向证据。旧07观测缺少单条 observed_at 时，只读原 snapshot.created_at，并明示 `ORIGINAL_SNAPSHOT_ACTUAL_PUBLICATION_TIME`；原记录不改。

08来源解析的 freshness/source_checks/依赖修订随新观察冻结。实际修订改变新日线价格与状态，原已发布观察仍保留原输入；replay 校验涉及原运行的原件/Parquet与 SQLite 原事实，网络调用为0。公告、网上权益、风险线索不写账户；实际账户仍仅经原草稿/确认事务。

## 持久执行

具体 SQLite 表：review_tasks、review_worker、review_sessions、review_coverage_gaps、review_audits、review_running_days、review_maintenance、review_maintenance_checks、review_verification_requests。创建幂等，schema_migrations 记录 `15-reviews-v1`，不重置 global user_version。

任务身份包含 mode、上海日期/阶段、事件截止（哈希以 UTC 规范化）、账户/名单/数据版本、影子未知状态和补查选择；保存原时区表达。重试、恢复复用 ID；同截止的时区别名不会重复创建。不同实际观察以快照前后关联与语义 fingerprint 显示 `NO_SUBSTANTIAL_CHANGE`；这不代表已生成的动作/通知去重通过。

一枚持久 worker lease 绑定 PID、实际创建时点与 nonce。另宿主只能排队；只在旧线程实际停止或旧宿主死亡后接管。正常 close 等待最多9秒；若边界仍阻塞，保留 lease，实际线程 finally 释放。普通 HTTP 每次尝试最多8秒、4次外部调用、单响应1MiB/合计4MiB；股票与固定背景共享调用/时间/字节预算。最多3尝试，失败退避1/2秒；三次实际中断后 FAILED，无第四次观察。SQLite短事务不跨联网，结果与任务审计同事务提交。取消不发布结果。

任务实际 module_errors 与运行日/按需/恢复审计可查询。每日审计只记录程序真实见到的上海日期，不补缺席日、不自动造观察。异常 worker 退出保存 WORKER_EXCEPTION、原错误及 MODULE_FAILURE_COVERAGE_GAP；正常关闭保留普通离线间隔。运行中实际心跳间隔超过60秒仅标未观察间隔（技术活跃心跳缺口检测阈值），不宣称分钟行情捕获或自动监控故障。不重建缺席时段触发顺序、不追发过期机会、不补造预测。

## 维护与展示

ONCE/WEEKLY/MONTHLY 检查点保留名义日期和交易日历顺延日期。节假日顺延不漂移下一名义周/月。自动运行检查与按需/恢复补查写唯一 schedule+due 身份、原计划时点、实际检查时点和逾期秒数；多次错过只做当前实际检查并列 missed_due_instants。27的标签成熟/资格到期/实验条件为 NOT_CONNECTED/null；不增加统计通过次数或触发重训。

今天先显示能力、账户时点、数据/最近运行与持仓事实；关注对象、公司原文与诊断折叠。原证据链接保留对象、披露/事件与获知时点。五入口不增加新一级导航，历史查看保存观察，设置只提供维护时间/频率等产品设置。

acquisition_seconds 包含取数/归档/规范化总耗时；network_seconds 使用共用工具 started/finished 边界（含该边界内原件归档，不伪称纯线路时间）；local_seconds 另记剩余处理/发布。缓存API读与真实Chrome全页P95分别记录，名单规模、设备和已缓存/未取得对象一并说明，不能拿MockTransport时延冒充公网承诺。

19/25 概率、25/26 未决意向/动作/翻转、28真实通知、27业务维护、30确认性样本以及32持续影子均待实际消费者联验。本票未接入状态不授技术资格或资金用途，不倒加前置依赖。

疑点请求与14消费共用公开输入契约：reason最多2000字符、fact_id最多100、field最多80；新输入不合规返回422。旧保存命令不兼容时消费返回可行动409，保留原观察知识截止与旧请求供重提，见[独立核验契约](independent-verification-contract.md)。
