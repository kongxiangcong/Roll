# Card workbench implementation checkpoint

## Completed code
- frontend/src/pages/card-workbench.tsx (new): fixed overview card, independent collapsible rails, selected-security research, real cancellation, guarded response identity, existing account edit/confirmation in native dialog, quote retrieval followed by valuation, opt-in visible-page five-minute updates.
- frontend/src/styles/card-workbench.css (new): scoped editorial-ui card hierarchy using existing green/neutral palette, focus treatment, narrow layout and reduced-motion policy.
- frontend/src/app.tsx: additive 工作台 entry and #workbench deep link.
- frontend/src/pages/sync-reconcile.tsx: optional initialMode only; existing confirmation contracts retained.
- backend/src/roll/runtime/assistance.py: supported mainland main-board A-share instrument, persisted idempotency, global exclusion, cancellation API support, transactional cancellation protection, instrument in history/material/source mapping, restart handling.
- backend/src/roll/agents/assistance_runtime.py: use material instrument instead of hardcoded company.
- backend/src/roll/app.py: additive cancel endpoint only relative to this task baseline.
- backend/tests/test_card_workbench.py: isolated contract regressions.

## Executed validation
- PASS npm run build: TypeScript plus Vite; pre-existing architecture still emits >500 kB chunk advisory, not a build failure.
- PASS 21 tests: test_assistance.py + test_card_workbench.py, 4.51s. No real provider/model calls.
- PASS 49 tests: application/test_account.py, test_reconcile.py, test_valuation.py, 355.90s. Temporary SQLite and test transports.
- PASS compiled-asset browser with in-memory fetch fixtures: 1440/1024/390/320 layouts, zero JS errors; fold/focus, double submission, real cancel-request UI, partial result, different security, late history response, preview no confirmation, preview and confirm 409 retention, cancel/discard, successful save, market-before-valuation, no implicit research/account writes.
- Browser direct local URL NOT_RUN: 127.0.0.1:5197 returned ERR_NETWORK_ACCESS_DENIED. No port/security workaround. Skill-authorized inline rendering used instead; about:blank UUID supplied by deterministic test fixture.
- Independent code/UI review: pending. This task does not claim independent acceptance.

## Boundaries
Single account; main-board SSE 600/601/603/605 and SZSE 000/001/002/003 research. Other boards not adapted. Source failures/ST restrictions can still prevent backtest. No current validated event probability or new predictive model. Quote latency/freshness displayed; no broker connection, real account writes, paid models, market collection, actual research, commit/push/deploy performed during implementation. No new package dependencies.

Account facts change only through existing explicit draft confirmation; quotes do not change quantities/cost. Main-board research selection is independent of quote watchlist registration; generic quote endpoint still enforces existing market identity/scope policies. Five-minute polling only when opted in, page open and visible; not an unattended scheduler.

Native physical IME/screen reader, real provider and model integration NOT_RUN. Browser fixtures are not market performance. Portable preview/Library final delivery remains pending independent review coordination.

## Reviewer baseline
Compare against baseline/ copies, not repository HEAD: backend app already contained user changes before this task. hashes.json records initial affected files. User daily-use and financial-observation changes not edited. Source line endings restored to LF to avoid unrelated diffs.
