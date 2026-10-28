# Independent workbench decision evidence repair
Status: ready-for-agent

Audit: E:/workspace/codex/2026-10-28/task-2/roll-workbench-independent-audit.md (2026-10-28).
Scope: offline HTML only; preserve chart/search/navigation. No APIs, backend edits, deployment or real research.

Capability mapping: models.py:299-329 -> historical CAL probability and unavailable current prediction; validation.py:141-174 -> sample/calibration diagnostics and INCONCLUSIVE/FAIL distinct from NOT_GRANTED; exploratory.py:6-82 -> fixed SMA5/20 exploration with costs and benchmark, not model performance or walk-forward; assistance.py:19-21,134-142 -> Jiangxi Copper scope only; ADR0005 -> assistance without formal grant; accounts/valuation.py and decisions/actions.py -> unknown account and unavailable execution sizing; enterprise valuation spec -> unimplemented DCF, no price multipliers.

The UI is a contract fixture, not an API adapter. All fixture identifiers explicitly start MOCK. Exact forecast event, artifact hashes, ledger details, real source links and real saved result replay remain unconnected. Synthetic summary numbers are not backend results. No live performance claims.

Acceptance: current probability unavailable; historical semantics and calibration support explicit; negative/zero/missing/expired/partial/corrupt/insufficient/FAIL states; instrument and generation checks; risk and conditions drilldown. Preserve real integration as a separately reviewed task.
