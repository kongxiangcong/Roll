# 07 验收：有限市场事实、原件与客观观察

日期：2026-10-08（上海）。本票有限范围实施完成，Completion=complete；Status保持ready-for-agent。真实外部取证与METHOD_CASE分别登记，08/11/12/14/15及模型联验仍归责任票，不以本票样例代替。

## 环境、集成与检查

07树已合入稳定集成 `7d153f4`，保留01/02/03/04/06/10接口、账户迁移、成交/费用/公司行动/CSV模板及五入口。环境见 [environment.json](environment.json)：Windows、Python3.13.12、Node25.8.1、实际Chrome，隔离API8027/Web5187；新增依赖仅httpx0.28.1、pyarrow25.0.1、pypdf6.19.0并锁定uv.lock。市场取证表幂等创建，不竞争账户全局user_version。

- 最新集成全后台 **138 passed，1 warning，360.99s**：[原输出](integrated-backend-tests.txt)。警告为Starlette/httpx弃用提示。
- 同组合实际Chrome **10 passed，30.4s**（账户、成交、公司行动、CSV、资金、名单与07真实取证）：[输出](integrated-browser-tests.txt)、[JSON](integrated-browser-results.json)；生产构建43模块通过：[输出](integrated-build.txt)。
- 此后补入800行截断案例与必需字段案例，并增加一行缺必需字段禁完整日线模型输入的guard；最终 **15个公开FastAPI/真实SQLite方法案例通过，27.28s**：[输出](method-case-tests.txt)。没有把138个全套结果表述为此后140个全套。
- 最后一行guard后，重新真实Chrome取七组事实、下载逐件SHA核验与零联网重放，**1 passed，14.6s**：[输出](final-live-browser-tests.txt)、[JSON](final-live-browser-results.json)、[页面](live-market-facts.png)。真实运行 `a77909f8-cf68-41a3-a598-a281f97bed7d`，UTC2026-10-07T17:11:29起（上海10/08 01:11）。
- 早期pre-final组合137后台通过；Chrome初始化未等名单加载导致测试误选额外对象而断言失败。保留 [原失败JSON](pre-final-browser-results.json)，测试等待目标对象及已选数量后复验通过；产品取证按钮已有非空已加载名单约束。该pre-final不充作最终验收。

账户输入均是隔离合成基线/成交，经真实应用确认，不能当作用户真实券商账户。外部响应、公司原文和行情是实际公开网络获取；没有私密凭据或付费模型请求。

## 逐组实际样例与范围

实际请求、来源URL/运行时间、原件指纹、逐组覆盖、原文元数据及客观观察见 [real-source-manifest.json](real-source-manifest.json)。最新股票范围仅明确确认SSE/MAIN/STOCK的600519，2026-01-01—09-30；它证明此范围的适配，不证明全市场长期服务或历史PIT。

| 组 | 实际结果 | 保留限制 |
|---|---|---|
| DAILY | Tencent原价181行、qfq181行，实际2026-01-05—09-30；两份原响应独立归档、复权口径和SHA版本分开 | 最多800行；当前供应商修订；历史成交额大多缺失。仅嵌入报价日期/OHLC/量均相符的同日取绝对元额；不回填其他日 |
| QUOTE | 实际Tencent600519报价1258.62，保留上游2026-09-30T16:14:58+08与10/08真实收到时间 | 旧报价不是10/08盘中现价，逐对象陈旧程度可查 |
| ADJUSTMENTS | 两条实际数值记录及权益分派实施原文PDF（4页）；每10股280.2423元转每股28.02423元 | 预披露半年度计划与已实施分派分开；报价调整不证明券商已到账，只有待核观察，账本不变 |
| ANNOUNCEMENTS | 业绩说明会公告AN202608141827994407，原JSON与2页PDF实际归档 | 单页最新30条、供应商总数1074不是已采齐深度；原文只有限摘取，完整PDF保留 |
| PERFORMANCE | 三条实际财务记录及半年度全文AN202608141827994408（110页） | TOTAL_OPERATE_INCOME明确为营业总收入92278072083.21元；不能混作营业收入90703260964.48。报告期与披露日/索引时钟分离 |
| MAJOR_EVENTS | 重大事项AN202607171827064564，原JSON与1页PDF | 按来源分类明确选取一条实际样例，不扩为全市场新闻或所有重大事项完备性 |
| STATUS | 实际生产路径保存UNKNOWN事实与CURRENT_STATUS_UNKNOWN缺口 | 不用旧报价上下限确认当前停牌/风险警示/上市阶段。正常、停牌、风险警示、除权、未知五类仅METHOD_CASE固定传输样本通过 |
| 固定背景 | 原两宽基SSE000001/SZSE399001及预固定相关行业SZSE399997，中证白酒；实际各7根原价日线及报价共24事实 | 行业选择依据CSI2026-08-31官方事实表及600519相关性；仅BACKGROUND，不能股票研究/交易。指数成交量单位UNKNOWN，不外推手转股 |

真实除息短窗另取得6/22—6/30七根原价/七根qfq及实施分派：6/26原价变动约-3.5863%，简单税前现金分派调整后约-1.2743%。观察是EX_RIGHTS_PRICE_CONTEXT，不标签普通暴跌、不自动入账、不宣称完整总收益验证。所依赖原件、日期、计算式和实际观察时点保留。

股票日线Eastmoney当前真实两路HTTP发生RemoteProtocolError，首运行及后续有界诊断保存，没有HTTP响应时不伪造原件。腾讯是请求显式选取的本票primary；未实施08自动换源。其他Eastmoney公告/财务/分派接口与原文PDF实际成功。公开无需密钥仅证明实际可达，不确认商业再分发授权。BSE事实源未适配，真实资产和请求仍显示逐对象缺口；STAR/其他市场手数转换未证明，保留reported/UNKNOWN。

## 输入、预期与实际

| 路径 | 预期与结果 |
|---|---|
| 范围及21只真实持仓语义 | 名单外403、背景研究403；公开账户确认21只持仓后DataRequest接受全部21对象，不套新增关注20只上限；调用预算耗尽逐对象TECHNICAL_LIMIT，末只仍显示 |
| 可靠归档与重放 | 实际HTTP响应先可靠写文件并SHA校验，再引用SQLite；Parquet先保存后短事务发布。最新15件原响应/原文/Parquet下载SHA全匹配，[字节证明](live-archive-byte-proof.json)；重放读原Parquet与SQLite比对，network_calls=0；原件损坏返回409 |
| 单位、精度与缺失 | 仅已证明SSE MAIN普通股票手→股×100；JSON数值token先Decimal、规范化存字符串。真实零量保留ZERO_REPORTED、价格0占位缺失、未知量额不补零；OHLC/量额不一致保存局部错误 |
| 完成度及休市 | 当日日线UNCONFIRMED_CURRENT_DAY，不进入完整日线模型；已知2026休市与未知日历分开；固定休市行不会当正常日线。缺显式required_fields产生REQUIRED_FIELDS_MISSING并禁该模型输入，仍保留基本事实 |
| 时间与修订 | DATE不补午夜，published未知null、报告期/披露/供应商索引/上游报价/真实收取分开；未来事实不能进入过去available_before查询。后续修订产生新SHA/快照，旧快照和观察依赖保留 |
| 历史深度 | 固定800行响应保留实际800行及请求2010起点差异、截断/深度限制，原价/qfq不混合；研究只能按coverage实际范围选窗 |
| 观察与账户隔离 | FACT与DETERMINISTIC_INFERENCE、日期精度、严重程度、原件依赖、未知与待核项可查；公司事项通过取证→原文→规范化→客观观察→页面。前后账户完全相同、model NOT_GRANTED/formal DISABLED |

默认request.cutoff早于收取，point_in_time_input_allowed=false仅指原请求截止。后续消费者需按自己的知识截止重新核验原available_at及事件/上游时间，不能永久否定现在已取得事实，也不能伪装过去可得；当前历史修订材料仍无PIT证明。HISTORICAL只代表现在取得的研究回放材料，不补写过去RetrievalRun、StageSnapshot、预测或前向覆盖。

## 原件保全与复现

实际采集ROLL_DATA_DIR：`D:\dsh-proj\Roll\.scratch\worktrees\07-market-evidence\backend\.roll-data\acceptance-07`，含roll.sqlite3、raw、parquet及background/ex-rights/失败运行JSON。浏览器服务使用OS临时`roll-browser-*`；稳定导出位置为 `D:\dsh-proj\Roll\.scratch\worktrees\07-market-evidence\backend\.roll-data\acceptance-07-browser`，含完整browser-live.json、实际原字节`<sha>.raw`和规范化`<sha>.parquet`。此前组合运行的不可变Parquet/原件也留在导出目录，其运行元数据留在Git清单；latest browser-live.json只对应最后运行。08/17可按清单SHA离线消费同版本档案。

**上述两个目录为真实证据保留位置，不能在只剩JSON指纹时清理worktree。** 后续如需归档/移除树，先保全SQLite与全部raw/Parquet并核验SHA；本次按要求不额外移动数据。源代码测试夹具没有代替这些真实原件。

CSI官方PDF与06交易所原件共九份的Git字节校验见 [reference-git-bytes.json](reference-git-bytes.json)，原PDF/HTML/DOCX关闭文本转换。运行原件下载用attachment与nosniff，不在同源内执行外部HTML。

公开接口、持久化与下游边界见 [数据取证契约](../../../../docs/data-evidence-contract.md)。在backend运行 `.venv/Scripts/python.exe -m pytest tests/application/test_market_evidence.py -q`；frontend设ROLL_TEST_API_PORT=8027、ROLL_TEST_WEB_PORT=5187、ROLL_BROWSER_CHANNEL=chrome、ROLL_LIVE_MARKET=1后运行 `npx playwright test`（需实际来源可达），生产构建`npm run build`。未设LIVE开关真实取证案例skip，不能将skip说成实际取数通过。

DSA固定ce364e457aab288863a5707e7b3df79786ad07f2、MIT/Copyright2026ZhuLinsen，仅参考Tencent/Eastmoney请求与字段设计，未复制Python实现。具体组件、许可与语义改造在契约登记；不继承补OHLC/零额、全市场报价或qfq缺失退day，不安装无用DSA依赖。

07提供请求/运行、同版本原件/规范化事实/客观观察及真实coverage。08用途新鲜度/可比换源/修订依赖失效，11/12真实生成式后端，13取消与工具安全，14关键复盘独立核验，15按需/盘后客观风险覆盖，以及17/19研究窗口/模型输入门禁仍pending，未先窥封存最终测试。
