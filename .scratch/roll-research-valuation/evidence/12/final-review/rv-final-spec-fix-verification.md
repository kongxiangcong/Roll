# Spec P1 fix verification

Verdict: RESOLVED at implementation level; no necessary new finding in the requested repair boundary.

Reviewed only `a540302a8936bfd1c63ebd40ab1a4686b82cd88b...879e82d6`, the new candidate contract/runtime, integration seams, focused test source and saved evidence. No models, services, databases or tests were run for this verification.

The original missing path is now reachable through the ordinary report worker: `D:/dsh-proj/Roll/.scratch/worktrees/rv-review-fix/backend/src/roll/research/company/reports.py:529` invokes the valuation runtime before freeze and binds its resulting shared child snapshot at line534. `D:/dsh-proj/Roll/.scratch/worktrees/rv-review-fix/backend/src/roll/research/company/report_valuation.py:74` handles unvalued snapshots, prepares a bounded production CODEX candidate and applies it through `calculate_operating_valuation` at line71. This is no longer dependent on preconstructing a valuation through a separate API request. The existing05/04 service creates the model, deterministic result, controlled review and immutable shared child, which report freeze and daily consume.

The new host checks candidate snapshot/hash (report_valuation.py:40), rejects candidate-controlled snapshot/idempotency/parent binding (46–50), requires temporal/assumption audits and dated compatible numeric bridge/share anchors (52–63), exact bound cutoff (67), and adds an unavoidable conditional-verification limitation (70). Existing provenance, unit/currency, cross-company, applicability and economic checks remain the calculation authority. Purpose stays on the job; `D:/dsh-proj/Roll/.scratch/worktrees/rv-review-fix/frontend/src/pages/company-report.tsx:20` submits the explicit user choice. Candidate instructions do not replace host review authority.

Exact new execution command/output/source bindings are archived; post-execution preview reads the original command (`reports.py:253`), and backup validation checks the new run bindings (`D:/dsh-proj/Roll/.scratch/worktrees/rv-review-fix/backend/src/roll/research/company/analysis_integrity.py:110`). Old report/core/source archives are not rewritten by this path.

Saved METHOD evidence reports15 final targeted passes and covers new unvalued research, REFRESH, rejection, immutable history and restore. That supports engineering reachability only. A6/A7 actual new-source/new-model/browser acceptance and A8 natural post-close observations remain ticket12 work, with CURRENT versus baseline applicability kept separate.
