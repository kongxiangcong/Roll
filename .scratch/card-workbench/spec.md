# Card workbench with real account and research flows
Status: ready-for-agent
Mode: Integrate; visual_policy: redesign; skill: C:/Users/72449/.codex/skills/editorial-ui/SKILL.md.

User brief supersedes prior three-column prototype presentation: card hierarchy, fixed overview, separately collapsible rails, decision terminology, account editing and selected-stock research. Preserve contracts and unrelated changes. No production data writes, network research/model calls, broker connection, commit or deployment during implementation.

01 Research: supported A-share instrument, durable idempotency, global mutual exclusion, real cancellation, source/material/history identity and partial results. No new probability model; current probability remains unavailable.
02 Workbench: independent route with account/market/research cards; reuse confirmation ledger. Refresh market before valuation, label delayed/missing marks. Responsive and keyboard-accessible controls, preserve drafts and ignore stale responses.
03 Verification: temporary DB and providers/model substitutes; frontend intercepted fixtures; build/typecheck; desktop/narrow, cancellation, conflicts, duplicate submissions, partial failure, restart. Independent review remains separate.

Single account only. Unsupported providers/stock classes visibly refused. No simulated live results. Portable design preview is separate from real application.
