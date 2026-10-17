# 16 情绪最小替代评估结果（首轮）

模型：IDEA-CCNL/Erlangshen-Roberta-110M-Sentiment，apache-2.0，权重 SHA256 `a1d1328c759c50726db6617c75abb5c260b12377bee7ecd003c8a201b526e38e`，本地离线推理（torch 2.10 CPU，transformers 5.20.1），非 FinBERT2，未训练。

数据：SENTIMENT-CORPUS-02 前 120 条，代理非独立标注；标签在结果前冻结（`eval-protocol.md`、`labels-120.json`）。

## 结果

- 二分类（69 条 P/N 标签）：macro-F1 0.853，POSITIVE recall 1.000，NEGATIVE recall 0.625；低置信拒判 11/120（9.2%）；延迟 p50 0.206s / p95 0.263s。
- 但中性/不相关处理失败：51 条 NEUTRAL/IRRELEVANT 中只有 3 条被拒判（5.9%），48 条被强行判成正/负向；其中 NEUTRAL→POSITIVE 17、IRRELEVANT→POSITIVE 21、IRRELEVANT→NEGATIVE 10。
- 因此：窄口径二分类门槛“通过”，但票 16 要求的“中性/不相关明确拒判”未满足，能力保持 **RESEARCH_LIMITED / NOT_GRANTED**，不能写成完整通过。

## 解释与限制

- 标签来自代理阅读标题/摘要，非独立人工标注，不能宣称独立分类有效性。
- 语料同上游、仅标题摘要，不能代表完整新闻库或长期分布。
- 当前拒判只有低置信度一层；需要独立的市场综述/事实公告/无方向线索拒判层后再评测。不能在看到本轮结果后针对标签调参；下一轮必须先冻结拒判规则再重跑。
- 情绪分类概率不是收益概率或买卖建议。