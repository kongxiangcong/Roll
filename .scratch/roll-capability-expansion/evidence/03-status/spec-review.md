# Spec review: status evidence and daily refresh

Reviewed committed range `4cfa76b2cd61e79ef7d2254cfb74b474b5a89c02..d279a0c551d96bb2e7dededd5f77d195aad06a12`. No code changes, commits, or tests performed. Preexisting P0/SSE producers are contract context, not reviewed changes.

## Finding

**[P2] Resolve the blank/current cutoff on the server.** `frontend/src/components/status-evidence-panel.tsx:15-16` turns “留空查询当前” into the browser clock's ISO timestamp; `backend/src/roll/market/status_evidence.py:9-10` rejects any timestamp ahead of the API host. For a mobile/browser clock five minutes ahead, the ordinary current query fails with `STATUS_KNOWLEDGE_CUTOFF_IN_FUTURE` even though the user supplied no future date. A slow browser instead silently queries an earlier snapshot. This affects [03's current-state user path / US-5](../../issues/03-status-evidence.md) and [spec ID-11](../../spec.md). Allow an omitted cutoff resolved once by the API host, return that resolved timestamp, and retain strict future/timezone validation for explicitly supplied cutoffs. Cover a skewed browser clock. This finding is derived from the committed code, not an observed production failure.

## Other checks

- Explicit naive/future API dates are rejected before reading saved observations. Each inherited reader filters `normalized_known_at <= known_by` and verifies archived receipts. The query preserves reported company facts and both suspension producers' top-level events; it does not convert listing descriptions, scheduled end dates or empty coverage into normal trading or confirmed resumption.
- Busy disables cutoff editing and repeat queries. Daily panels are remounted immediately when a parent mutation starts and disabled throughout it; old in-flight responses cannot populate the replacement panel. The committed refresh regression exercises clearing old results after a source mutation.
- Original hashes point to existing archived-source APIs. Recorded METHOD/API/browser evidence remains separate from inherited real-source evidence. Existing logs match the claimed two API passes and one browser pass; this review did not rerun them. Naive/future rejection is present in implementation, but not explicitly exercised in the two new API tests.
- [Acceptance](acceptance.md) and [03](../../issues/03-status-evidence.md) honestly retain partial status for effective enumerations, risk subtypes and complete negative coverage. Those documented remaining source gates are not hidden completion claims; no scope creep or false normal/resumption claims found.
