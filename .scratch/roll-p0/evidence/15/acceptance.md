# 15 · 按需/盘后观察、覆盖与维护验收

本票自身范围完成，后续消费者联验保持部分。上海日期2026-10-08，原日志/快照使用实际UTC。起点68e3b59；实际合入12/17的e5559c9，再合18的1ab8903，保留双方应用路由、双取证后端、研究输入审计和执行标签。源合入点6502390；本票最终提交另见任务Comments/协调报告。未宣称全仓225用例或默认共享账户E2E全绿。

契约：[review-contract.md](../../../../docs/review-contract.md)。公开接口和输入断言：[test_reviews.py](../../../../backend/tests/application/test_reviews.py)、[test_review_process.py](../../../../backend/tests/recovery/test_review_process.py)。主要seam是真实FastAPI、SQLite和隔离原件；源码字段不接受客户端报价/收益/预测。没有模型凭据、资金授权或资格仍可读取普通事实，网上权益/风险线索不入账。

## 输入、预期与实际

| 场景 | 输入与预期 | 实际 |
| --- | --- | --- |
| 休市独立流程 AT19/48/82 | 2026-10-07 10:00上海，年度休市；空账户可观察/历史，资金/模型未知不拦事实 | CLOSED/HOLIDAY，account0、forecast=null、forward=false，原ID重启不变 |
| 报价/日线 AT20/21 | 9/30已完整与10/8未完整日线，9/30原报价；盘中不能把当天bar做完整输入，盘后不把9/30冒作当天齐全 | 最近完整9/30、10/8 incomplete/model_daily_input_allowed=false；源报价原时点保留，POST_CLOSE_DAILY_INCOMPLETE局部待补 |
| 取数/重试 AT26 | 共用07/08请求，外部ConnectTimeout；3尝试、1/2秒退避，单尝试8秒/4调用/4MiB | 原ID、3 retrieval_runs、实际错误/时点/预算、PARTIAL，不发布模型输出/动作/通知；未接入指标为null |
| 空账户背景 | 无持仓但固定背景可补查，股票与背景共用调用/时间/字节预算 | 2个背景取得9/30原日线；无账户变化，仍保留报价/量纲未知 |
| 取消/竞争 | 受控阻塞HTTP边界；第二宿主同库、取消第一任务、排队第二任务 | 唯一worker，live DIRECT_HTTP原运行不被重启标签覆盖；取消不发布，第二任务继续。该等待边界为控制案例，不冒充真实供应商故障 |
| 正常关闭/线程租约 | 阻塞跨原3秒关闭边界，旧任务仍未退出 | 租约保留到实际执行边界停止，peer不能提前调用；8秒技术请求上限与有限关闭并存 |
| 语义状态 AT23 | 10:00/10:30同一事实状态 | 前后snapshot关联、NO_SUBSTANTIAL_CHANGE；不重建未知触发顺序，forecast/sample仍无 |
| 真实知识时间 | 提交后才收到源事实 | completion knowledge >=available；原event cutoff不变，ACTUAL_COMPLETION_NO_BACKDATED_KNOWLEDGE |
| 日历/休眠 AT25 | 活宿主从9/30跳至10/9；周检查10/7休市顺延10/8 | 一条实际心跳缺口、非监控故障；只在10/9真实检查逾期项，下一名义周10/14，不漂移10/15 |
| 正常离线维护 | 10/8关闭、10/12恢复，10/9维护错过 | NORMAL_OFFLINE缺口；实际10/12 OVERDUE_CHECKED仅一条、下次10/16；27业务检查NOT_CONNECTED/null，无统计通过次数/重训 |
| 运行日审计 RUN02 | 10/8运行后下一次见到10/12 | 只记录实际两日审计；task/snapshot=null的运行日检查不造观察，不补10/9—11审计 |
| SQLite实际错误 | BEGIN IMMEDIATE持锁12.5秒跨真实10秒写超时；同宿主显式recover | OperationalError/WORKER_EXCEPTION原记录保留，恢复RUNNING；后续正常关闭独立记录NORMAL_CLOSE，不沿用旧错误 |
| 实际elapsed超时 | 控制HTTP等待8.1秒 | TIMED_OUT/attempts1、实际acquisition>=8，部分已知/缺口及audit保留，无额外第四调用 |
| 原件修订 | 08真实resolve/revision接口，原价10→11且量价额一致 | 新观察采用11、旧依赖INVALIDATED/新CURRENT；旧观察价格10/原记录与零联网replay不变 |
| 明确重点复盘 | 用户指定close，原snapshot/fact_index/field/reason、原knowledge cutoff | 冻结原值10/rawSHA，任务/观察/audit关联且幂等；错对象/版本/后知输入拒绝。14状态PENDING_CONSUMER_14、verification_id=null，尚非多源核验通过 |
| 同时区别名 | 10/7 10:00+08与02:00UTC | 同任务ID，原表达保留；哈希UTC规范化 |

## 实际进程与浏览器

`final-api-process.log`：当时16 API +6实际OS案例，22 passed/108.11s。其后同一16案例的知识/引用边界1例、身份相关3例与同宿主恢复1例分别定向重验；身份更改后的4相关OS案例32.54s通过。新增Windows原生正常关闭另1例6.70s通过：独立隐藏进程组向uvicorn发CTRL_BREAK，实际生命周期结束；重启公开coverage为NORMAL_OFFLINE、原观察完整相同。合18后2个源任务/租约交点10.32s通过。以上共16公开行为与7个OS场景的票级证据，分层记录，不相加冒充一轮23用例suite。

OS案例包括观察提交前/后与取得回执后终止，维护触发提交前/后终止，三次连续真实进程中断后耗尽同身份尝试（原红灯attempts4，修复后FAILED/attempts3、result=null），以及实际Windows正常关闭。临时SQLite/HTTP进程通过公开查询断言，故障注入只在ROLL_ENV=test，未触及用户账户。

方法Chrome：[reviews.spec.ts](../../../../frontend/tests/e2e/reviews.spec.ts)，1 passed，最终JSON含实际开始/完成时长；五入口、无交易声明、普通观察、停牌方法风险、个人权益待确认、固定背景、盤后日线未齐、折叠审计/未接入指标、历史与维护登记。公开account整个JSON前后相同（version2/cash10000/100股），外部观察不写账户。[截图](chrome-method-today.png)、[结果](chrome-method-results.json)、`final-chrome-method.log`。METHOD_CASE与冻结上海16:00工厂仅在隔离测试；不是当前市场真实停牌或用户财富。

真实缓存Chrome：[reviews-real-cache.spec.ts](../../../../frontend/tests/e2e/reviews-real-cache.spec.ts)，1 passed；实际原件REAL_ACQUISITION、供应商quote.upstream_at=9/30、available_at=10/7，重放零联网/账户不变。[截图](chrome-real-cache.png)、[结果](chrome-real-cache-results.json)、`final-chrome-real-cache.log`。这些旧报价不被包装成10/8新行情。两Chrome调用使用不同data目录，不合并成默认共享账户suite通过；既有05共享夹具基线红保留，见browser-acceptance.md。

## 实机容量与保全

设备AMD Ryzen7 7840H，8核16线程，29734326272字节内存，Windows与Python/Chrome具体版本见device JSON、真实性能JSON。实际工程名单20只+3固定背景；4条正缓存报价、4个正缓存完整日线，其余对象缺口显式。工程账户/名单不代表用户财富。

`real-archive-and-api-performance.json`：50次真实FastAPI/SQLite today+summary本地读取P95=122.115ms；`chrome-cache-performance.json`：50次真实Chrome导航至完整今天/保存观察显示P95=449.9785ms，≤2s。两个计时分列；均无新公网调用，不替代公网时延承诺。取数任务另记acquisition/network工具边界/local发布，控制超时与原件缓存不混作真实provider SLA。

07 root保全目录acceptance-07的45文件只读复制，逐字节/SHA一致，源后比较0差异。旧观测缺少observed_at的红灯由实际原档暴露；现在只读原snapshot.created_at并标明原快照实际发布时间，不改原记录。重放原件/Parquet可核查。

本票自有ignored运行保全清单：[runtime-retention.json](runtime-retention.json)，6个精确目录/176文件，包含原件、Parquet、SQLite/WAL和工程收据；明确两份最终必要运行与较早控制/失败状态。不得按宽泛目录删除；父流程复制后逐字节/SHA再验，最终清理归父流程，本票未删除任何树或原件。最终方法目录acceptance-15-method-final-4，真实副本acceptance-15-real-205133。

## 尚待实际消费者

14真实verification_id与核验结论、19/25概率时点/资格、25/26真实未决意向/动作失效/翻转、28通知/重复/渠道异常、27标签成熟/资格/新实验业务维护、30确认性样本及32持续影子仍PARTIAL/NOT_CONNECTED；本票不预造输出或以0冒充健康。RUN02关键请求已冻结14-compatible原截止/疑点，但最终真实核验联验由14/调用方承接。数据完整性、账户状态、资金授权、技术资格与任务服务健康保持独立。
