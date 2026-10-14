# Standards review — 2026-10-14

Scope: `git diff f463dcb755c4785a6f07842aeb4231bb210f1010...7fc35604819edf821a81deae35a0606653c1cb79`; commit list inspected with `git log f463dcb..7fc3560 --oneline`. Also read the four owned, uncommitted UI files in `.scratch/worktrees/t25-input-settings/frontend/`: `src/components/broker-cost-panel.tsx`, `src/pages/settings.tsx`, `src/styles/funding.css`, and `tests/e2e/broker-costs.spec.ts`. This is a source review, not a new test run or acceptance of subsequent changes.

## Documented standards

No actionable violations found. Sources: `AGENTS.md`, `docs/agents/{issue-tracker,triage-labels,domain}.md`, `GLOSSARY.md`, relevant ADRs, and `.scratch/roll-p0/project-layout.md`.

Reviewed the actual broker-cost commands, persistence, estimator and action integration; policy successor registration, migrations, calculation and replay; action-window normalization, archive verification and forward consumer; API composition; associated application tests; and the UI confirmation/retry/history flow. Responsibilities remain in the prescribed decisions, research and market modules, with FastAPI composition and the existing five-page navigation. Decimal money handling, source/version binding, research/formal isolation and source-specific failure reasons match documented requirements. The browser test exercises the public application seam with explicitly synthetic input.

## Judgement smells

No actionable baseline smell findings. All twelve supplied Fowler heuristics were considered. Ordinary functions, Pydantic commands, concrete SQLite persistence and public owner queries serve present callers; the change does not introduce speculative layers, generic workflow infrastructure or competing frontend business rules. Revalidation at capture/publication/query/replay is required by the documented correctness boundary and was not treated as duplicated internal validation. Existing composition patterns and immutable raw evidence CRLF were not reported as new defects.

Standards findings: 0 documented violations, 0 actionable judgement smells. No code edits, tests, HTTP requests, production SQLite access or provider calls performed for this review.
