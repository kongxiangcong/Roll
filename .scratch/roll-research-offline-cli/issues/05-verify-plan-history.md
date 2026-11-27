# 05: 在 M0a 副本核验研究发布与计划历史

**What to build:** 研究者在同一份验收库副本上贯通缺证、补证、重试和发布，核实每个阶段的交易计划读取了哪个档案版本。

**Blocked by:** 03, 04

**Status:** ready-for-agent

Resolution: completed

Closed: 2026-11-26

- [x] 从 M0a 副本记录原冻结计划 ID、内容及预览基线。固定账户、行情快照和同一截止时点，经过缺证、补证、生成 A 和重试生成 B 后，roll plan --preview 与基线逐字段相同。
- [x] 按 A 的回执审阅发布，安排与旧档案有效期衔接的时间。用正式 CLI 分别在 A 生效前和有效期内预览，计划依次引用旧档案和 A；同时确认 B、两次尝试和父子清单均可按 ID 重读。
- [x] 按原计划 ID 离线重读，完整结果与首次归档逐字段一致。记录可复核的任务、尝试、版本、快照、时点、计划 ID 和比对结果，写入仅使用副本。

## Comments

2026-11-26 通过 SQLite backup 从只读 M0a 原库取得副本。每次调用均启动独立的正式 `roll --data-dir /tmp/roll05-history-c6jfigzu` 进程，由 Python socket 审计钩子禁止建立网络连接、域名解析和数据报发送。该临时目录保留库及每步完整 JSON 回执。以下 JSON 摘要使用 UTF-8、按键排序、紧凑分隔符及非 ASCII 原文计算 SHA-256。

**冻结计划和预览。** 账本 `m0a-example`，标的 `600362.SH`。先按计划 ID `65a4dae479fd3278cb52250927c91ef8daa835f2348aad2a4d7a1232558be9ab` 重读，存为 `archived.json`，与 `.roll-data/v3-acceptance/structured-plan-refresh.json` 中的 `previous_frozen_plan` 整体相等，档案为 `2026q3-cashflow`。预览使用 LIVE_RUN 快照 `b6cac86c682fbe7d9cfeadbe65553567419472da29fd96304dfa7b55b228ce22`、截止 `2026-11-26T07:38:52.909461Z`、账户快照 `a3a733d7f33fd4d9d7ffb052a95e9470dbdf98f080309642416180a257963d65`，引用 `2026q3-buyback`。缺证、补证取得 A、重试取得 B 后分别与 `baseline.json` 比较完整预览，三次均相等，摘要均为 `e7ec140236d6b846bf73095e713a8a4f9f01b7c7c0747f783fb088f63b96867c`。

**任务与输入。** 研究使用重建快照 `a67c1c43cf4f284460ed6e987f8fd1a8a2f4e9f1720d9a431efe993901167bcb`，截止与基线相同。核对三季报第 12 页经营活动现金流量净额及其来源。父任务未收到可定位摘录，补证取自 M0a 观测 15053，合并现金流量表年初至报告期末净额为 14,162,724,945 元。摘录取得于 `2026-11-26T07:34:09.393912Z`，内容 SHA-256 为 `4b7e6ceac5fab04a765125c735815e4e69fd5c05ec1c8aa8198920c3d4f0e716`。[江西铜业 2026 年第三季度报告，第 12 页](https://static.cninfo.com.cn/finalpage/2026-10-29/1225636802.PDF#page=12)

| 任务 | 尝试 ID | 按回执复读的结果 |
| --- | --- | --- |
| 父 `task-cae7002bed8b47fbb213161ca2b1e91f` | `attempt-703a60825d0148888ac20c4690f799c0` | 缺三季报原文或可定位摘录，阻塞 |
| 子 `task-9f39f5750954442f98fb84e5dd565751` | `attempt-4d6216ba71e34f1f851acc44c2bfc54f` | A，版本同尝试 ID。正文引用新增摘录，记录缺少部分日期行业对照的局限 |
| 同一子任务 | `attempt-40b45ab67c0b4216ba90ed94e35fda3e` | B，版本同尝试 ID，独立草稿 |

父清单 `e3add19e053f701b7079f840fa9ca02c3f2be2e9d986cf1fc581ca4efa35966b` 不含提交公告；子清单 `a64b26094eb18fd1c1bde66a472b1fe385d1364ccf81592485c3f7bdab067c5a` 含该摘录。发布后按三个尝试 ID 重读，逐字段等于对应回执。父任务整体重读一致，子任务清单、父引用均一致，尝试列表恰为 A、B。

**发布及计划回放。** 显式按版本审阅 A 后，由“研究者”于 `2026-11-26T12:56:12.848521Z` 发布。A 生效于 `2026-12-04T00:00:00+08:00`，恰逢旧档案到期，截至 `2026-12-26T07:38:52.909461Z` 有效。发布版本的任务及尝试均指向 A 回执。B 的草稿与发布前逐字段相等，按 B 查询发布版本为空。

| 计划截止（上海） | 同一 LIVE_RUN 快照下的账户快照 | 计划引用 / 研究状态 |
| --- | --- | --- |
| 12-03 15:30 | `9fda128608b88492d98f5d806c585ca133570893871f38554517d4067d7356c3` | `2026q3-buyback` / active |
| 12-04 15:30 | `1d5811ac7e5e2376afa1385d0a618529868b4b7b0ebff979d147de0518a277be` | A / active |

最后通过 `plan --plan-id` 再读原计划，全字段与初次归档一致，摘要均为 `4a239d00321325854db24c664c9fb339ff951470d664e594ea3c5e808d154f5d`。干净检出可用临时账本重跑 `backend/tests/test_v3_research_tasks.py::test_plan_history_uses_only_the_reviewed_effective_attempt`。
