# 16 工程标准审查

- 隔离：模型推理只在既有隔离运行时子进程，业务 venv 不增 torch/transformers；导入前拒绝 socket，离线变量固定。
- 指纹：reference 校验包版本与权重/config/vocab SHA256；权重下载尝试有独立编号、字节/时间上限与零重试。
- 持久化：`sentiment_runs`/`sentiment_facts` 只追加；分类绑定 fact、event、association、文本 SHA、模型/权重与拒判层版本。
- 可追溯：公开 API 与页面显示覆盖、计数、拒判原因、评测门槛未通过；不显示收益/买入概率。
- 测试：METHOD 注入 worker，真实运行单独留证；不把 METHOD 当真实模型结果。
- 限制：标签非独立、语料同上游、留出集失败；未针对留出集调参。
- 开放风险：模型偏正向、拒判层过宽；在没有新独立标签前不得调门槛或宣称通过。
