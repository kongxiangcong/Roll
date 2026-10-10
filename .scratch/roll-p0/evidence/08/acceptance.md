# 08验收：用途、换源与原输入重放

08已合最新集成d0cd37d，源码提交6c9372f。沿implement-spec/TDD纵向公开FastAPI/真实SQLite/raw+Parquet；未增加依赖，未改execution-status。契约见[用途与换源](../../../../docs/source-resolution-contract.md)。真实源、METHOD_CASE、METHOD_WAIT和合成账户分别记录。

实际报价自动补查不是07显式选Tencent primary：原Tencent运行必需QUOTE.volume_shares缺失，沿其原run_id归档校验后调用Sina一次。两条实际路径同对象SSE:600519、2026-09-30、RAW报价；last/open/high/low/previous_close/amount用Decimal逐字段比较相同。Sina1258.620、原股数3833098、成交额4797246636.000元，腾讯reported38331量单位UNKNOWN，不进行外推手股换算。Sina单位依据是[官方证券页](https://finance.sina.com.cn/realstock/company/sh600519/nc.shtml)及其[原parser](https://n.sinaimg.cn/finance/hq2018/utils-hq.js?ts=3.7)，后者SHA f41849458131169afb92f0ea1b266841052419867f9ea3b363e0fafaa4ebc3ee。仅明确SSE MAIN STOCK范围已核验，其他身份/指数单位保持UNKNOWN；公开GET成功不声称商业再分发许可。原JS只登记数据字段依据，不执行或迁入。

实际获取发生在上海2026-10-08凌晨，报价上游仍为9/30（Sina15:34:59，腾讯16:14:58），报告日、上游、实际接收、available及本次消费知识截止分别保留。原request.cutoff的PIT布尔不被永久套用；本次消费按自己的cutoff重新核验。两源价格/金额相同不意味着独立原始依据，14独立性仍待联验。原源探针只作为字段依据，票级闭环是[真实报价运行](real-quote-closure.json)，并验证公开归档attachment/nosniff、SHA、原运行回放与缓存/刷新页面。

实际异步日线补查另见[真实取数及确认](process-real.json)：Eastmoney两条原价/qfq路径实际RemoteProtocolError，完整失败tools/时点/原因保留；08有界自动取得Tencent两条RAW/qfq规范化记录（9/29—9/30）。4次调用、0重试、总外部1.158秒。历史成交额仍缺失，complete_daily_model受限，状态DEGRADED，不因必需close存在就授完整模型资格。

同进程、同SQLite、实际HTTP确认100项P95 323.660ms，11项在轮询观测RUNNING期间完成，重叠P95 83.443ms。真实源较快，重叠样本少且轮询可能高估一个25ms间隔，不外推持续慢网覆盖。隔离账户为合成基线与确认交易，不包含用户券商凭据/真实账户事实。修正过验收脚本汇总字段错误；早期真实报告仍保留，但本票采用最终exit0运行。

[固定等待及ReadTimeout](process-method-wait.json)明确为MockTransport六秒回调等待后抛固定ReadTimeout，不冒充真实上游超时测量：实际HTTP确认100项P95 383.983ms，30项重叠、重叠P95 97.613ms；补查6.188秒后返回DEGRADED、失败与缺口。该实际子进程运行中终止再重启，未完成任务INTERRUPTED，账户版本111、已保存ReplayRun均未丢失；没有产品reset接口，取数不占账户长事务。可复运行命令：

```powershell
backend/.venv/Scripts/python.exe -X utf8 scripts/source_resolution_acceptance.py --data-root backend/.roll-data/acceptance-08-new-run --port 8028
```

目录必须是新隔离目录，不覆盖原验收。真实与方法两组均记录自己的runtime目录、源run、规范化facts、确认样本、轮询时间线及重放；原脚本可分别`--kind real`/`--kind method-wait`。

[07原输入复验](07-original-replay.json)：从已保全根`D:\dsh-proj\Roll\backend\.roll-data\implementation-evidence\07\acceptance-07`只读SQLite备份及37份原件SHA一致副本，在08服务公开API重放7个07版本原运行，网络0，未写回原07目录。历史回放不证明当时市场可得/无上游修订。

公开API方法用例最终14 passed/31.62秒：[原输出](backend-resolution-final.txt)。覆盖声明交易所错配/请求外交易日报价归档但禁消费，已知字段与必需缺口分离，超20真实持仓逐对象缺口和调用预算，实际0价格禁当前监控，session用途、自己的知识截止、缓存时间不刷新、价格冲突、qfq版本不可拼接，补录修订/Observation失效、原输入/原观察重放、新运行关联及无效revision不占槽。

组合backend173 passed/578.52秒：[原输出](backend-final.txt)。此套件启动于81bf13c（含d0cd37d最新集成），最后一项监控价格/完整对象守卫及对应新增方法用例在启动后追加；因此173为该组合基线，最终局部delta由14项专项与浏览器验证，不声称同一源码HEAD完整174项一遍通过。账户迁移/恢复/CSV/05对账组合保持基线全部通过；不重复不相关恢复套件。构建45 modules通过：[原输出](build-final.txt)。

浏览器：METHOD_CASE修订页面1 passed，真实SQLite旧1258.620→新1259.620修订，旧依据INVALIDATED警示、原状态DEGRADED/原输入重放网络0、原值仍可查；[报告](browser-method-results.json)、[页面](08-method-revision.png)。早期方法页面定位器重复及测试端点不经/api代理的错误保留为red日志，修正测试路径，没有弱化产品断言。

默认全文件浏览器suite存在05夹具共享状态冲突：05首例硬编码空账户version0，排在先前baseline/fill/未知费用用例之后，忽略draft409/confirm422，其第二例依赖第一例的利息事实，遂失败。保留[默认全文件11pass/2fail/1skip报告](browser-combined-results.json)和[原输出](browser-combined-final.txt)，不称默认suite全绿、不改账户校验。05使用空隔离账户独立2 passed/13.8秒，其余共享组合11 passed/1 METHOD skip/36.9秒；可重复命令及最终分组结果见同目录browser-reconcile-isolated-final.txt和browser-shared-isolated-final.txt。31负责通用可重复验收runner的收口。

运行原件不入Git但已经逐文件登记[保全清单](runtime-preservation.json)，共144文件；均在`D:\dsh-proj\Roll\.scratch\worktrees\08-source-fallback\backend\.roll-data`下：probe-08保留实际源网页/parser/报价，acceptance-08-browser保留最新及前次完整JSON导出和不可变raw/Parquet，acceptance-08-process-final/{real,method-wait}保留实际SQLite/原件/运行日志，acceptance-08-07-replay保留37份复制原件及只读备份。早期process-01/02原证据同样保留。清理本树前须按清单复制并核验SHA，不能仅保留JSON指纹后删除原件；本票未移动/清理这些材料。

限制：实际真实current STATUS仍UNKNOWN；Sina成交量映射未扩至STAR/其他市场/指数，历史金额缺失、800日线深度、qfq跨源版本/PIT修订证明继续保留。换源只覆盖日线和报价，其他公司材料无适配备源。真实修订通过新取数关联但本次相同报价为NEW_RUN_NO_NORMALIZED_FACT_CHANGE，真实数值修订/失效由明确METHOD_CASE证明。真实模型/预测/动作依赖和独立核验在11/13/14/19/25继续联验；08不签发任何正式交易或模型资格。
