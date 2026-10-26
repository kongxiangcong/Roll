# Standards review

Reviewed only the uncommitted threshold-stress slice against HEAD `63200a2`: host/worker/method, own app routes, panel/integration and API/browser tests/config. Original SSE and unrelated changes excluded. Sources: AGENTS.md, domain instructions, GLOSSARY.md, relevant ADRs and the code-review smell baseline. Tool-enforced checks excluded. No tests, network or main-profile operations performed.

No actionable documented coding-standard violations or Fowler smells found. Original lifecycle findings, now resolved:

- **Original P2:** output-directory creation after START was outside terminalization, so an OSError stranded a live-owner RUNNING run.
- **Original P2:** two initializers recovering the same stale RUNNING snapshot could make the second fail startup when the first had already terminalized it.

The START row and per-rate events otherwise share one transaction before worker entry. Finish atomically records terminal events, run outcome and archive. The METHOD family manifest keeps `partition=null` and does not modify the original training-attempt table or claim a larger fit budget.

Numerical work is limited to the fixed three entry thresholds, with support and all other policy clauses preserved. Every saved base prefix must match complete original state. Network is denied; frame/span, timeout and input/output limits apply inside the bounded worker. Persisted readers check parent source and nested input/method archives; replay avoids new attempts or fitting. Unknown valuation and known risk failures remain distinct from computational success.

## Focused repair re-review

Both P2 findings are **resolved**. All post-START directory setup, worker execution and successful finish are now inside the terminalization try. Recovery uses `recovering=True`; under BEGIN IMMEDIATE, an already-terminal row returns without new events or archive rewrites. Explicit duplicate terminal transitions retain their conflict behavior.

Inspected the regression: a real file/directory conflict in the disposable profile produces three FAILED attempts, preserves one diagnostic on same-key retry, and restores the directory. A Barrier makes two actual service initializers inspect the same dead-host snapshot; both complete and the family records exactly three INTERRUPTED events. Existing training manifests remain equal, and unknown protocol lookup is now 404. Inspected `api-final02.log`: **1 PASS/33.38s**. Chrome final rerun was still preparing at re-review. No independent test rerun performed.

Final acceptance follow-up: inspected `browser-final.log` **1 PASS** (body42.8s; parent reports result duration63.94s) and `build.log` PASS. Together with `api-final02.log` **1 PASS/33.38s**, this closes the outstanding acceptance caveat. No test rerun or repeated implementation review performed.

Final Standards findings: 0. Open review/acceptance caveats: 0 within this slice.
