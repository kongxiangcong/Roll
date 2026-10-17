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
