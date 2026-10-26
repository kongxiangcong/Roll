# Standards review

Reviewed the current uncommitted ticket 19 slice against base `353579d`: `performance_process.py`, `performance_reports.py`, their app routes, performance panel/research-report insertion/styles, and performance tests/fixture. Existing SSE, financial and other dirty changes excluded. Sources: AGENTS.md, domain instructions, GLOSSARY.md, ADRs 0001–0004, ticket 19, and the code-review smell baseline. Tool-enforced checks excluded.

No actionable documented-standard violations, Fowler smells, or additional boundary findings found.

The host reuses existing saved-report and archive boundaries, records original/source/renderer fingerprints, and writes only derivative report rows and artifacts. Saved retrieval checks the manifest and every referenced derivative/source archive and works without the QuantStats runtime. Concurrent inserts recheck the idempotency key within BEGIN IMMEDIATE and preserve the unique constraint.

The isolated renderer disables the relevant network paths, checks QuantStats 0.0.86, records actual library source hashes, and receives only saved curves. The host bounds the saved window to 3650 sessions, kills and waits for interrupted/overdue subprocesses at 30 seconds, and checks result/figure sizes before archiving. No new fit, forecast, shadow advance or validation writer is introduced.

Local inspection of the pinned library confirms `compsum` does fill missing returns, but this adapter rejects missing/unknown fixed-window observations before calling it. `monthly_returns(..., prepare_returns=False)` bypasses automatic price/return inference; synthetic zero month cells are excluded using observed return months. Drawdown receives explicitly normalized NAV starting at 100. The first saved close is an anchor with an unknown initial return, not a manufactured zero earning; boundary monthly intervals are labelled and short-window annualization is suppressed.

Missing matched benchmark input remains explicit, with no fabricated relative-return series. The four namespaces remain separate. This acknowledged partial scope is not treated as a Standards violation.

Inspected supplied API and numerical-reference logs: 1 PASS/22.00s and 1 PASS/9.39s. Browser acceptance was still pending at assignment. No tests or network requests performed during review.

Standards findings: 0. Additional requested boundary findings: 0.
