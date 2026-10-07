# 09 · 账户估值与现金流调整绩效验收

本票范围完成；AT-50 / ACC-15、17、18 的公开事实、页面、重放与真实进程恢复已验收。基于 `76272df` 开始，最终实际合入 `12c9563` 的08来源解析、07档案与既有账户代码；不是全仓累计测试通过声明。上海日期2026-10-08，日志原始UTC时间保留（UTC2026-10-07）；09最终API开始19:08:42.942Z、结束19:09:19.355Z，另Sina消费案例19:18:55.679Z—19:19:00.824Z。

## 公开事实与口径

契约见 [valuation-contract.md](../../../../docs/valuation-contract.md)。POST `/api/account/valuations`、GET `/api/account/valuation-basis`、估值历史/current/按ID查询及POST `/{id}/replay` 使用真实FastAPI、SQLite、07/08归档QUOTE与原件/Parquet哈希，不接受外部估值金额或客户端报价。旧发布版本不可覆盖；双时间、账户/资金原起点与报价知识时点独立保存。保存与期初报价锚点同事务，不重置全局schema版本。

`account-raw-nav-dietz-v1`：Decimal80/金额分舍入。净资产=现金+原价持仓+确认未结收入−确认未结费用/税；冻结现金已包含，不重复扣。费用前FIFO价格损益通过 `Ledger.price_period` 具体只读入口重放，费用、外部流、收入和待结算变化各算一次。总盈亏须同时等于费用前损益+收入−费用+待结算净变化，以及净资产−基线−外部投入+外部撤出。百分比为修正Dietz，按实际现金流时点加权。未知输入、未守恒、零时长或非正分母不会产生确定收益率。

## 输入、预期与实际

以下账户和报价方法案例通过真实应用/SQLite/原件路径，但不代表用户财富或实际市场。`cases/*.json` 保存公开输出与人工预期；代码 [test_valuation.py](../../../../backend/tests/application/test_valuation.py) 保存输入命令与所有assert。金额单位元，实际均与预期一致。

| 案例 | 输入与独立预期 | 实际证据 |
| --- | --- | --- |
| 部分卖出 | 基线100000；买300×10费5，卖100×12费5，余200报价12：费用前已实现200/未实现400，费10，NAV100590/P590 | `cases/cash-flows-and-tax-corrections.json`、API |
| 现金流、收入、待结算 | 再入10000/出4000，分红20、利息10、确认分红100部分结60、确认税10：NAV106710/P710；修正Dietz0.67405063%，利息不增加外部投入 | 同上；公开P与NAV恒等校验 |
| 到账与税费双更正 | 分红到账60→50使实际收入减10/未结增10，NAV不变；税支付10后支付与原应付都更正8，NAV106712/P712、费用18，不重扣、不重复收益；旧版本重放仍原值 | 同上及 `cases/tax-double-restatement.json` |
| 送转与迟补费 | 免费送转300→600，卖200×6；买费暂估10后确认3，另卖费5：gross200+400，费用8，NAV100592/P592 | `cases/free-share-late-fee.json` |
| 配股总额分拆 | 支付501取得100股；费用未知则价格PnL/null，后确认费1后本金500且不再扣现金；卖半数6费5：gross50+50、费用6、NAV100094/P94 | `cases/paid-rights-partial.json` |
| 未知基线 | 导入300股无历史成本/期初报价，现价12.000333…：仍展示NAV103600.10，但基线资产/历史收益/P未知；冻结10000未重复减 | `cases/unknown-opening-history.json` |
| 暂估基线费用 | 买费保守暂估形成投影现金；期初资产与确定NAV/P仍null，不把投影现金冻结为确定资本 | final16 API新增基线案 |
| 原起点知识 | 先确认账户，再取得QUOTE，再确认资金origin：期初资产103600.10、P0；opening quote按origin合法知识取值，不误用账户confirmed_at | API；后取得旧价不能补造原origin已知价格 |
| 10契约消费 | ACCOUNT原授权起点不重置；买300×10费5、现价8：gross−600/fee5，10纯查询剩余额度4395；资金仍PENDING_FACTS、资格UNGRANTED，无授权写入 | API类型化LossFacts消费；25/27真实动作未联验 |
| TRIAL边界 | TRIAL授权仍可查看普通ACCOUNT NAV100000；TRIAL_ACTUAL无真实逐事件归属返回422；10拒绝scope不匹配事实，原TRIALorigin保持不变 | API；不以全账户冒充试用 |
| 05补录/替代 | 追加卖出替代与迟补买入按真实时点FIFO：gross已实现300/未实现600、费用11、P889；旧估值、原事件、旧known_by一致 | API |
| 08来源消费 | Sina原QUOTE经08路径入档后09使用：买300×10费5、当前12，NAV100595/P595；source/run/raw SHA均保留，重放一致 | `cases/08-sina-raw-consumption.json`，独立1案 |

非法应付8但实际支付10且无对应支付更正仍隔离/422，未更改超额结算guard。合法税链10→10→支付更正8→应付更正8先按所选知识截止收束净事实再物化，原事件/回执/旧版本仍10，当前cash99992/pending0/P−8。CSV3同四行一版本真实确认、raw记录10及哈希不变，不新增列或修改旧模板含义。04/05 Comments记录本票真实调用修复。

## 分层检查（相互有重叠，不相加）

| 检查 | 结果 | 原始证据 |
| --- | --- | --- |
| 核心账户/成交/现金/CSV/对账/资金/09与估值OS恢复组合，08合入前 | 124 passed，240.09s | `account-combination.log` / `-metadata.json` |
| 双更正修复定向组合：现金/对账/CSV/09以及对应原生恢复，08合入前 | 76 passed，292.52s | `restatement-combination.log` / `-metadata.json` |
| 新增双税更正原生OS故障 | 3 passed，27.10s | `tax-native.log` / `-metadata.json` |
| 真实08 merge消解后09+SourceResolution接口 | 29 passed，63.46s | 当时终端输出；未保存专用log，不冒称有档案 |
| 合后09公开API最终16案 | 16 passed，34.53s | `post-merge-api.log` / `-metadata.json` |
| 最后新增Sina消费案，未改变产品代码 | 1 passed / 16 deselected，3.31s | `sina-consumer.log` / `-metadata.json` |
| TypeScript/Vite合后构建 | passed，46 modules | `build.log` |
| 09现金流实际Chrome，独立空档案 | 1 passed，11.8s | `post-merge-chrome-cash.{log,json}` / `-metadata.json` |
| 09保全真实旧价实际Chrome，独立复制档案 | 1 passed，9.6s | `post-merge-chrome-real.{log,json}` / `-metadata.json` |
| 05已有路径实际Chrome，独立空档案 | 2 passed，13.5s | `reconcile-isolated-chrome.{log,json}` / `-metadata.json` |
| 其他既有共享路径实际Chrome，独立空档案 | 9 passed / 3 skipped，25.8s | `shared-isolated-chrome.{log,json}` / `-metadata.json` |

估值OS测试通过子进程在版本提交前/后退出，确认重启后不可半发布、期初报价锚点与版本原子保存，账户/资金不变。新增双税OS测试在最后关联更正的提交前/提交后/回执后退出，重启验证版本4或5完整、旧版本3不可改、重试幂等与cash99992守恒。

三项Chrome skip分别是07真实联网、08真实联网、08显式方法factory，本轮未提供它们的专用环境；既有07/08独立证据保留，不声称本轮重验。先前把05与其他改变账户的路径混跑曾得到9 passed/2 failed/1 skipped（`existing-chrome.*`保留）：05独立空账户前提被共享fixture破坏，第二路径缺少第一路径建立的利息。按08 [浏览器验收约定](../../../../docs/browser-acceptance.md)分开运行后上述共享9/05两案均通过，没有降低产品guard。09早期现金页面测试先于异步发布完成读取current曾失败，现等待保存成功提示再查，同步确认不是产品放宽。

最终截图 `valuation-cash-flow.png` / `valuation-real-stale.png`已实际查看：110010/P10与API一致、冻结10000不减；真实旧价135862、期初未知/收益未知与独立时点清楚展示。JSON artifacts核对为各自对应suite，无串写。

## 保全真实旧报价与可复现入口

[real-archive-final.json](real-archive-final.json)记录源45个文件逐个SHA、复制位置与源前后未变，来源为根保全07 `backend/.roll-data/implementation-evidence/07/acceptance-07`，只读复制。09全程没有重新联网取得报价。原腾讯QUOTE SSE:600519=1258.62，upstream `2026-09-30T16:14:58+08:00`、available `2026-10-07T16:19:01.517857+00:00`均保留；合成验收账户现金10000/持100股，当前NAV135862.00、行STALE。origin时尚未取得该价，baseline/P未知；当前读取时间不能把9月30日旧价刷新成新价。是**真实市场原件＋合成账户**，不代表用户实际财富。

本树ignored运行位置：`backend/.roll-data/09-real-final`（最终原件、SQLite、估值及Chrome发布），`backend/.roll-data/09-real-archive`（前一轮独立复制）。[runtime-retention.json](runtime-retention.json)列出当前自有档案字节/SHA；完成交接前不归档删除工作树。测试临时目录不是永久原件。源码版本、公共结果和截图可Git复现；原始运行文件须保留本树或按清单复制保全。

在backend使用 `.venv/Scripts/python.exe -m pytest tests/application/test_valuation.py`；原生恢复分别运行 `tests/recovery/test_valuation_process.py` 与 `tests/recovery/test_tax_restatement_process.py`。复制原件命令为 `.venv/Scripts/python.exe tests/adapters/valuation_real_archive.py --source <保全07目录> --data <新隔离目录> --output <结果JSON>`。frontend使用 `ROLL_BROWSER_CHANNEL=chrome`、`ROLL_TEST_API_PORT=8029`、`ROLL_TEST_WEB_PORT=5189`，`npx playwright test valuation.spec.ts --grep 'saved cash-flow'`跑空目录现金路径；真实路径另设 `ROLL_TEST_DATA_DIR=<新复制目录>`、使用 --grep 'preserved real September'。精确test标题以源码为准；两种不能共用同一个账户fixture。

## 验收边界

09当前票全部criteria完成，正式资金/资格保持原规则：PENDING_FACTS/UNGRANTED、剩余额度不由09页面代填。25/27真实动作预算/暂停、26真实试用事件subset、08按调用用途消费新鲜度与14独立验证仍须各票实际联验，保持PARTIAL；不将10纯类型/公式消费证明冒充这些正式链路。研究费用预算未增加。
