# Final31 current-day no-trade flow appendix r02

有限调用方验收已通过；普通观察任务的业务结果仍是 **PARTIAL**。这是对旧五入口流程遗漏的当前日无交易声明→ON_DEMAND / POST_CLOSE UI/API 路径的补充，不重复三P95、两条15测试、安装或许可验收。

起点：root `aaf1929`，自有 branch `codex/roll-p0-ticket31-final` merge `3dcd7bc59748da89000912b0cd582656d7fcc9ba`。仅新增本目录 harness / 原始回执 / 图片 / 字节保护与保全资料；`backend/src` / `frontend/src` 产品修改为0。根 status、trace、README、plan、票Completion及manual239由协调者拥有，本次未改。

## 字面行为和时点

真实主机上海时钟为 **2026-10-11 周日 23:09:40—23:10:18 +08:00**，没有跨10/12、调整时钟、假装工作日或指定旧观察cutoff。来源 `run-20261011-230939/flow-receipt.json` 与 `browser/browser-receipt.json`。PRD BR-06 / MON-01/02/10/12 / UI-01/04 / AT-48及31原计划要求普通无交易流程、保留实际时间线、允许非交易日同步及普通回看，不需要选择模型或阅读投研报告。

1. 新建独立 METHOD_ENGINEERING 现金账户，10000.00元，无持仓、无成交、无未决委托。UI当前分钟基线→差异→确认→回执查询，随后全四范围（成交、委托、资金、权益）`changes=NONE` 的范围声明，截止 **23:10:00**，记录推进账户版本1→2；资金/持仓逐项不变。账户分析 use-check 在该声明**显示的分钟**返回 `CONFIRMED_AS_OF / allowed=true`、缺范围[]。这只覆盖显示的截止，不声称用户真实券商账户已核验，也不把稍后秒级请求反推为声明已覆盖。
2. 今天入口普通“按需观察”实际请求 **23:10:03.891614**，`ON_DEMAND`任务发布 `PARTIAL`：日历 `SSE-2026/CLOSED/WEEKEND/is_trading_day=false`，账户版本2，8条QUOTE/DAILY缺口，4个本次可适用固定指数的未知事实。没有持仓/关注源采集，未勾“补查缺失事实”。系统可得截止与本次实际观察时点相同，UI显示时点和缺数，不转成买卖判断。
3. 当前产品服务端和UI明确允许 `CLOSED` 触发普通“盘后复盘”。实际 **23:10:04.917541** 提交 `POST_CLOSE`，同样发布 `PARTIAL`，`previous_snapshot_id`连接前一观察、`NO_SUBSTANTIAL_CHANGE`。这支持**当前休市日普通复盘**；不证明交易日当日日线齐备、15:30/18:00自动触发、冻结影子检查点、盘中覆盖或整天市场数据。
4. 对两次已保存观察分别用原始精确cutoff / mode / refresh=false重复提交，`task_id`不变；历史时间线只有2条，无额外任务。两次immutable replay均network_calls=0且结果逐项相同。观察后账户与声明后账户完全相同。没有要求读投研报告或挑选模型。
5. `forecast=null`、`forward_sample_created=false`、formal_judgment=DISABLED、formal_capabilities=[]、grants=[]；没有任何实际资格。通知原始审计字面 `business_notifications=3 / merged_sources=1 / transmission_attempts=0 / delivery_status=UNKNOWN`。这些是站内账户核对/运行摘要记录与合并，不能报告“无通知记录”，也不能把合并计数当外部重复送达；用户外部渠道未配置，未执行发送。

真实业务任务的PARTIAL和工程路径的PASS分别记录。没有完整交易日/完整行情/研究资格证明；AT-48的当前普通无交易路径切片得到补足，真实用户账户核对与交易日完整日常流程仍须按其实际条件另验。

## 受控边界、失败和进程

`offline_app.py`仅使用当前同一产品，真实默认时钟、IN_PROCESS工程worker、新自有数据库；HTTP市场/通知transport若调用即记录并拒绝，Codex/baostock worker显式指向未存在的owned DISABLED文件，不连真实provider。不生成METHOD grant或新的实际技术ReviewRecord，不fit/forecast/SEALED/source采集；检查站内记录允许，外部发送不允许。成功run外部attempt日志不存在、retrieval_runs=[]、module_errors=[]。这是有限受控工程流程，不替代此前已验收三独立生产进程。

首次 `run-20261011-230801` 保留 **FAIL**：调用方 exact getByLabel('本次用途')无法定位含选项控件、30秒超时，声明/观察尚未提交。仅改 harness 为 combobox 的当前名称定位，并在第二个全新 profile 完成上述路径，没有改产品。两个run原始API响应、browser.log、服务日志、receipt及失败profile均保留；没有筛掉失败或重跑旧基准。

每个run均仅启动本轮API/工程worker宿主和Vite，记录launcher及真实host PID / CreationDate / ExecutablePath / CommandLine，CTRL_BREAK请求后逐PID CIM为空，无taskkill fallback。浏览器关闭后服务和worker仍在。原始receipt的stop标签沿用旧helper `CTRL_BREAK_NORMAL`，但**不能解释成全零正常退出**：API完成 shutdown 日志、宿主退出码3；Vite被CTRL_BREAK终止、退出码3221225786。停止证据仅证明本轮owner进程全部停止，未终止任何原有进程。

## 字节保护和保全

`guard-before.json` 与 `guard-final.json` 字节相同：当前产品源码清单、保护15、许可3旧数值文件、原19SQLite165814272字节/SHA一致。仅字节读原19，不连接原SQLite；guard里的076e是最初已接受产品绑定，当前run真实source_oid在receipt为3dcd7bc。没有读取凭据或源/SEALED数据。安装/组件静态未重复，因为仅新增证据/脚本。

只保全本轮两个fresh runtime，目标 **D:\dsh-proj\Roll\.roll-data\implementation-evidence\31-flow-r02**，64文件6689112字节，SHA/长度源与目标全匹配，12次确切PID停止再核查，private排除0/reparse0。`runtime-union-manifest.json`含source_tree、source_roots、目标、path及每条绝对source/destination/bytes/sha256映射；manifest43831字节，SHA `a5cd19228c96ccdb80e70f00fe41762ced73f9165530aca941c7a5a7ac85b3f6`。`runtime-preservation-summary.json`给出元数据。不涉及旧 frontend/test-results，不覆盖旧union任何映射。

旧r01的根及自有manifest只核已知文件字节，均保持178259字节/SHA `ca3331799dbf8ffcf298e45d0c2fe076ac94a939361a000cf378dfe91252ba7d`；见 `previous-r01-byte-check.json`，未重复旧runtime sweep。新appendix供独立21只读检查后，由协调者合入与逐条手工对账；此文不自动更改任何Completion或manual239结论。

End comment：本轮闭合当前日无变化声明→普通按需观察→合法休市复盘→历史/幂等/回放切片，保留8项事实缺口与formal未启用，首次harness失败和两个profile完整保全，产品修改0、无外发/真实provider/新资格/前向样本。
