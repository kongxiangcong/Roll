# 01 冻结双工作流合同与参考能力映射

Status: ready-for-agent
Completion: complete
Depends on: none
Spec: [v1.0](../spec.md) 第4、8、12节

## 目标与执行条件

冻结双工作流合同与参考能力映射。本票是唯一初始执行入口。
开始前阅读spec与[执行索引](README.md)，将Completion改为in-progress。仅完成本票范围；后票另行按顺序执行。

## 开发范围

- 核对当前源码与已有未提交变更，记录可复用入口和迁移边界，不覆盖无关工作。
- 读取deep-dive-research实际模板、计算器、闸门、测试、许可证，逐文件记录hash与直接复用/适配/仅参考/不采用；Git版本无法确认时如实记录。
- 依domain-modeling技能维护GLOSSARY及适用ADR，区分账户计值、条件估值、共享分析快照、报告版本与核查记录。
- 定稿公司/证券、数据/分析/估值/报告合同及任务状态、错误和版本关系；沿用现有归档/worker/API约定。
- 形成报告十节及估值子章节与原模板质量规则的逐项映射，列明部分交付语义。

## 实施入口

现有 GLOSSARY.md、docs/adr、backend/src/roll/runtime/assistance.py、agents/assistance_runtime.py；deep-dive-research 的 references/02、15、scripts/check_gates.py、fundamental_valuation.py。

## 验收标准

- [x] 合同能表示三类变化、独立核查状态、A+H及两工作流同快照。
- [x] 相容性说明明确不改ADR0005正式资格及旧实验；许可证保留要求明确。
- [x] 每项spec需求可映射到后续票，未支持银行模型等边界可呈现。

## 验证与交付证据

合同缺口与报告模板映射走查；此票不要求实现计算或模型调用。

证据保存于 `../evidence/01/`，至少包含变更摘要、命令与实际结果、复现入口、数据/模型来源、限制及失败记录。没有运行的检查明确记为未运行。完成后回填本票、执行索引及证据链接；Completion只有在验收达到后才能改为complete。

## 范围边界

遵循spec的研究/资格隔离、真实与合成分离、来源与时点约束。不借本票重置旧预算、确认真实成交或输出未经校准概率。外部阻塞记Completion: blocked及原因；未满足依赖不自行跳票。

## Comments

2026-10-26：依据已确认需求创建，尚未实施。



2026-10-26：已冻结合同、术语/ADR、27文件来源/hash/许可快照、94处闸门逐项映射与十节模板。文档走查通过，见[01验收证据](../evidence/01/README.md)；未执行计算/模型/浏览器，不表示整体完成。下一执行入口02。
