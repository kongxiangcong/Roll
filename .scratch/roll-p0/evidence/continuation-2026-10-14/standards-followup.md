# Standards follow-up — 2026-10-14

Scope: `git diff 1041842...a23a808cd0a6cf6a99bfd6a1f1f95bfa1060cf2f`, focusing on the second policy slice integrated at `92ca6dd8a3be7fc3ff6ddf0c15af99bdc65722b8`. Earlier broker-cost, action-window and UI changes are covered by `standards-review.md`. Read `successor_shadow.py`, the added-lot evaluator delta, routes, both application test files, acceptance/plan material and the owned evidence preservation helper. No tests, HTTP, SQLite or provider calls performed.

## Documented standards

No actionable violations found against `AGENTS.md`, `docs/agents/`, `GLOSSARY.md`, relevant ADRs or `.scratch/roll-p0/project-layout.md`. The new module remains under research and owns a concrete separate METHOD ledger. The existing policy calculator and fee calculator are reused; ACTUAL ledger mutation and formal qualification remain outside this service. Commands use the existing Pydantic boundary, cash uses Decimal, and the concrete SQLite writer retains immutable/versioned freeze, frame and replay records. Public application tests use isolated SQLite and explicitly synthetic samples rather than production data. The preservation helper is a local evidence operation on its owner's identified METHOD directories, not production configuration.

## Judgement smells

All twelve Fowler heuristics were considered; no actionable findings. Lot state and inherited frozen design represent present requirements rather than hypothetical framework needs. Repeated execution-support and binding checks occur at distinct financial/state boundaries; the repository explicitly requires those checks. The nested execution routine shares simulation state for current buy/sell callers without introducing a generic engine or wrapper hierarchy. Idempotency and replay shapes follow existing concrete persistence conventions. No speculative extraction or private cross-module implementation access needs to be introduced to satisfy this review.

Standards findings: 0 documented violations, 0 actionable judgement smells. This does not establish economic/statistical validation, complete-experiment freeze or production eligibility; those are separately recorded implementation/spec boundaries.
