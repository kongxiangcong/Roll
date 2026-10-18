# 16 受限情绪研究组件与有限评测验收（partial）

> 2026-10-18接手纠正：[新验收](takeover-20261018/acceptance.md)发现下文旧召回/macro-F1漏计拒判FN和跨类FP。当前合并负向召回为0.200、二类macro-F1为0.563218；旧120/30日期范围交叠，不能视为时间隔离评测。原始报告及本页历史结果保留，当前指标依据采用新纠正报告。16继续partial。

交付一个**受限研究组件**：本地二分类中文情绪模型 + 冻结拒判层，只处理已保存新闻事实；明确不是 FinBERT2，不生成中性/收益概率，不构成买卖建议。因 FinBERT2 官方无中文情绪 checkpoint，本票按验收条件第 6 条保持 **partial**，同时保留真实替代评估与完整工程。

## 交付

- `backend/src/roll/market/sentiment_contract.py`：冻结拒判层 v1（市场指数/资金流/无方向线索/关联不适用/低置信度）。
- `sentiment_process.py`：隔离运行时离线推理，导入前拒绝 socket，校验包版本与权重 SHA256。
- `sentiment-reference.json`：模型 IDEA-CCNL/Erlangshen-Roberta-110M-Sentiment（apache-2.0）、权重 SHA256 `a1d1328c…`、包版本、拒判层、评测限制。
- `sentiment.py` + 路由：`POST /api/market/sentiment/{instrument}/classify`、`GET /api/market/sentiment/{instrument}`、`GET /api/market/sentiment/runs/{id}`。保存 fact/event、关联、文本 SHA、模型与权重、置信度、拒判原因；只追加。
- 页面：“受限情绪研究”折叠区，显示覆盖、计数、拒判原因、模型/权重、评测门槛未通过与限制；不显示收益概率。

## 真实运行

`real-sentiment.json` / `real-sentiment.log`：对 14 票实际归档的 10 条新闻分类，模型真实加载并离线推理：

- POSITIVE 2、ABSTAIN_FUND_FLOW 3、ABSTAIN_NO_DIRECTIONAL_CUE 5，覆盖 20%；
- 账户版本 0→0，network_calls=0，状态 COMPLETE，能力 `RESEARCH_LIMITED`。

## 评测（冻结标签与门槛）

- 150 条唯一公司名标题摘要（SENTIMENT-CORPUS-02），150 个唯一事件、0 转载/修订；120 条设计标签 + 30 条留出标签，均为代理非独立标注。
- 首轮无拒判：二分类 macro-F1 0.853，但中性/不相关拒判仅 5.9%。
- 冻结拒判层后：设计集 macro-F1 0.956、拒判 0.804；留出集 macro-F1 0.333、负向召回 0.000；合并 macro-F1 0.803、正向召回 1.000、负向召回 0.500、拒判覆盖 0.540。
- 冻结门槛未通过：负向召回 <0.55、总拒判覆盖 >0.35；能力保持 RESEARCH_LIMITED / NOT_GRANTED。见 `eval-report.md`、`eval-reject-report.md`、`eval-reject-results.json`。

## 工程验收

- `app-test.log` 1 passed/7.47s：METHOD 分类、拒判、幂等、截止重放、重启、账户不变。
- `regression.log` 5 passed/29.41s（sentiment + news ingestion + events）。
- `browser.log` 1 PASS/9.2s：390px、标签/拒判/门槛未通过可见、0 分类 POST；截图 `mobile.png`。
- `build.log` TypeScript/Vite 通过。

## 未完成与限制

- FinBERT2 官方情绪权重仍缺失；替代模型不是 FinBERT2，且未过冻结门槛。
- 标签非独立人工标注；语料同上游、仅标题摘要；留出集负向召回 0.000。
- 因此 16 保持 partial，17 及 18/22/26 继续受依赖阻塞；不得把拒判当中性，不得据此授情绪能力或收益含义。
