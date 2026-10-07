# implement-spec 调用方式核验

核验日期：2026-10-07。仅调研，没有执行实现技能。

## 作者明确说明的使用路线

作者的 [ask-matt 主流程](https://github.com/mattpocock/skills/blob/main/skills/engineering/ask-matt/SKILL.md) 明确给出两种选择：

- `/implement` 逐票执行，每票之间清空上下文；本地任务按依赖人工挑选。
- `/implement-spec` 一次协调整份规格；把关联任务视为依赖图，用子代理并行处理当前可开始的任务，汇总到一个集成分支。

因此，用户过去的 `implement <ticket-path>` 是作者认可的第一条路线；第二条路线是把输入提升到整份规格，无需人工逐票调用。

## 调用语法的证据边界

[implement-spec/SKILL.md](https://github.com/mattpocock/skills/blob/main/skills/engineering/implement-spec/SKILL.md) 要求提供一份规格，其关联任务应描述如何实现该规格；项目的任务跟踪方式也应已配置。该文件没有提供固定参数签名、参数解析器或完整命令示例。因此，`/implement-spec <spec-path>` 是依据技能输入约定得出的实用写法，不应称为作者逐字公布的 CLI 命令格式。

在当前 Codex 使用 `$implement-spec` 选择技能后，可这样提供工作材料（使用示例，并非仓库逐字原文）：

```text
$implement-spec .scratch/roll-p0/spec.md

关联 tickets：.scratch/roll-p0/issues/
请读取规格和全部关联 tickets，按 Blocked by 推进到完成。
使用仓库已经配置的本地 Markdown issue tracker。
```

若规格尚未明确链接 tickets，显式给出目录可以消除关联歧义。已有规格和任务时，无需重新运行 to-spec / to-tickets。

## 执行行为

技能原文要求创建集成分支；每个实现子代理独立分支与 worktree，使用 TDD；实现完成后由合并子代理合入集成分支；依赖解除就启动下一批；全部完成后统一 code-review、修复、按 tracker 规则结项并清理工作树。它不是严格按编号串行执行的循环。

[to-tickets/SKILL.md](https://github.com/mattpocock/skills/blob/main/skills/engineering/to-tickets/SKILL.md) 则负责先生成经过用户确认、具有阻塞边的任务；本地布局正是 `.scratch/<feature-slug>/issues/<NN>-<slug>.md`。文件编号按照依赖排序，但能够同时开始的任务并不因此变成串行。

技能描述表达的是整份规格完成的执行目标，不证明任意环境或外部前置条件下都能无人介入完成，也不包含独立持久化调度服务。
