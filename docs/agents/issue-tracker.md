# Issue tracker: Local Markdown

本项目的规格与任务使用 `.scratch/` 下的 Markdown 文件管理。

## 文件约定

- 每个功能使用一个目录：`.scratch/<feature>/`。
- 规格保存在 `.scratch/<feature>/spec.md`。
- 每个任务独立保存为 `.scratch/<feature>/issues/<NN>-<slug>.md`，
  从 `01` 开始编号。
- 分诊状态在任务文件顶部附近用 `Status:` 记录，
  标签映射见 `triage-labels.md`。
- 评论与讨论追加到文件末尾的 `## Comments` 下。

## 发布规格或任务

发布规格时创建或更新 `spec.md`。
发布实施任务时，在 `issues/` 下为每个任务创建独立文件。

## 读取任务

读取用户指定的文件路径。
用户仅提供编号时，在对应功能的 `issues/` 目录查找；
编号存在歧义时，先明确所属功能。

## Wayfinding

供 wayfinder 工作流使用：

- Map：`.scratch/<effort>/map.md`，
  包含 Notes、Decisions-so-far、Fog。
- 子任务：`.scratch/<effort>/issues/<NN>-<slug>.md`，
  从 `01` 编号，正文记录待回答的问题。
- 类型：顶部用 `Type:` 记录
  `research`、`prototype`、`grilling` 或 `task`。
- 状态：顶部用 `Status:` 记录 `open`、`claimed` 或 `resolved`。
- 依赖：顶部用 `Blocked by: NN, NN` 记录阻塞任务；
  所有依赖均为 `resolved` 时，任务解除阻塞。
- 选择任务：按编号选择第一个 open、无阻塞且尚未认领的任务。
- 认领：开始工作前，将状态改为 `claimed` 并保存。
- 完成：在 `## Answer` 下追加结果，将状态改为 `resolved`，
  并在 map 的 Decisions-so-far 中追加摘要与文件链接。

Wayfinding 状态用于其子任务生命周期；
普通实施任务的分诊状态遵循 `triage-labels.md`。
