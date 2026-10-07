# 05 · 补录更正、范围声明与逐项对账

Completion: complete。分诊仍为 ready-for-agent。本票实际验收日期2026-10-08（Asia/Shanghai）；最终账户验收实际开始/完成时点见 [run](final-account-run.json)，Chrome实际开始/完成及环境见 [environment](environment.json)。数据均为合成个人账户凭证，验证真实FastAPI/SQLite/原件/OS进程/Chrome行为，未连接真实券商账户。

## 来源与测试边界

基于已实际合并04 `ada6cfb`，先完成账户切片，再合入07真实集成 `1159dc71b610d15c17fd7d889f08c98978f0bc40`。保留07市场事实/raw/Parquet/来源接口、06列表版本历史、03原件与批次确认及04已付配股/费用口径。唯一确认事务仍负责版本、事件、回执、审计及处理材料状态；无新数据库迁移/版本重置，运行数据在隔离外置目录。

- 合07前完整后端：**140 passed**，470.24s，含全部旧恢复/升级及真实HTTP进程的30持仓、142事件、100次确认P95≤2000ms门槛，[日志](backend-full.log)。这是门槛通过证据，不声称新增外部检索/模型并行性能已联验。
- 合07后的影响范围：全部application API + 05六个原生故障 + 实际v1/v2旧服务升级，**138 passed**，294.88s，[日志](after-market-integration.log)。不是同一完整套件重复计数。
- 用途缺口细分/实际费用替代及v2真实升级补验：**13 passed**，32.64s，[日志](final-api-tests.log)。包含12个05公开API用例及1个v2 OS升级；与上述结果重叠，不相加。
- 最终资金原快照日期修正后的账户/成交/现金/CSV/05及实际v1/v2升级：**73 passed**，143.93s，[日志](final-account-tests.log)。新增公开证明权限12点确认后再录13点成交，冻结/可取日期仍为原10点，未知券商可用日期仍null；不重复相加。
- 05最终真实Chrome：**2 passed**，13.4s，[结果](browser-results.json)、[日志](browser.log)。①范围声明→追加利息替代→券商数量差异确认→未知可卖待核→旧发布版本/双时间查回；②CSV v3三种05事实整批一个回执。
- 合并后的既有Chrome：**9 passed / 1 explicitly skipped**，24.8s，[日志](integrated-browser.log)。覆盖基线/权限历史、现金/权益、paid rights、旧CSV v2三种流程、成交费用、资金门禁及有限市场名单。07实时外部来源测试须显式ROLL_LIVE_MARKET=1，本轮未重复网络验收；该票实际来源证据保留在07目录。
- `npm run build`：类型检查及Vite **44 modules**通过，[日志](build.log)。Starlette/httpx弃用提示是已存在的一项warning，不算失败。

## 输入、期望与实际

| 公开路径 / 输入 | 期望 | 实际 |
| --- | --- | --- |
| AT-12：基线100000；12点买100×10费5，13点卖100×12费5；晚补11点买100×5费5 | 当前按实际时点重建FIFO，旧确认/旧known_by保留 | 旧v3现金100190/已实现190；新当前现金99685/剩余成本1005/已实现690；旧v3及回执逐项相同 |
| 同一实际12:30，旧known_by与当前known_by | 展示当时所知及事后修订两种事实 | 旧现金98995/100股；新现金98490/200股；当前事实截至13点，最近输入11点，系统获知为新回执时点；券商可用仍99000且截至13点，不倒退为11点99495 |
| 原买入价格10→替代8→替代9；旧链末端再写；随后先冲正卖出再冲正买入 | 原事件/原因/回执追加留存；旧目标拒绝；依赖顺序重建 | 现金100390/实现390→100290；旧目标QUARANTINED；最终现金100000、无持仓；完整replay一致；旧v3不变 |
| 部分分红：确认应收100、结60→完整替代结40；paid rights总支付501→替代601，费用1 | 未结与实际到账不重计；已付配股按替代事实重建 | 实际收入40/未结60；配股取得成本601，原501凭证仍可查；声明也可追加完整替代 |
| AT-13：新增风险用途要求13点；只声明CASH14点，再声明四范围14点；用途改成15点 | 根据本次用途与范围判断，不补每日打卡 | STALE_DECLARATION缺成交/委托/权益→CONFIRMED_AS_OF→STALE_DECLARATION；无现金/数量变化，独立市场观察始终allowed |
| AT-14：镜像100股，券商120股、可卖null；明确确认快照现金99000对原98995 | 预览不判断谁正确，确认对齐有据当前值，历史缺口不编收益/成本 | 预览原100不变、差异+20；确认120/可卖null/成本null，现金对齐+5单列UNEXPLAINED_ALIGNMENT，投资收入不增加；Today/查询均RECONCILE_REQUIRED，减仓quantity=null |
| 利息漏记／部分分红／税费更正：应收100结40、税10；券商现金100052、收入60、费用8、未结60 | 分列差异，先追加有凭证事实；不能猜补或重复记应收收入 | 首稿差额现金+22/收入+20/税费−2；追加利息20与税更正8后最终v7现金100052、实际收入60、费用8、未结60；旧v4与原稿不变，旧稿RESOLVED可查 |
| 仅现金利息金额未知，数量/可卖已知并声明成交/委托/权益；随后有未知成交 | 总体待核仍可给独立降风险政策所需事实；不能永久因无关现金缺口全局禁用；未决数量仍受限 | 总体RECONCILE_REQUIRED但REDUCTION fact_scope_state=CONFIRMED_AS_OF/allowed=true；NEW_RISK仍false；新增未决FILL后REDUCTION false，始终executable_quantity=null |
| 成交费用PROVISIONAL，券商核实300股/可卖300；其后可卖改为未知 | 费用待核不替代降风险政策资格；可卖未知必须受限 | 已核对数量及范围时保留REDUCTION事实核对；未决数量材料及可卖null后fact_scope_state=RECONCILE_REQUIRED且allowed=false |
| v3真实文件：替代利息10→20、匹配快照、四范围声明 | 全批一个版本/回执，原字节与链身份可查；旧模板含义不变 | v2→v3，三个事件共用回执，现金/收入为100020/20；v2输入05新kind隔离；浏览器另一真实v3批次20→25共用三事实回执 |
| 部分卖出后实际成交费用6→完整替代2 | 重建已卖/剩余费用分摊，不二次扣支付，原费用回执保留 | 旧v4现金99589/实现92；替代后现金99593/实现94/剩余成本501；原事件实际费用6不变，当前费用2，replay一致 |
| 原04 v2实际服务在ada6cfb生成带空格record_id的paid-rights CSV草稿，停进程升级05 | 原文件/草稿不变，冻结v2仍按原含义确认 | 原字节与草稿完全相同；v2确认现金99499/取得成本501；canonical lot_id v2-rights、费用分拆待核，schema未重置 |
| 并发两个当前末端替代；同键重试 | 同链一胜一冲突、不双写；旧known_by可查 | 200/409；一版本推进，事件总数4；重复同键返回同回执；旧known_by现金100010；基线前替代QUARANTINED并保留原命令 |
| CORRECTION/RECONCILIATION各3个实际OS故障点 | 未提交全回滚；提交后/回执后重启一次恢复，材料状态与事实同事务 | before_commit保持v2且材料QUARANTINED；after_commit/after_receipt保持v3且RECON引用材料RESOLVED；重试原回执、现金100020、replay一致，旧v2与原材料逐项保留 |

附加费用样例曾因测试辅助函数参数顺序错误而未生成v4，红日志单独保留在[fee-fixture-red.log](fee-fixture-red.log)；使用明确amount/target参数后通过。未知数量对账材料不能被无关现金/费用的减仓事实路径忽略：该公开用例先红，再修正材料分类，最终13与73组合通过。

公开用例及可复现输入：[test_reconcile.py](../../../../backend/tests/application/test_reconcile.py)、[test_reconcile_process.py](../../../../backend/tests/recovery/test_reconcile_process.py)、[v2实际升级](../../../../backend/tests/recovery/test_csv_v2_upgrade.py)、[Chrome脚本](../../../../frontend/tests/e2e/reconcile.spec.ts)。服务/模板字段与用途边界见 [契约](../../../../docs/reconciliation-contract.md)。

## 关键页面

[范围声明](declaration-preview.png) · [分列差异](reconcile-differences.png) · [未知可卖待核](reconcile-unknown-today.png) · [旧版本及双时间](reconcile-old-history.png) · [v3整批预览](reconcile-csv-v3-preview.png) · [同回执查询](reconcile-csv-v3-receipt.png)。真实Chrome截图经目视核对，内容完整且无横向截断。

TDD中先观察不支持v3的失败，再实现复用确认；现金缺口错误地全局阻止REDUCTION的公开用例先红后绿。首次合并浏览器中共享基线为当天、CSV却为昨日，受正确的“基线前无法重建”保护而失败；调整合成共享基线早于后续实际输入后9条既有流程通过，没有放宽产品保护。权限事件确认元数据与04金额更正按原事项有效时点重建的初期回归问题已修，合07前完整140与合后组合均验证。

## 明确保留的后续联合边界

26/27真实动作尚不存在，**旧动作在确认事务中失效联验仍PARTIAL**，只已提供账户版本/原子回执语义，不用替身宣称完成。REDUCTION allowed仅是账户事实子检查，22/25还须独立政策资格、用户授权与实际可行性；05没有生成减仓/退出动作。09对修订后估值、收益、应收应付呈现仍待真实调用方联合验收；08/13外部检索或模型等待期间的确认延迟仍待实际联验。独立市场资料不因账户声明不足被禁用。上述边界不阻止本票已授权且独立可验的全部标准完成。
