# Roll 数据、财报与新闻组件候选审计

审计日期：2026-10-14。范围：官方 GitHub、源码与作者文档的静态审查；未安装、未运行候选，未调用受权数据接口、下载模型或访问私有数据。此文件为选型研究，不是实施批准、数据资格认定或任务状态变更。

## 本地边界

- `backend/src/roll/market/cnequity_process.py` 已复用 CNEquity，固定提交 `c118038ea82b5bb78783c0c17a1d9251b36de71d`；现有执行范围限制为 `600362.SH`、最多 45 日及五个来源路由。因此“引入 CNEquity”不是新增能力，应该评估扩展已存在适配器。
- `backend/pyproject.toml` 已包含 BaoStock 0.9.4 和 pypdf；`market/baostock.py`、`baostock_process.py`、`source_facts.py` 已有来源与原件处理。
- 已读 GLOSSARY、ADR 0001/0004：保持模块化单体、候选事实与正式账户/资格分离；量价重建研究不得偷偷引入后来财报、新闻与 LLM 情绪。新增基本面或新闻预测特征应成为新候选、使用独立实验协议。
- 本轮新增组件只能减少取数、解析、分类代码；不能提供缺失的原始历史版本、独立来源、真实前向结果或正式能力授权。

## 候选与接入判断

| 候选 | 已确认功能与具体复用点 | 许可证、服务依赖 | Roll 建议与成本 |
| --- | --- | --- | --- |
| [CNEquity](https://github.com/rootSunc/CNEquity) | 多源数据、Parquet 湖、增量采集与质量检查；官方 `cnequity.query.load` / `cne run daily`，Roll 已直接调用其底层 adapters | Apache-2.0；README 无需账号/token，但上游仍有可达性与覆盖限制 | **优先扩展现有适配器**，成本中；保留 Roll 原件、时钟和来源契约，不复制另一套权威数据湖。官方 PIT 表述不自动等于 Roll 的严格历史时点资格 |
| [AKShare](https://github.com/akfamily/akshare) | `stock_profit_sheet_by_report_em`、`stock_balance_sheet_by_report_em`、`stock_cash_flow_sheet_by_report_em`、`stock_financial_analysis_indicator_em`；可补三表与指标取数 | MIT；选定公开接口通常不需 token；当前 README 要求 Python 3.11+。官方提示数据用于研究、接口可能移除 | **首选三表采集补充**，成本中；适配为 `source_facts` 候选，归档响应、单位、报告类型、发布日期和修订。东方财富与现有东方财富路由不是独立来源 |
| [Tushare](https://github.com/waditu/tushare) | `pro.income`、`balancesheet`、`cashflow` 可作结构化财务来源；利润表有 `ann_date/f_ann_date/report_type/update_flag`，保留不同报表类型 | SDK BSD-3-Clause；Pro 是独立服务，需要 token 和接口权限；官方利润表当前要求 2000 积分，批量 income_vip 为 5000，不应把 SDK 开源理解为数据免费 | **有相应服务权限时值得优先试验**，成本中；历史更正链与第一次实际可得时刻仍须实证，不能仅凭字段认定严格 PIT |
| BaoStock（既有） | 已在 Roll 接入日线、日历及调整来源 | 沿用项目已锁定 SDK/来源审计；本次搜索出现的是非官方 Go 逆向实现，未将其当官方仓库 | **继续现有路线**；无需再引入 Go 客户端。当前连通和字段完整性须看 Roll 验收，本报告未重测 |
| [finance-report-analyzer](https://github.com/lt91888/finance-report-analyzer) | `fetcher.py` 收集 AKShare 三表、财务指标并输出 JSON；分析框架位于 SKILL.md | MIT；取数依赖东方财富和 AKShare。仓库页显示仅 2 次提交，成熟度证据有限 | **小型参考实现**，成本低；可以借鉴字段映射和展示，但它不是完成验证的财务分析引擎。README 限定非金融行业；不要把其 SKILL 自动作为生产指令 |
| [Docling](https://github.com/docling-project/docling) | `DocumentConverter` 可处理 PDF 布局、表格、OCR，导出结构化文档；适合作为当前 pypdf 纯文本不足时的解析 worker | 代码 MIT；README 明确模型各自遵守模型许可。可本地执行；首次模型下载与 OCR 运行依赖须锁定核查 | **首选公告/PDF 表格解析试点**，成本中；结构化提取并不保证财务字段正确，需保存页码/位置/单位并做勾稽验证 |
| [MinerU](https://github.com/opendatalab/MinerU) | PDF/扫描件到 Markdown/JSON，可作 Docling 对比候选 | 当前 LICENSE 为 Apache-2.0 基础加额外条款：商业规模门槛及向第三方提供在线服务时署名；不是纯 Apache-2.0。模型及后端许可仍需逐项核验 | **备选解析器**，成本中到高；只在中文复杂表格样本明显胜出时再采用。未验证本机资源和速度 |
| [RSSHub](https://github.com/DIYgod/RSSHub) | 将网站转换为订阅源；适合独立进程输出 RSS，Roll 通过 HTTP 轮询归档 | **当前 LICENSE 为 AGPL-3.0**，不是 MIT；具体路由可能另需 cookie/token、浏览器或反爬处理。本轮未验证任何财经路由可用性 | **新闻发现候选**，成本中；先固定少量公开路线。仍需自己做正文获取、实体归属、去重、转载链、首次接收时刻、修订与情绪时间序列 |
| [valuesimplex/FinBERT（FinBERT2）](https://github.com/valuesimplex/FinBERT) | 中文金融编码器；`Fin-labeler/sequence_inference.py`、SC_2 情绪任务；Fin-retriever 可用于相关性检索 | 仓库 MIT；作者提供模型和数据链接，但具体 checkpoint 的模型卡/权重许可需在选定后单独确认。不是所有权重都已验证可下载 | **中文情绪分类的首选验证候选**，成本中；先标注 Roll 新闻样本比较准确率/拒判，不把情绪分类概率当上涨概率。预训练数据时间范围可能造成历史评测污染，需界定用途 |
| [FinGPT](https://github.com/AI4Finance-Foundation/FinGPT) | 金融指令微调、LoRA、情绪/问答研究流水线；README 包含中文基座方案 | 代码 MIT；基座模型、LoRA 权重、训练数据和外部 API 权限分别核验 | **研究备选，非当前最低成本首选**，成本高；不要整体迁移多模型流水线。现有轻量分类器满足前先不投入大模型训练 |
| [yya518/FinBERT](https://github.com/yya518/FinBERT)、[ProsusAI/finBERT](https://github.com/ProsusAI/finBERT) | 英文金融情绪模型与示例；yiyanghkust/finbert-tone 是其中常见权重 | 此轮未完成所选权重许可证审计，不能作为可直接部署结论 | **不作为中文默认情绪模型**；英文能力不能推断中文能力，也不应为了使用它默认先翻译所有新闻 |

接入成本是结构判断（低=小型适配/参考；中=运行隔离、契约和验收；高=训练/多服务），并非交付工期承诺。

## 优先顺序

1. 先在既有 CNEquity/BaoStock/原件链上补证据完整性；不要为了换库重启验证链。
2. 财报 MVP：AKShare 或已获得权限的 Tushare 三表 → Roll 标准化、报告期/披露时间/修订账本 → 确定性财务指标与原件链接。Docling 仅为 PDF 表格/OCR 补充。
3. 新闻 MVP：优先用 [AKShare 官方文档](https://akshare.akfamily.xyz/data/stock/stock.html) 的 `stock_news_em` 单股新闻接口，再用 [trafilatura](https://github.com/adbar/trafilatura) 提取可访问网页正文 → 原始内容归档和去重 → 证券相关性 → FinBERT2 分类评测 → 带版本的情绪序列。`stock_news_em` 仅覆盖当日最近 100 条，不能当完整历史新闻库；要从现在持续归档并记录轮询遗漏风险。RSSHub 是扩展订阅来源的备选，不是 MVP 必需服务。trafilatura 的具体版本、许可和正文样本正确率仍须在接入时锁定验收。
4. 有了可追溯前向样本后，再研究财报/情绪特征的增量预测价值，并冻结新候选。不要把新增能力直接塞进现有量价模型工件。

## 无法由开源项目替代的工作

- 缺失的历史首次发布与修订证据、同上游重复源、不可访问或无权使用的数据。
- 公司行动经济语义、财报口径与单位、累计/单季、金融行业特殊报表、重述版本和缺失值判断。
- 新闻转载去重、对哪家上市公司利好/利空的对象判断、时间对齐、延迟与非交易日聚合。
- 本地资源/稳定性、数据合约、Windows 兼容性和真实接口验收。
- 概率校准、独立验证、前向积累、用户资金授权。情绪标签置信度不等于买卖收益事件概率。

## 维护状态与证据限制

本轮主研究代理已成功获取下列 GitHub REST 元数据，全部 `archived=false`；日期为 `pushed_at` 的 UTC 日期，不是正式发行日期，也不能证明维护质量或接口可用性。

| 仓库（官方 API） | pushed_at UTC 日期 |
| --- | --- |
| [CNEquity](https://api.github.com/repos/rootSunc/CNEquity) | 2026-10-08 |
| [AKShare](https://api.github.com/repos/akfamily/akshare) | 2026-10-13 |
| [Tushare](https://api.github.com/repos/waditu/tushare) | 2024-03-13 |
| [Docling](https://api.github.com/repos/docling-project/docling) | 2026-10-14 |
| [MinerU](https://api.github.com/repos/opendatalab/MinerU) | 2026-10-14 |
| [RSSHub](https://api.github.com/repos/DIYgod/RSSHub) | 2026-10-14 |
| [FinGPT](https://api.github.com/repos/AI4Finance-Foundation/FinGPT) | 2026-09-23 |

FinBERT 的 API 请求在 10 秒超时，最新推送日期未确认。Tushare SDK 仓库推送较早，不据此推断其在线数据服务停止维护。后续实施前应锁定具体 tag/commit、检查最近发布/问题响应、许可证文件与依赖漏洞，再做运行验收。finance-report-analyzer 页面显示 2 次提交，FinBERT 页面显示 19 次提交；这些只是页面快照，不能替代维护质量分析。

## 一手来源补充

- [AKShare 官方使用与限制](https://github.com/akfamily/akshare)、[官方股票接口文档：三表与 stock_news_em](https://akshare.akfamily.xyz/data/stock/stock.html)。
- [Tushare 利润表：权限、时间字段、调整前报表](https://tushare.pro/document/2?doc_id=33)。
- [Docling：本地文档解析与模型许可](https://github.com/docling-project/docling)。
- [MinerU 当前完整许可](https://github.com/opendatalab/MinerU/blob/master/LICENSE.md)。
- [RSSHub 当前完整许可](https://github.com/DIYgod/RSSHub/blob/master/LICENSE)。
- [FinBERT2 中文任务和入口](https://github.com/valuesimplex/FinBERT)、[FinGPT 许可](https://github.com/AI4Finance-Foundation/FinGPT/blob/master/LICENSE)。

所有推荐均为文档和本地源码审计结论，未证明数据可用、解析准确或策略收益。
