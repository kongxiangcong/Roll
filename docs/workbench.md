# Terminal workbench

Open the existing application and select **工作台**, or append `#workbench` to its frontend URL. Use the existing documented installation/startup procedure; no new service is required.

The terminal has saved OHLC/volume and MA5/20, dark/light themes, collapsible watch/account panels, research/decision/history tabs, and an account dialog reusing draft → preview → explicit confirmation. Chart and NAV axes track their container size. Account quantities/cost change only through explicit account confirmation. Quotes update manually, or every five minutes while the opted-in page is visible; there is no unattended daily workbench scheduler.

Research accepts ordinary main-board symbols matching SSE600/601/603/605 or SZSE000/001/002/003. Symbol syntax is not proof of instrument identity or suitability; source and backtest checks may reject ST, suspended, missing or incompatible data. New quote symbols still require existing watchlist registration. Research persists source dates/material identity, partial results, idempotency and cancellation. Restarted orphan jobs become interrupted. It does not trade or write the account.

Historical SMA5/20 simulation is not model prediction performance or an independent validation. Historical CAL probability does not establish a current-symbol/current-date probability; the UI displays missing applicability. Model assessment uses the configured Codex service and may cost money. Full source data remains stored; model material is bounded, as recorded in its display scope. Formal authority remains NOT_GRANTED.

## Verification

Backend: `python -m pytest tests/test_assistance.py tests/test_card_workbench.py -q` from backend. Uses temporary ledgers and controlled providers/models.

Frontend: `npm ci`, `npm run build`, then `node scripts/workbench-smoke.mjs` from frontend. The smoke test renders the real compiled assets into an inline browser document with an in-memory fetch replacement and synthetic OHLC. It does not start a server or call live account/provider/model services. Chrome must already be installed (`ROLL_TEST_BROWSER` may select another installed Playwright channel). Tests cover viewport geometry, keyboard tabs/chart, task cancellation/state, account draft/confirmation, fold widths and missing-data/quote isolation. Output goes to ignored/local `.scratch/workbench-smoke`.

Implementation and limited independent source checks passed before publishing; the PR records checks rerun on its exact integrated tree. Native 200% browser zoom, true-origin theme reload and live-provider/model E2E were not validated in the restricted browser environment. Equivalent small CSS viewport and controlled storage were tested separately. No screenshot or fixture is investment performance.

## Next reliability acceptance

Before broader rollout, run one explicitly authorized ordinary main-board security through a budget-limited real-source → archived input → fixed backtest → bounded assessment → restart/readback cycle, with account read-only. Verify symbol/date/RAW units, completeness, latency, errors, cancellation and preserved partial results. Record a reproducible acceptance result rather than treating UI/mock success as live operation or probability qualification. Independent prospective statistical validity remains a separate requirement.
