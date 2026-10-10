# 04 现金与权益验收

验收日期：2026-10-08（Asia/Shanghai）。实施分支 `codex/roll-p0-04`；最终组合代码已合真实03 `1e09bb4`、父集成文档 `af59b42`。账户唯一写入口、真实SQLite、隔离运行数据与已批准测试接缝沿用01/02，不调用行情/模型或券商自动确认。

## 实际检查

- [账户/成交/现金权益/CSV与全部恢复检查](account-cash-fill-csv-tests.txt)：78 passed，264.89s。包含单条现金结算三个OS故障点、两版CSV故障恢复、旧版实际进程升级、版本/幂等/失败原子性和原件指纹。开始00:36:56，结束约00:41:21（进程开始记录＋日志时长）。
- 截图人工检查发现另一只初始持仓无已知成本时被空批次合计成0；公开API先复现红，再最小修复。[修复后现金权益与成交成本回归](final-cost-regression.txt)：26 passed（14现金权益＋12成交），44.44s。包含一个新边界用例；不能把26与78直接相加当作一次全套结果。
- [实际Chrome受影响路径](browser-tests.txt)、[浏览器结构化结果](browser-results.json)：7 passed，21.5s；[构建](build.txt)：41模块、TypeScript通过。端口API8024/web5184，实际系统Chrome channel chrome，独立临时ROLL_DATA_DIR。覆盖基线、成交、应收/部分结算/更正、实际配股及晚费用分拆、两版CSV与v2配股。
- [真实HTTP确认性能](confirmation-performance.json)：100次确认、10次预热、30持仓/142事件，P95=57.1205ms（nearest rank），门槛2000ms。该性能样例仍是成交确认，08/13真实外部任务延迟联验保持pending，不冒充本票配股性能数据。

继承03已有117项后端/7条Chrome验收见[03证据](../03/acceptance.md)。本轮以受影响范围回归，不重复声明一次全仓全套。FastAPI/Starlette使用httpx的一条已知deprecation warning不影响结果；Chrome颜色环境warning亦不影响结果。

复现：工作树根运行 `backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/application/test_account.py backend/tests/application/test_fills.py backend/tests/application/test_cash_events.py backend/tests/application/test_csv_import.py backend/tests/recovery -q`；最终成本修复回归仅运行test_cash_events.py及test_fills.py。浏览器在frontend目录设置ROLL_TEST_API_PORT=8024、ROLL_TEST_WEB_PORT=5184、ROLL_BROWSER_CHANNEL=chrome后运行 `npm run test:e2e -- tests/e2e/baseline.spec.ts tests/e2e/fills.spec.ts tests/e2e/cash-equity.spec.ts tests/e2e/csv.spec.ts`，再 `npm run build`。已安装锁定依赖；数据由测试临时目录提供。浏览器精确开始/结束与验收记录时点保存在environment.json及browser-results.json。

## 输入、字面预期与实际

全部输入为测试内合成个人账户凭证，实际通过公共FastAPI保存真实SQLite并查询事件、回执、历史版本和replay。字面预期独立写于断言；下列实际与预期一致。

CSV配股截图使用先前浏览器用例的共同账户（确认前98760.10→98260.09），而下表CSV API是独立100000.10基线（→99500.09）；两者都只扣实际总支付500.01，不能混用各自初始账户值。

| 场景/原始依据 | 输入与字面预期/实际 | 证据 |
|---|---|---|
| AT-10，利息与追加存款 | 初始100000＋利息20＋存款5000→现金105020；investment_income=20、external_cash_in=5000，存款不提高收入 | test_interest_and_deposit…；CSV外入/利息页面 |
| AT-11/84，公告及网页宣称已分红 | example.invalid来源、仅日期宣告原文→保存learned_at/宣告日期原精度/actual_effective_at=null；账户版本、现金、持仓完全不变 | test_web_claim…；equity-hints公开查询 |
| 原个人应收凭证与实际部分到账 | 应收100不改现金/可用；到账40→现金100040、未结60、实际收入40；余60到账→100100、未结0、收入100；重复确认同回执 | test_confirmed_receivable…；[部分到账截图](cash-partial.png) |
| 应付税款、部分扣款与追加纠错 | 应付30、付10、应付更正25、原扣款更正8、再付17→现金99975、实际费用25、未结0；原30/10记录仍在 | test_payable_partial…；[历史截图](cash-history.png) |
| 现金六类别与连续更正 | 出50、分红12.34、费2、税3.21、入0.01、分红更正15再14→99958.80；收入14/费用5.21/外入.01/外出50；原12.34和前次更正关系可查 | test_all_cash_categories… |
| 送转、部分卖出与后补费 | 买300×10预留10，卖100×12费5，余股送转300，卖100×8费5，补原费5→现金98985，剩余200股/成本1335.55、已实现320.55；原买300不改 | test_share_change_carries… |
| 连续送转与多批最高精度 | 两次送转/间隔部分卖出后补费→现金97985、剩余200股成本2003.34、已实现-11.66；两批8位数量余数150.00000001＋150.00000000、成本105＋105守恒；最大参考乘积999999999999999999999999980000000000.00仍为参考而非已知取得成本 | 三个precision/transfer公开API用例 |
| PRD4.2实际配股，费用分拆未知 | 买300股总成本3005；新增100股总支付500、fee_amount=null→现金96495、400股、成本3505、费用前本金未知；补实际费5→现金/成本不变，本金495，原null保留 | test_paid_rights…；[配股预览](rights-preview.png)、[配股历史](rights-history.png) |
| v2真实配股CSV整批 | 初始100000.10/300股；新增100.00000001股支付500.01＋同批后补费用5.01→99500.09/400.00000001股，本金495；一版本/两事件/一回执/原件可读；v1拒绝新kind | test_csv_v2_paid_rights…；[CSV配股预览](csv-rights-preview.png) |
| 关联ID首尾空白 | 原草稿目标` pending-1 `保留；个人应收100→带空白目标到账60→现金100060/未结40，后续50隔离；更正后未结30。配股ID/费用目标/子lot身份统一trim，raw不改，replay一致 | test_identifier_whitespace… |
| 无lot的另一只初始持仓 | 初始300股取得成本未知；新增另一只配股100股/支付500→原持仓acquisition_cost仍null，新增成本500；replay一致，页面显示未知 | test_rights_in_another_security…；人工重查rights-preview |
| 原材料未知/失败/并发 | 超结算、降低应收到已结以下、负现金、未知税、float费用、未知数量→原草稿隔离、现金100040/未结60/版本3不变；四并发确认仅一次，旧版409 | test_cash_failures…；test_cash_confirmation… |
| 实际OS退出/重启 | 单条分红部分结算及v2配股＋费分拆在before_commit/after_commit/after_receipt三点各运行真实服务。重启重试后各只入一次；配股现金99499.99/100.00000001股/成本500.01/本金495/原费null/原件与回执一致 | test_cash_process（3），test_csv_process RIGHTS（3）；78项日志 |

## 结项范围与后续入口

04支持独立现金到账/扣款、外部资金、已确认应收/应付、部分/全结算、追加金额更正、免费数量调整、实际配股付款/新增批次与费用分拆。所有正式事实经同一prepare/confirm事务。字段/时点/成本/费用口径见[现金权益契约](../../../../docs/cash-equity-contract.md)与[CSV契约](../../../../docs/csv-contract.md)。新增组件表只幂等创建equity-hints，保持全局user_version2及旧账户数据；v1 CSV头/允许事件冻结，v2复用既有quantity/amount/fee_amount。

本票未交付05全账户对账及一般纠错、09估值/NAV/百分比绩效，也未抓取真实外部网页。05使用cash_resolutions及关联待结余额；09/10消费配股已付总成本、本金/费用分拆及lot lineage，不能将fee-inclusive成本再扣一次费用，未知分拆保持费用前结果未知。07/14接入真实网页后复验AT-11/84材料边界；因此ACC-07跨票整体仍PARTIAL。正式资金状态/技术资格/模型Runtime保持各自票边界，CSV/线索不会增加授权。
