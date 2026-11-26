---
as_of: '2026-11-26T07:38:52.909461+00:00'
attempt_id: attempt-3ea6fa67605b4a39bdcae7154f89c802
constraint_basis:
  fundamental_gate:
    evidence_refs:
    - material-c85d6bac6b4f1d9c0ffba7e368b2ed6b7b97a3b57d465f73f013af355ad7b687
    rationale: 《江西铜业股份有限公司 2026 年第三季度报告》第 12 页合并现金流量表所列年初至报告期末经营活动现金流量净额为 14,162,724,945
      元，满足本次唯一条件：严格大于零。
  invalidation_triggers:
    evidence_refs:
    - material-c85d6bac6b4f1d9c0ffba7e368b2ed6b7b97a3b57d465f73f013af355ad7b687
    rationale: 仅对上述报告第 12 页同一报告期、同一合并口径的净额应用原门禁阈值，不设投资逻辑或策略层面的触发条件。
  strategy_whitelist:
    evidence_refs: []
    rationale: 单项门禁通过不等于策略获准，现有证据不足以列入任何策略。
  thesis_status:
    evidence_refs: []
    rationale: 单期净额为正不足以判断投资逻辑是否成立或失效。
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
  reason: 单期累计净额只能判断该期净额是否为正，不能判断经营现金流能否持续为正。
  required_evidence: 多期可比经营现金流数据，以及营运资金变动和一次性因素的说明。
- blocking: false
  reason: 本次单项门禁不验证投资逻辑，也不构成策略准入。
  required_evidence: 明确的投资逻辑及其验证证据、具体策略的准入规则及相应证据。
imported_at: '2026-11-26T14:07:50.783790+00:00'
invalidation_triggers:
- condition: 若后续正式更正使同一报告期、同一合并口径的经营活动现金流量净额小于或等于零，则本次门禁通过结论失效。
  evidence_refs:
  - material-c85d6bac6b4f1d9c0ffba7e368b2ed6b7b97a3b57d465f73f013af355ad7b687
published_at: null
review_status: draft
reviewer: null
strategy_whitelist: []
symbol: 600362.SH
task_id: task-c34b389365a84c7985cf839e99016aaf
thesis_status: unknown
valid_until: '2026-12-26T07:38:52.909461+00:00'
version: attempt-3ea6fa67605b4a39bdcae7154f89c802
---
**可核查事实：**《江西铜业股份有限公司 2026 年第三季度报告》第 12 页合并现金流量表摘录：“年初至报告期末经营活动产生的现金流量净额：14,162,724,945 元。”

**门禁依据与范围：**14,162,724,945 元大于零，因此本次基本面门禁通过。该门禁仅检验年初至报告期末的合并经营活动现金流量净额是否严格大于零，不评价单季度表现或整体基本面。

**推断边界：**仅凭这一项，不能判断经营现金流能否持续为正，不能确认或否定投资逻辑，也不能认定任何策略获准准入。