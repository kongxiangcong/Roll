# 01: 断网发起研究并重读阻塞性缺口

**What to build:** 研究者通过 roll research task run 提问，拿到缺证回执，重启后仍能查到当时用了哪些公开材料、还缺什么。

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

Resolution: completed

Closed: 2026-11-26

- [x] 在 M0a 验收库副本用 600362.SH、指定行情快照、截止时点及一个需要额外公告的问题运行正式 CLI。回执含任务与尝试 ID、阻塞原因和所需证据，无可发布草稿。
- [x] 按 ID 重读问题、标的、用途、截止时点、行情快照、公开输入的内容或不可变引用及指纹，以及该次缺口。再次运行读取命令得到相同内容。
- [x] CLI 支持本地公开文件和摘录，两种形式均要求标题、来源、定位、URL 或文档标识、实际取得时间。验证输入后修改原文件，仍可离线核对当次材料。截止后取得的公告不能用来填补该问题的缺口。
- [x] 未建档股票也可建立任务并登记用户材料。用带私有标记的账户数据验证执行桩可见输入仅含本次获准的公开材料。

## Comments

在 M0a 验收库的 SQLite 备份上用正式 CLI 核对江西铜业经营现金流同比变动原因。行情快照为 `a67c1c43cf4f284460ed6e987f8fd1a8a2f4e9f1720d9a431efe993901167bcb`，截止时点为 `2026-11-26T06:35:00.566787+00:00`，使用档案 `2026q3-cashflow`。任务 `task-b230c567e56d425b87ee846ee5a43e3b`、尝试 `attempt-674cf2ae026c4c5694646c91496416f8` 记录所缺的「经营现金流变动说明公告」，结果为 `blocked`。独立进程按 ID 重读清单及缺口相同，冻结行情引用为 `market-research:ee42a6b54859024ae1f2afd46c128dfcc5043cbb85ef92b8cc9dae61add63902`。

`research task run` 可重复指定 `--require 公告标题` 和 `--material 描述文件.json`。每份 JSON 提供 `title`、`source`、`locator`、`url` 或 `document_id`、`received_at`，以及 `excerpt` 或 `file`（相对路径从描述文件所在目录解析）。`research task show 任务ID` 读取清单及尝试，`research task attempt 尝试ID` 读取该次回执。自动化验收覆盖截止后材料、缺失元数据、二进制文件替换后复核、未建档研究及含私有标记的账户隔离。
