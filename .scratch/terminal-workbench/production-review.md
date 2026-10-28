# Approved terminal — production integration checkpoint
Actual React/API work completed, not a static-HTML-only redesign. Five frontend files listed in production-evidence/hashes.json. Existing account draft/preview/confirm, quote-then-valuation and persisted instrument-bound research/idempotency/cancel/restart contracts reused. Full source OHLC source_id binding retained; historical NAV remains separate. Backend runtime unchanged against this continuation baseline: True. Earlier concurrent backend material/display_scope changes preserved.

Completed remaining gaps:
- Removed numbered kickers, repeated subheadings, tutorial/corner text. Preserved concise data dates, expired opinion, missing probability, errors and history-vs-account distinction. Model cost warning remains on demand under Run information before execution. No demo badge in real React UI; portable wrapper only has a short simulated-data badge.
- Added shared ResizeObserver chart sizing; both price and NAV SVG viewBox match actual pixel bounds. Independent P1 tiny-axis issue fixed: measured font-size11 * screen matrix1 =11 physical CSS pixels. Price and volume use separate areas; tight containers scroll locally.
- OHLC rejects blank/nonfinite/nonpositive input and invalid ranges rather than drawing zero candles; invalid volume omitted. MA5/20 computed only with sufficient valid rows.
- Drawer positioning now relative to content area, so it never covers task tabs. Explicit grid-column placement keeps main area nonzero after hide/drawer conversion. Draft and active task state retained.

Validation:
- PASS npm run build (tsc + Vite), bundle advisory remains.
- PASS current backend test_assistance + test_card_workbench:21 tests in4.18s; controlled dependencies. Earlier49 account/reconcile/valuation tests remain prior result, not rerun unchanged ledger.
- PASS terminal-regression: six viewport geometries, keyboard tabs/chart, task survives tabs/cancel, draft retention/confirm refresh, fold main width, missing data, unregistered selection quote isolation; zero JS errors.
- PASS terminal-readability: actual pixel axis measurements, controlled storage initial theme/write, themed dialog, mobile drawer and research action reachable. Inspected dark/light history and mobile screenshots.
- PASS contrast values from unchanged tokens: minimum5.07 for30 text/background combinations.

Limits and next step:
Independent targeted source/screenshot re-review pending. Direct file/localhost URL unavailable under prior browser restriction; no retry/bypass. Inline same compiled assets with fake transport is not live E2E. Native200% zoom and real-origin storage reload NOT_RUN;720x450 equivalent CSS reflow and storage substitute tested. No real account mutation, provider/model call, trading, push, merge or deployment. Final Library HTML not replaced while awaiting review; prior preview identities remain available.
