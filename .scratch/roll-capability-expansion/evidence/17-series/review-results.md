# Ticket17 two-axis review

User fixed point b4fb4407a9e6e91876f314ac9ad5bde7d0e7f35e; pinned implementation5a940ea39a087ebd32741ca4fdf9d84c71b76f91, current ticket increment0e4f412...5a940ea. Parallel read-only review using the already invoked code-review skill; inherited16 excluded from duplicate review. Original unrelated dirty files are outside the scoped commit.

## Standards

0 documented-standard violations,0 actionable baseline smells; no blocker. AGENTS/tracker/triage/domain/GLOSSARY/ADR0001 checked. Explicit BEGIN commit and idempotency double-check, append-only snapshots, model/rejection/association/grouping lineage isolation and successor membership epochs are consistent. Raw source integrity, actual classification availability, postclose/closed-day mapping, calendar gaps and METHOD/real provenance are retained. No account write or qualification elevation. Read-only review, no inference/training/source/account operations.

## Spec

Initial review found2 blockers. P1: representative selected by latest source receipt allowed a later old reprint to override a known correction. P2: the same selection could delay first consumption when original14:00 was reprinted15:01 and classified15:02. Both conflict with first consumption/event-version requirements and spec122. The reviewer checked ORIGINAL/REVISION/REPRINT behavior with the existing15 pure grouping function; no real model/source calls.

Fix: v2 collapses each exact content version to its earliest receipt, then chooses the newest distinct version. One targeted METHOD regression covers both trigger orders and old snapshot replay. Old v1 snapshots remain immutable. Final independent read-only delta review: both blockers eliminated, no new wrong behavior found; v2 and preserved v1 reads satisfy successor/history requirements. Spec may pass observation engineering acceptance once final checks and commit are fixed. Research limits/grants remain unchanged.

Standards:0 findings/no worst issue. Spec:2 initial blockers,2 resolved,0 remaining blockers. Targeted6 series tests passed45.96s; realv2 runtime04 zero model/HTTP calls and identical expected observations; Chrome recheck recorded separately. Final completion manifest binds the reviewed delta; no production enable or later ticket acceptance implied.
