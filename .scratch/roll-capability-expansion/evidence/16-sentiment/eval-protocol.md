# 16 中文情绪有限评测预登记（结果前冻结）

冻结时间：2026-10-18（Asia/Shanghai）。此时尚未下载情绪模型、未运行任何分类结果。

## 数据

- 主评测集：SENTIMENT-CORPUS-02（公司名称关键词，150 条唯一标题/摘要），取前 120 条，标签见 `labels-120.json`。
- 标签来源：代理逐条阅读标题/摘要标注，**非独立人工标注**；不含正文（仅 10 条有正文）。
- 类别：POSITIVE / NEGATIVE / NEUTRAL / IRRELEVANT（定义见 labels-120.json 的 rubric）。
- 切分：按事件组（15 票规范URL/内容哈希）与日期描述，不训练、不调参；全部 120 条只作评测。留出 30 条不参与本轮指标。
- 拒判：关联规则为 INDUSTRY_BACKGROUND/UNRELATED 的条目不进入模型，记为 ABSTAIN_RELEVANCE；模型二分类无法输出中性，最大概率 <0.65 记为 ABSTAIN_LOW_CONFIDENCE。

## 模型候选

FinBERT2 官方无中文情绪 checkpoint，不能复用推理。按 ID-10 记录“最小替代评估”：只允许使用许可证明确（apache-2.0/MIT）、中文、二分类、可离线推理的模型；不得生成中性概率或收益概率。选定模型与权重 SHA256 必须在本文件追加后方可运行。

## 冻结门槛（结果前）

- macro-F1（POSITIVE/NEGATIVE 二类）≥ 0.60
- POSITIVE recall ≥ 0.55；NEGATIVE recall ≥ 0.55
- 拒判覆盖率 ≤ 0.35（含 relevance 与低置信度）
- 推理延迟 p95 ≤ 3.0 秒（CPU，单条）
- 任一门槛未达：能力保持 RESEARCH_LIMITED / NOT_GRANTED，不得写成通过。

## 指标与留证

每类支持数、macro-F1、每类 recall、混淆矩阵（含 ABSTAIN 列）、拒判原因分布、延迟 p50/p95、模型版本/权重 SHA256、输入文本 SHA256、运行命令与机器资源。非独立标签不得宣称独立分类有效性。
