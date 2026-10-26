# 09 实现Markdown/PDF交付与版本恢复

Status: ready-for-agent
Completion: not-started
Depends on: 08
Spec: [v1.0](../spec.md) 第4、8、9节

## 目标与执行条件

实现Markdown/PDF交付与版本恢复。必须先验收[前票](./08-report-template-and-pipeline.md)，不得跳过依赖。
开始前阅读spec与[执行索引](README.md)，将Completion改为in-progress。仅完成本票范围；后票另行按顺序执行。

## 开发范围

- 复用/适配原Markdown到PDF能力，保存Markdown、PDF、引用索引、估值输入输出与发布manifest。
- 实现历史版本、受控下载及安全渲染；文件路径/HTML脚本/来源指令不得执行。
- 归档文件和共享引用纳入现有备份恢复，损坏引用可诊断；原文可离线读取。
- 报告重生成形成新版本，旧文件保持不变；渲染失败不丢Markdown和分析结果。

## 实施入口

deep-dive-research/scripts/md_to_pdf.py、Roll备份/文件归档/API。

## 验收标准

- [ ] PDF目录、中文字体、分页、表格和图表可读，无截断乱码，引用/估值条件和缺口未丢失。
- [ ] A2/A10文件层通过：新版本不改旧文件，隔离备份恢复后hash匹配。
- [ ] 下载不能越界读取其他文件；渲染失败可重试且状态明确。

## 验证与交付证据

使用pdf技能做实际页面渲染和视觉检查；加入中文长表、缺图、长URL和失败恢复场景，保留验证页截图。

证据保存于 `../evidence/09/`，至少包含变更摘要、命令与实际结果、复现入口、数据/模型来源、限制及失败记录。没有运行的检查明确记为未运行。完成后回填本票、执行索引及证据链接；Completion只有在验收达到后才能改为complete。

## 范围边界

遵循spec的研究/资格隔离、真实与合成分离、来源与时点约束。不借本票重置旧预算、确认真实成交或输出未经校准概率。外部阻塞记Completion: blocked及原因；未满足依赖不自行跳票。

## Comments

2026-10-26：依据已确认需求创建，尚未实施。

