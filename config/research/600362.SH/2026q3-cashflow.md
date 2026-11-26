---
version: 2026q3-cashflow
as_of: "2026-11-26T06:23:37+00:00"
valid_until: "2026-12-01T00:00:00+08:00"
fundamental_gate: pass
thesis_status: watch
strategy_whitelist: []
invalidation_triggers:
  - id: operating-cash-flow-nonpositive
    source: 江西铜业最新正式定期报告或更正公告
    data_required: 合并现金流量表的年初至报告期末经营活动现金流量净额
    condition: 最新披露或更正后的累计经营活动现金流量净额小于等于零
    effect: block_new_risk
    evidence_refs: [2026q3-report]
  - id: cash-flow-hypothesis-falsified
    source: 江西铜业 2026 年年报及三季报
    data_required: 同口径合并经营现金流及归母扣非净利润的全年和前三季度累计值
    condition: 在适用条件成立时，四季度经营活动现金流量净额小于等于零或归母扣非净利润同比未增长
    effect: require_research
    evidence_refs: [2026q3-report]
evidence_refs: [2026q3-report, 2026h1-report, icsg-2026-10]
constraint_basis:
  fundamental_gate:
    evidence_refs: [2026q3-report]
    rationale: 最近一期正式定期报告可定位，前三季度累计经营活动现金流量净额大于零。这一门禁仅检查经营现金流。
  thesis_status:
    evidence_refs: [2026q3-report, 2026h1-report, icsg-2026-10]
    rationale: 利润和经营现金流同步改善。加工费、季节性与资本支出仍需跟踪。
  strategy_whitelist:
    rationale: 四季度的经营和风险指标尚待验证，维持观察。
  invalidation_triggers:
    evidence_refs: [2026q3-report]
evidence:
  - id: 2026q3-report
    classification: disclosure
    title: 江西铜业股份有限公司 2026 年第三季度报告
    issuer: 江西铜业股份有限公司
    source: 巨潮资讯网发行人公告
    url: https://static.cninfo.com.cn/finalpage/2026-10-29/1225636802.PDF
    locator: 第 1 页主要会计数据，第 4 页变动原因，第 12–13 页合并现金流量表
    disclosed_at: 2026-10-29
    received_at: "2026-11-26T06:23:37+00:00"
  - id: 2026h1-report
    classification: disclosure
    title: 江西铜业股份有限公司 2026 年半年度报告
    issuer: 江西铜业股份有限公司
    source: 巨潮资讯网发行人公告
    url: https://static.cninfo.com.cn/finalpage/2026-08-26/1225505938.PDF
    locator: 第二节 主要会计数据及第三节（一）公司从事的主要业务及经营模式
    disclosed_at: 2026-08-26
    received_at: "2026-11-26T06:23:37+00:00"
  - id: icsg-2026-10
    classification: external_forecast
    title: ICSG Copper Market Forecast 2026/2027
    issuer: International Copper Study Group
    source: ICSG 新闻稿
    url: https://icsg.org/download/2026-10-14-press-release-icsg-copper-market-forecast-2026-2027/
    locator: 附件第 1 页全球精炼铜供需结余段落与第 2 页结余表
    disclosed_at: 2026-10-14
    received_at: "2026-11-26T06:23:37+00:00"
---

# 江西铜业 600362.SH · 盈利改善能否转为经营现金流

## 披露事实

2026 年第三季度单季营业收入同比下滑 2.75%，同期扣非归母净利润 26.83 亿元，同比增长 40.42%。2026 年前三季度累计扣非归母净利润 102.39 亿元，同比增长 63.56%，经营活动现金流量净额为 141.63 亿元，同比增长 125.23%。公司把盈利改善归因于经营管理、资源利用效率与主产品价格共同作用。这是公司在未经审计季报中的解释。同期投资现金净流出 159.33 亿元，筹资现金净流入 164.03 亿元。 [2026 年三季报][q3]

江西铜业同时经营矿山、冶炼、加工及贸易。半年度报告披露，进口铜精矿定价与 LME 铜价以及金银价格相关，扣减双方商定的 TC/RC。上半年累计经营活动现金流量净额 58.14 亿元。 [2026 年半年报][h1]

## 外部预测

ICSG 在 2026 年 10 月预测全球精炼铜市场 2026 年结余约 10.4 万吨，2027 年约 36.8 万吨。该口径使用中国表观消费，未计入未报告库存，适合作为行业供需情景。 [ICSG 供需预测][icsg]

## 研究推断与反证

用前三季度累计经营现金流减去上半年累计值，第三季度单季经营现金流约 83.48 亿元。利润和经营现金流同步改善支持继续观察盈利兑现。前三季度经营现金流不足以覆盖同期全部投资现金净流出，且公司同时暴露于矿山与冶炼加工，尚无法量化铜价、TC/RC、库存变动和融资变化分别贡献了多少。缺少可核证的市场一致盈利预期，也无法判断股价已计入多少改善。 [2026 年三季报][q3] · [2026 年半年报][h1]

## 待验证的投资假设

**cash-flow-persistence** · 江西铜业 2026 年第四季度的盈利改善仍能转化为正经营现金流。若年报未披露重大并表口径变化或核心生产长期停摆，验证目标为第四季度合并经营活动现金流大于零、同期扣非归母净利润同比增长，两者同时满足才支持命题。以 2026 年年报正式披露为验证期限。将 2026 年和 2025 年各自的全年同口径累计值各减去其前三季度可比值，再作单季比较。任一目标未达到即证伪，触发重新研究。条件不成立或数据缺失则记录为未知。识别正现金流门禁时直接读最新正式定期报告的累计值，累计值小于等于零时暂停增加风险。 [2026 年三季报][q3]

每周查阅发行人公告。有财报更正、重大生产或并表变更时提前复核。档案有效期届满重新确认现金流门禁、披露时效及投资逻辑。

[q3]: https://static.cninfo.com.cn/finalpage/2026-10-29/1225636802.PDF
[h1]: https://static.cninfo.com.cn/finalpage/2026-08-26/1225505938.PDF
[icsg]: https://icsg.org/download/2026-10-14-press-release-icsg-copper-market-forecast-2026-2027/
