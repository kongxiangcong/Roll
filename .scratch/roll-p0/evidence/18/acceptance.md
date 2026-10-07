# 18 日线执行与成熟标签验收

2026-10-08，独立树 `D:/dsh-proj/Roll/.scratch/worktrees/18-daily-execution-labels`，分支 `codex/roll-p0-18`。起点245b1d6（17已合），源606645f→合最新集成e5559c9得f949188→定向修复344f198。后续仅票据/证据文档提交；父execution-status未编辑。API8038/web5198。Python3.13.12；FastAPI0.141.1、pyarrow25.0.1，12原锁定openai-agents0.23.1/OpenAI3.26.0同步后兼容，18无新增依赖。

## 实际来源、范围与原件

只读来源 `D:/dsh-proj/Roll/backend/.roll-data/implementation-evidence/17/acceptance-17-final`，其原07真实RAW181日、17登记协议和真正宿主分片保持。27个raw/Parquet原件按字节复制并核SHA；SQLite作隔离逻辑备份，公共账户核验0/空持仓，未把07/08合成工程资金当用户授权或前向起点。本票不解析SEALED价格/收益、不进行候选拟合或最终PASS查看；不改17原目录。

最终实际HTTP在2026-10-07 20:50:53–20:51:09 UTC（上海10-08）取得工程结果：DEVELOPMENT80、CALIBRATION40个预定标签窗口日期，120个不可变执行记录全部UNSCORABLE，真实训练支持0；40个期限跨分片边界，99个观察日历史规则范围未适配，全部历史状态/公司行为未知。实际价格为原07当前修订原价，历史PIT和今天名单回溯独立性不证明，未知金额/状态/规费不填0或正常。逐对象/日期/原因/输入SHA由公开execution-support查询，重复日期/压力/复评不是独立成功样本。不能用METHOD样例替换这些缺口解锁19训练/20冻结/21准入。

完整实际报告与原件长期待根保全：

- `D:/dsh-proj/Roll/.scratch/worktrees/18-daily-execution-labels/backend/.roll-data/acceptance-18-final`：最终SQLite/raw/Parquet、完整real-execution.json、原进程日志与Chrome追加的不可变记录。
- `.../backend/.roll-data/acceptance-18-second`：前一版实际120/METHOD记录保留。
- `.../backend/.roll-data/acceptance-18`：首次真实HTTP500（identity额外code误传rule）报告/日志保留，显式按exchange/board/type三字段修复后成功。
- `.../backend/.roll-data/acceptance-18-methods`：最终公开pytest的18合成边界档案副本，仅METHOD，不是历史实况。

[runtime-preservation.json](runtime-preservation.json) 按原文件绝对来源/相对映射/SHA256/字节数登记。清理工作树前须根复制并逐项核验，不能只保留JSON指纹删除原件。[source-byte-check.json](source-byte-check.json) 核17源仍相同、冻结引擎canonical-LF指纹=Git blob，原供应商/Parquet SHA按原字节。[最终紧凑报告](acceptance-18-final.json) 含120ID/结果/输入指纹和全量报告路径/SHA，原件与全量报告不移动/覆盖。

## 输入、预期、实际与证据

| 主责任 | 固定输入/公共路径 | 预期与实际 | 证据 |
| --- | --- | --- | --- |
| AT-35/EVAL-04切片 | METHOD Jan05事件20交易日；Jan06上涨，label_as_of Jan06 16:00 | IMMATURE、空标签/收益、不训练；Feb02 15:00成熟规则保存，完成bar15:01可得之前也不成熟。真正标签available_at为实际Oct结果生成；复评追加子ID，原未成熟不变 | [公开测试](../../../../backend/tests/application/test_execution_labels.py)、[HTTP](acceptance-18-final.json)、[定向5](backend-directed-final.txt) |
| AT-36/MOD-04 | 同日stop98/profit104均触线；买入日T+1；后续停牌/0量触线 | 不推顺序/不保证成交；保守费用后下界、INTERVAL空评分、UNDETERMINABLE不可评分，含错过触线的期限退出。Jan07停牌/零量不能成为出口，排除日期持久保存，合法Jan08出口 | [原红](backend-touch-red.txt)、[定向绿](backend-directed-final.txt)、[METHOD截图](18-method.png) |
| AT-37/EVAL-05 | NEXT_OPEN/NEXT_CLOSE/再延迟OPEN/超冻结价窗；0/50/100% | 日期/价窗/计划数量先冻结；0和超价NO_EXECUTION不当预测亏损，部分成交整数增量，T+1可卖；停牌入场不成交、停牌/未知或0量期末无法退出；客户端报价不能注入成交 | [公开测试](../../../../backend/tests/application/test_execution_labels.py)、[HTTP11方向](acceptance-18-final.json) |
| EVAL-05费用 | 100股原价100→110，基础3bp佣金每侧、最低5、转让0.1bp每侧/卖印花5bp/滑点5bp | 分项Decimal成本，佣金包含规费，额外规费0为明确重复收费规则而非未知费用0；基础净974.29。登记30bp佣金/20bp滑点压力净889.31，实际券商费仍UNKNOWN | [公开测试](../../../../backend/tests/application/test_execution_labels.py)、[契约](../../../../docs/daily-execution-contract.md) |
| 成熟/提前结算 | 20日跨分片/未知时段；已适配Aug03盘前；晚到退出bar；归档最终现金90、Jan08 12:00、无退出OHLC | 跨界purge不可评分；未知时段留限制，适配官方15:00盘前IMMATURE；bar可得晚于评估也IMMATURE。仅确定性全股现金/精确时点/最终费用处理允许早成熟；不造退出OHLC/午夜，未确认不提前 | [时点原红](backend-maturity-red.txt)、[定向5](backend-directed-final.txt)、[公开测试](../../../../backend/tests/application/test_execution_labels.py) |
| 原输入与不可变 | RAW→先归档SHA→短SQLite事务→追加结果，重启、原件下载、replay、当前复评 | 原event/窗口/成本/来源版本保持；联网0结构化重算一致；换引擎版本409保留旧结果；附件/nosniff；公共真实账户0完全不变 | [最终HTTP](acceptance-18-final.json)、[原日志](acceptance-18-final-process.txt)、[源码字节核对](source-byte-check.json) |
| 真实支持缺口 | 原07→17仅DEV/CAL120窗口日期 | 120全部UNKNOWN不可评分，0真实训练，40跨界；真实照做分布未知，未计算真实收益/模型概率、未授G7 | [最终HTTP](acceptance-18-final.json)、[真实页面](18-real-unknown.png) |

## 验证层次与实际红项

TDD先404红→公共API SQLite/原档案绿；[初始18/17组合26passed](backend-owned-combined.txt)50.70s，终止现金无退出OHLC修正后[26passed](backend-owned-final-source.txt)51.54s；父审两条时点/触线修复[定向5passed](backend-directed-final.txt)10.86s。最终集成56项（18的20、17的10、11/12相关方法/恢复）：[55passed/1failed](backend-integrated-final.txt)225.87s，唯一12固定localhost实际SDK多轮方法等候20s未终态；[原run状态](shared-sdk-first-run-status.json)保存20:52:35→20:52:55测试退出后CANCELLED/Job无剩余PID。仅该同代码方法[单例复验1passed](backend-deepseek-focused.txt)8.63s，未改生产预算、未放宽断言。原组合不是全绿，也未诊断成随机失败或实盘SDK问题；20秒fixture轮询与宿主任务上限关系由根最终审计/31继续收口。没有实际provider/计费模型请求或凭据读取。

最终独立安装Chrome [2passed](browser-final.txt)14.9s，[原JSON](browser-final-results.json)、[真实120未知页面](18-real-unknown.png)/[METHOD成熟区间页面](18-method.png)；保存未成熟→原输入重放→追加成熟复评→原结果保持、真实账户0、主入口5项均核验。[构建](build-final.txt)48modules/tsc通过。前次Chrome严谨选择器匹配3个区间元素的[原红JSON](browser-first-red-results.json)保留，仅first定位后通过，无弱化标签/范围断言。默认全文件Chrome仍有05共享fixture状态红，见仓库browser-acceptance；本票未运行/未声明默认全suite绿。

## 边界与后续

本票工程范围完成：固定日线执行、成熟/未知/未执行定义、原输入重放与页面；不创建回测框架、正式动作或真实财富。METHOD明确合成规则/状态/完成时钟，不能替代真实历史证据。真实状态、公司行为、早期规则/PIT、金额与实际费用仍有限；只有适用的真实后继报价才可另测下一可观察价格，本票无该后继历史报价路径。19须消费本票原输入/支持并如实保留不足/失败，不造未知概率；20完整冻结、21准入、22独立风险政策、30/32真实起点/期限各自后续。
