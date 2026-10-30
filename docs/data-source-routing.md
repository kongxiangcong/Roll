# 默认数据来源与自动切换

2026-10-29 的[来源比较](research/2026-10-29-data-source-comparison.md)区分供应商官方接口和交易所/发行人原始披露。当前本机使用以下设置；密钥保留在宿主私有环境中，不需要填进页面。

```dotenv
ROLL_DATA_SOURCE_POLICY=OFFICIAL_FIRST
ROLL_MX_CONFIG_FILE=C:/Users/72449/.codex/config.toml
# FUYAO_API_KEY 使用已有配置；不要将真实值写进文档或提交 Git。
```

`EM_API_KEY` 优先于显式 `ROLL_MX_CONFIG_FILE`；后者只接受固定妙想地址的 `http_headers.em_api_key`。不自动搜索其他凭据。启动时读取仓库 `.env` 或显式 `ROLL_ENV_FILE`；进程环境优先。修改后停止原宿主再启动，同一个已运行进程不会热读 `.env`。

| 用途 | 自动默认及备用 |
|---|---|
| 普通个股日线 | 扶摇 → 东财公开日线 → BaoStock PUBLIC → 搜狐 → 腾讯 |
| 固定背景指数日线 | 扶摇 → 腾讯 |
| 带明确证券时点的报价 | 新浪 → 腾讯 → 扶摇；扶摇目前仅作时间未知的受限参考，不能替代新鲜报价 |
| 公司行为 | 扶摇 → 东财 → BaoStock PUBLIC；保留披露/记录日/配股完整性缺口 |
| 财务/公告研究参考 | 妙想 → 扶摇利润表或个股新闻首屏；东财财报/公告PDF原件继续按现有路径核验 |
| 停牌/ST、交易日历 | 已适配 BaoStock/官方来源；不从非零价格或股票名称推断状态 |

页面日线、报价和除权事项默认选择 AUTO，可手动固定一个供应商。API支持同名字段 `daily_source/quote_source/adjustment_source="AUTO"`；`research_source="AUTO"` 开启供应商参考。OFFICIAL_FIRST 下省略的字段采用默认路由；显式供应商保持原请求，不自动换源。`ROLL_DATA_SOURCE_POLICY=LEGACY` 恢复原省略字段默认值，显式 AUTO 仍有效。

勾选「增加一个来源比较」，或API传 `compare_sources=true`，在原请求剩余预算内尝试取得另一个来源；失败可顺序尝试后续来源，最多保留一个取得数据的比较来源。比较对齐证券、日期、复权、币种；报价还要求相同证券时点。差异和不可比较原因记录在 `source_comparisons`，保留主源，不投票或平均。不同供应商不自动意味着独立原始生产。

自动换源处理网络、HTTP错误、业务错误、无数据和质量/必需字段不满足。扶摇 HTTP429/业务4001是限流，2001是认证、2003是权限；妙想明确积分/额度不足记录 `MX_QUOTA_EXHAUSTED`，未知业务错误保留通用错误，不编造稳定供应商错误码。认证、额度、权限/限流冷却5分钟，SQLite保留到期时间；不会购买额度或自动提升权限。

所有尝试共用原请求调用数、时间、响应/总字节预算。失败请求、归档、子运行引用与实际来源保留在 `source_attempts`/`tools`；完整来源不足时保留部分事实及 `AUTO_GROUP_INCOMPLETE`，不将RAW补成前复权。离线回放仍不联网。

日常卡片、MARKET更新、取证页面采用AUTO。交易辅助在OFFICIAL_FIRST下优先扶摇RAW日线，个股回测所需昨收/停牌/ST从BaoStock补充且逐日比对OHLC；不匹配或取不到时不伪造执行字段，保留辅助材料但回测受限。每对象仍限制30秒、5次操作、2MiB总响应。RESEARCH刷新与无显式原件计划的完整报告先采集供应商研究参考，保存为共享材料，之后沿用现有财务/新闻采集器和原件；有明确原件计划时继续按计划执行。

供应商参考单独放在快照 `research_context`，有原始响应哈希、实际接收时间及 `admitted_as_fact=false`。公司材料标为 `SUPPLIER_RESEARCH_REFERENCE`，不自动生成财务事实或历史PIT资格。宏观、港美股等工具虽有客户端允许名单，本轮没有将它们加入默认公司采集；既有前向CNEquity/AKShare策略也不被按需路由替换。

查询当前策略：`GET /api/data/source-policy`。源码默认LEGACY用于兼容未配置安装；本机私有 `.env` 已启用OFFICIAL_FIRST。测试工厂不自动读取仓库凭据。真实验收收据与METHOD测试分开保存到 `.scratch/roll-source-routing/`。
