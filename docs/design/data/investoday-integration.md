# Investoday 在 Roll 的接入建议

建议 Roll 后端通过 HTTPS REST API 按数据项采集，先用行业历史日行情验证固定轨所需的结构化数据，再用个股研报元数据验证周度研究。首轮在独立目录取样，保留现有工作台数据。供应商公开文档说明调用契约，实际账户的授权、历史覆盖、配额与可保存范围仍待验证。[已有双轨评审](../research/roll_dual_pipeline_review.md#4-investoday-应放在哪里)

## 调用与验收

REST 让 Roll 固定端点、日期、分页和请求预算，按同一参数重跑并解释差异。MCP 适合分析师在一次研究会话中临时搜索研报或追问线索；固定的周度研报清单仍可走 REST，保留明确的日期窗口。Agent Skills 面向使用编码助手的人，可按需安装，Roll 后端无需依赖它。三种入口的选择取决于谁发起查询以及是否要重复采集。[官方接入方式](https://std.investoday.net/apidocs/quick-start) · [AI 原生金融数据](https://std.investoday.net/apidocs/ai-native-financial-data)

后端从本地配置读取建议键名 `INVESTODAY_API_KEY`，在请求头 `apiKey` 传入密钥，检查 HTTP 状态及 JSON 业务码 `code=0`。以 `POST /data/industry/quote` 验证一个行业连续 20 个交易日的开高低收与量额，核对行业分类、日期连续性和单位。该端点的日期参数下界为 2020-01-01，每页最多 500 条，实际覆盖应根据返回内容记录。分页测试可调小每页条数，记录页边界、重复条数及缺日。调用记录中剔除密钥。[官方快速开始](https://std.investoday.net/apidocs/quick-start) · [行业历史日行情](https://std.investoday.net/apidocs/api-reference/行业历史日行情/行业历史日行情)

## 与当前实现衔接

- `sync_workbench` 已统一手动同步与区间补库。`sync_inputs` 默认使用 AKShare，识别的数据项有明确清单，传入 `source` 时还会调用它的交易日历。行业指数日线应先定义行业标识与独立序列，再按序列选择来源，沿用现有交易日历和同步入口。行业 ETF 保持自己的证券代码与行情。[同步入口](../../../backend/src/roll/market/sync.py#L11) · [数据项与日历](../../../backend/src/roll/market/inputs.py#L143)
- 现有 `market_inputs` 主键只有数据项、标的与交易日，同键写入会覆盖观察值。并行对账先单独留存来源、无密钥请求参数、实际采集时间、原始单位、响应指纹和版本，再挑选合格记录进入工作台。历史修订和补采时间影响回测中何时可使用该记录。[主键](../../../backend/src/roll/market/inputs.py#L30) · [写入行为](../../../backend/src/roll/market/inputs.py#L79) · [历史时点原则](../../adr/0004-reconstructed-price-volume-research.md)
- Roll 的 ETF 资金流按相邻交易日的份额差乘当日净值计算。Investoday 二级市场成交资金流可设独立指标，期间份额变化、资金净流入均不能直接填入日终总份额。[当前计算公式](../../../backend/src/roll/market/inputs.py#L60) · [供应商数据项与口径对照](../research/roll_dual_pipeline_review.md#4-investoday-应放在哪里)
- 周度研究先保存研报标题、机构、发布时间与原文定位。机构观点保留作者归属，影响公司事实判断的数字回溯公司公告。原文存储与索引按实际授权范围决定。[既有研究要求与样本建议](../research/roll_dual_pipeline_review.md#4-investoday-应放在哪里)
