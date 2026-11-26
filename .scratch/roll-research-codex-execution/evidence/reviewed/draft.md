---
as_of: '2026-11-26T07:38:52.909461+00:00'
attempt_id: attempt-753e9b8687d245628953e400faaed404
constraint_basis:
  fundamental_gate:
    evidence_refs:
    - material-c85d6bac6b4f1d9c0ffba7e368b2ed6b7b97a3b57d465f73f013af355ad7b687
    rationale: 冻结摘录披露的累计经营活动现金流量净额为 14,162,724,945 元，满足严格大于 0 的唯一门禁。
  invalidation_triggers:
    evidence_refs:
    - material-c85d6bac6b4f1d9c0ffba7e368b2ed6b7b97a3b57d465f73f013af355ad7b687
    rationale: 冻结摘录界定比较口径；按题设，用 Roll 的最新同口径观测判断是否阻断新增风险。持续性另由人工核对。
  strategy_whitelist:
    evidence_refs: []
    rationale: 基本面门禁通过不等于策略获准；没有足够的策略准入证据。
  thesis_status:
    evidence_refs: []
    rationale: 单期累计净额不足以确认或否定投资逻辑。
effective_at: null
evidence:
- id: material-c85d6bac6b4f1d9c0ffba7e368b2ed6b7b97a3b57d465f73f013af355ad7b687
  locator: 第 12 页合并现金流量表，年初至报告期末经营活动产生的现金流量净额
  received_at: '2026-11-26T07:34:09.393912+00:00'
  sha256: 4b7e6ceac5fab04a765125c735815e4e69fd5c05ec1c8aa8198920c3d4f0e716
  source: 江西铜业股份有限公司（巨潮资讯网发行人公告）
  title: 江西铜业股份有限公司 2026 年第三季度报告
  url: https://static.cninfo.com.cn/finalpage/2026-10-29/1225636802.PDF#page=12
evidence_refs:
- material-c85d6bac6b4f1d9c0ffba7e368b2ed6b7b97a3b57d465f73f013af355ad7b687
fundamental_gate: pass
gaps:
- blocking: false
  reason: 冻结摘录只给出本期累计净额，不能判断现金流持续性或确认投资逻辑。
  required_evidence: 多期同口径合并现金流量表及解释现金流变动、营运资本和一次性因素的披露原文。
- blocking: false
  reason: 本期净额仅支持基本面门禁判断，不能据此批准任何策略。
  required_evidence: 拟准入策略的明确规则及验证这些规则所需的证据。
imported_at: '2026-11-26T14:23:59.649629+00:00'
invalidation_triggers:
- condition: 当最新有效的同口径累计净额小于等于 0 元时，阻断新增风险。
  data_required: 最新合并口径、年初至报告期末的经营活动现金流量净额，单位为人民币元。
  effect: block_new_risk
  evidence_refs:
  - material-c85d6bac6b4f1d9c0ffba7e368b2ed6b7b97a3b57d465f73f013af355ad7b687
  feature: operating_cash_flow_ytd_cny
  id: operating_cash_flow_ytd_nonpositive
  operator: <=
  source: Roll 公开观测；同口径参照《江西铜业股份有限公司 2026 年第三季度报告》第 12 页合并现金流量表。
  threshold: 0
- condition: 在据现金流持续性判断投资逻辑前，人工对比多期同口径数据并核对变动原因，判断正净额是否主要由可重复的经营活动支撑；无法确认时继续研究。
  data_required: 多期同口径累计经营活动现金流量净额，以及营运资本变动和一次性因素的相关说明。
  effect: require_research
  evidence_refs: []
  feature: null
  id: cash_flow_sustainability_review
  operator: null
  source: 待补充的发行人定期报告合并现金流量表及现金流变动说明原文。
  threshold: null
published_at: null
review_status: draft
reviewer: null
strategy_whitelist: []
symbol: 600362.SH
task_id: task-ad2c1d5892dd483b89f427cdbf68307e
thesis_status: unknown
valid_until: '2026-12-26T07:38:52.909461+00:00'
version: attempt-753e9b8687d245628953e400faaed404
---
**可核查事实：**《江西铜业股份有限公司 2026 年第三季度报告》第 12 页合并现金流量表“年初至报告期末经营活动产生的现金流量净额”一项，冻结摘录为 **14,162,724,945 元**（`material-c85d6bac6b4f1d9c0ffba7e368b2ed6b7b97a3b57d465f73f013af355ad7b687`）。

**门禁判断：**该净额严格大于 0，按题设唯一基本面规则，本期门禁通过。盘后若 Roll 最新同口径累计净额小于等于 0，则阻断新增风险。

**推断边界：**本期净额为正不证明现金流可持续，也不足以确认或否定投资逻辑；投资逻辑状态保留未知，不批准任何策略。现金流持续性单列为人工研究条件，不作为自动阻断条件。