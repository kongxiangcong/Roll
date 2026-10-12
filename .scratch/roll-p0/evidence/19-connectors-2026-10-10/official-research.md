# WorkBuddy 金融连接器公开一手能力核查

核查日：2026-10-10（Asia/Shanghai）。范围：公开官网、官方技能源码；未调用账户金融连接器、读取凭据、查询实际 SEALED 数据、训练、更新 ticket 或提交。本文是公开契约评估，不是账户权限或数据质量验收。

结论：**Wind 是值得实测的历史 RAW 量价及公司事件候选来源，但公开 MCP 契约不足以证明 ticket 19 的历史 PIT 合格；腾讯自选股有历史 K 线能力线索，当前未取得可归属于腾讯的一手完整 schema，不能宣布满足，也不能说没有历史能力。** WorkBuddy 只是调用入口，底层 Wind 终端 / Client API 的覆盖不能直接等同于 WorkBuddy 连接器暴露的能力。

## 一手来源与真实性边界

Wind 官网的 [Alice Market](https://aifinmarket.wind.com.cn/) 重定向到 [market.windalice.com](https://market.windalice.com/)，其 [官方接入文件](https://market.windalice.com/skill.md) 明确指定安装源 `https://github.com/Wind-Alice/AliceMarket.git`。网页工具未读到接入文件，已用 Python HTTPS 只读获取同一公开 URL，确认其安装源。没有执行该文件内安装、配置密钥或行情查询指令。

[Wind 官方仓库](https://github.com/Wind-Alice/AliceMarket) 的 README 同时保留 `Wind-Information-Co-Ltd/wind-skills` 路径。以下引用使用官方仓库当前 main 公开文件；main 可变，实测时仍须记录提交版本并从已连接服务取得 `tools/list`。

[Wind Client API 产品页](https://www.wind.com.cn/portal/zh/ClientApi/index.html) 确实介绍历史日线、Tick、分钟数据与权益事件，这是另一产品的概括；没有据此向 WorkBuddy MCP 补造功能。

## Wind：已确认的 MCP 契约

官方 [股票工具契约](https://github.com/Wind-Alice/AliceMarket/blob/main/skills/wind-mcp-skill/references/stock.md) 表明：

- `get_stock_kline` 支持绝对日期区间，日线含 OHLC、成交量与成交额。`aftype` 默认 `0`（前复权），RAW 必须显式用字符串 `"2"`；`issusp` 默认 `"1"` 含停牌；`count=0` 取区间全部。`afdate` 是复权基准日期，不是历史版本查询参数。
- `get_stock_events` 覆盖分红、股本及 ST / 风险警示变化等结构化事件，但不返回公告原文。
- `get_stock_basicinfo` 明确只给当前 ST / 摘牌状态，不给状态变动历史。当前行情工具的涨跌停价也是当前截面。
- 公开契约没有明确量、额单位、历史发布 / 接收时间、版本 ID、修订链、PIT / as-of 查询语义，也没有承诺完整历史交易状态和历史交易规则。

[运行参数规则](https://github.com/Wind-Alice/AliceMarket/blob/main/skills/wind-mcp-skill/scripts/call-rules.json) 进一步校验复权枚举与停牌开关，并将技能层 `period="1d"` 映射为后端 `"10"`。调用技能 CLI 与直接 MCP 时不能混用层级；以实际服务 schema 为准。

官方 [金融文档契约](https://github.com/Wind-Alice/AliceMarket/blob/main/skills/wind-mcp-skill/references/financial-docs.md) 有 `get_company_announcements(query,top_k=5)`，返回相关文本 / 片段。它能帮助寻找公司行为依据，但相关性检索不是公告全集导出接口；不能仅凭返回若干条就断言没有其他事件或已覆盖全部历史。

## 原始响应与完整性：必须额外验收

官方 [CLI 源码](https://github.com/Wind-Alice/AliceMarket/blob/main/skills/wind-mcp-skill/scripts/cli.mjs) 当前标示技能版本 `2.0.4`。其中 `normalizeSuccessPayload`、`normalizeCallSuccess`、`writeRawCallSuccess` 会解析 / 重序列化 JSON，将结构化数据里的 `INVALID` 转为 null，并追加 `cli_meta`；非 JSON 文本才按原文透传。**函数名带 Raw 不表示 stdout 是网络原体。** 存 stdout 可作为工具交付物，但不得将其哈希冒充 HTTP 原始响应体哈希。

同一源码将 `excelTotalCount` 标为 `UNRELIABLE_DECLARED_COUNT`，以实际 `rows.length` 统计返回表；这不保证区间覆盖无遗漏。`count=0` 的语义与服务器实际容量、分页 / 截断限制需要分别核实。ticket 19 需逐段连续日期核对、真实原体或来源原件、请求参数、接收时间及归档哈希。

公开源码列出 `stock_data` 地址 `https://mcp.wind.com.cn/vserver_stock_data/mcp/` 和金融文档独立地址，支持 `list-tools`。本文仅阅读源码，没有发 `tools/list` 或 `tools/call`。

## 腾讯自选股：已发现线索，尚无一手 schema 验收

检索到的 [westock-skill 镜像](https://github.com/infometa/workbuddyskills/blob/main/connectors/westock-mcp/skills/SKILL.md) 声明 author 为腾讯自选股，并列出 `data_quote(date)`、`data_kline(start,end,period,limit,fq)`，其中空 `fq` 表示不复权；还列有停牌、公司事件、风险标签工具。**仓库由第三方 infometa 维护，自述 author 不足以证明原文件当前版本和供应方承诺。** 这些只是下一轮实测字段线索，本报告不据此认定腾讯已支持历史 RAW、历史状态或 PIT。

其 [连接配置镜像](https://github.com/infometa/workbuddyskills/blob/main/connectors/westock-mcp/mcp.json) 指向 `https://stockbuddy.qq.com/cgi/cgi-bin/openai/mcp/mcp`。这是腾讯域名的入口线索，尚未通过官方发布说明或真实 `tools/list` 核对该配置、参数与返回字段。

腾讯 [WorkBuddy 连接器文档](https://staging.codebuddy.cn/docs/workbuddy/From-Beginner-to-Expert-Guide/Function-Description/Connector) 说明连接器各自授权、只按既有权限执行；其文档不提供这两类金融数据完整 schema。开发者社区普通用户文章及 Skill 汇集网站没有用作供应方能力证明。

## 对 ticket 19 的对应判断

| 必需证据 | Wind 公开 MCP | 腾讯自选股当前核查 |
| --- | --- | --- |
| `600362.SH` / `SSE:600362` 历史 RAW 日 OHLCV、量额单位、至少 21 连续交易行 | 区间 RAW 日线有官方契约；实际范围、单位、连续性、缺失 / 停牌含义待测 | 第三方历史 K 线线索，官方 schema / 数据待核实 |
| 20 日事件的可交易性与实际买卖限制 | 当前截面不足；事件接口有部分覆盖，日级停复牌、ST、涨跌停、退市链仍待测 | 未证明历史链覆盖 |
| 公司行为原文、公告 / 生效日及完整性 | 事件接口 + 公告检索可作候选；时间语义、全集完整性、原件待测 | 未证明 |
| 输入在每个历史截止时点已经可得、原版本 / 修订链 | 未在已读公开契约找到支持证明；日期 / afdate 不构成 PIT | 未找到一手支持证明 |
| 历史有效交易规则 | 已读工具契约未覆盖 | 未证明 |
| 批量完整导出、真实原始响应、内容哈希 | 可以取区间，但完整性待测；CLI 会改写 JSON，原体须另保留 | 未证明 |
| 在 Roll 本地持久保存、研究及模型训练的许可 | API Key / 权限不等于数据许可；公开接入文件未给出该用途授权范围 | 未证明 |

因此，下一步应先在用户现有连接器中核对真实工具清单，再做既有 5 日只读样本并问明版本 / 原体 / 单位 / 授权。样本只检查连接器和口径，不能让 `CURRENT_QUERY_ONLY` 升格为历史 PIT 合格；当前最新修订的历史行情即使数值齐全，也不自动解除 ticket 19 的历史时点证据阻塞。若供应方只支持今天回查，可用于覆盖核对、来源适配工程验证或今后前向归档；真实 PUBLIC 数据不能改标为 METHOD_CASE。资格须由冻结协议分别判定，不能用连接器品牌代签。

此前仓库的 WorkBuddy 匿名 Open API `401` 只是未经授权入口结果；没有真实 Wind 调用，不能算 Wind 数据失败。
