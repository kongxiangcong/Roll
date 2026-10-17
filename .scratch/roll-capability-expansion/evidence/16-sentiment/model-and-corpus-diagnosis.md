# 16 中文情绪组件：权重与语料条件诊断

日期：2026-10-18（Asia/Shanghai）。只做只读公开元数据核对与本仓库证据检索；未下载权重、未训练、未改业务依赖。

## 核对结果

1. 官方组织 `valuesimplex-ai-lab` 当前公开模型只有：
   - [FinBERT2-base](https://huggingface.co/valuesimplex-ai-lab/FinBERT2-base)（license:apache-2.0，预训练 BERT，文件为 pytorch_model.bin/config/tokenizer）
   - [FinBERT2-large](https://huggingface.co/valuesimplex-ai-lab/FinBERT2-large)（license:apache-2.0，预训练）
   - [Fin-Retriever-base](https://huggingface.co/valuesimplex-ai-lab/Fin-Retrieve-base)（检索）
   - FinBERT1-base（apache-2.0）
2. GitHub [valuesimplex/FinBERT](https://github.com/valuesimplex/FinBERT) README 的“模型列表”同样只列 base/large/retriever；情绪任务在 `Fin-labeler/SC_2` 目录以**二分类数据集 + 微调脚本**提供，没有发布可直接推理的中文情绪 checkpoint。
3. 因此若坚持“复用推理而非默认自训”，当前没有满足条件的 FinBERT2 情绪权重；若改走自训，需要先冻结标签映射、数据切分、训练/评测方法和算力预算，属于规格允许但需明确授权的路线。
4. 本仓库当前合法归档中文新闻只有 14 票的 10 条标题/摘要与 3 篇正文；没有 ≥120 条带事件组/时间切分与人工标签的中文语料。不能把财报 PDF 句子当新闻情绪标签，也不能用 10 条自称覆盖正/负/中性/不相关/否定/修订/多公司/转载。

## 具体未满足条件

- 缺：已发布、许可明确、标签集明确的中文金融情绪 checkpoint（HF id + 文件 SHA256 + license）。
- 或：用户授权按冻结方法自训 FinBERT2（SC_2 二分类）并提供算力/时间上限；二分类仍不能生成中性概率，需拒判层。
- 缺：≥120 条合法归档中文材料的标签集（事件组/时间隔离）；若由代理标注，必须在结果中标注“非独立人工标注”。

## 未执行

未下载模型/数据、未训练、未新增依赖、未调用外部推理服务、未创建评测结论。16 保持 pending/needs-info；17 及其后的 18/22/26 继续受此条件阻塞。以上不是对 FinBERT2 方法有效性的否定，只是当前资源与授权条件不足。


## 2026-10-18 语料补充尝试 SENTIMENT-CORPUS-01

经登记的 3 次有界请求（同上游 `search-api-web.eastmoney.com`，pageSize=50，页1—3）取得 150 条唯一标题/摘要，共 73,437 字节、零重试、零跳转；原始 JSON 归档在 `corpus-attempt/01.raw`—`03.raw`，结构化副本为 `corpus-attempt/corpus.json`。这解决了“不足 120 条候选文本”的数量问题，但仍是同一上游、仅标题/摘要（其中 10 条有正文），不能算独立来源或完整新闻库。

仍未满足：120 条标签集（需在查看模型结果前冻结标注规则与阈值）、可用的中文情绪 checkpoint。若采用非 FinBERT2 的中文二分类模型，只能按 ID-10 作为“最小替代评估”，必须记录实际标签集、拒判和未过门槛的研究受限状态，不能宣称 FinBERT2 或收益有效性。

### 语料构成复核（2026-10-18）

用 15 票的确定性关联规则对 150 条做离线分类：COMPANY_SUBJECT 33、COMPANY_MENTIONED 28、INDUSTRY_BACKGROUND 33、UNRELATED 29、UNCERTAIN 27。公司相关合计 61 条，仍不足以支撑 120 条公司级情绪标签；其余多为资金流/概念表，标题摘要本身不表达对目标公司的情绪。

因此下一语料尝试应使用公司名称关键词（同上游、固定 3 页/150 条/零重试）而不是证券代码，并继续把 INDUSTRY/UNRELATED 作为拒判与覆盖样本，而不是强行给目标公司情绪标签。