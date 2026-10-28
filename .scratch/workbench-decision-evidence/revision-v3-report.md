# Revision v3 — independent review corrections

Offline prototype only. Audit input: E:/workspace/codex/2026-10-28/task-2/roll-workbench-independent-audit.md and second review delivered by parent.

- Central fixtureFor() creates independent runStatus, probabilityG3, validationVerdict/reason, qualification, probabilityAvailability and backtest.availability.
- Zero signal: no trades, costs or unfilled orders; flat cash. Normal and negative scenarios: one buy and one full sell, zero ending shares. Detailed fees sum to 213.7707 for positive case; negative case costs 207.2862 and return -2.1872862%.
- Missing market and invalid MOCK-BT-v3 block every backtest-dependent numerical view. Invalid MOCK-CAL-v3 blocks probability, diagnostics and sample statistics. Source fixture remains a separate dependency.
- Event fixture specifies entry/exit, 20 sessions, RAW prices, dividends/equity handling, tax/slippage and unscorable rules. Single-event values and constant synthetic diagnostic cohort are identified; 0.50 selection threshold is consistent with all records in [0.5,0.6). CAL fitted diagnostics are not independent validation. Fixed 20-session block method and minimum 10-block requirement disclosed; only 5 blocks => insufficient.
- G2 candidate fee-stress FAIL leaves G3 INCONCLUSIVE and backtest available. Probability failures do not become a global qualification switch.
- Async requestDelayed() captures generation and selection epoch; receiveFixture() validates identity and applies the payload then renders. Controlled delayed responses are tested across security and state changes, and on normal acceptance.
- Correct index names: Shanghai Composite, CSI300, ChiNext. Research tab now has a report reading entry rather than duplicating overview.

Implementation browser verification: verification-v3.json, Chrome via existing permitted environment. Passed 10 targeted checks, zero JS errors, zero HTTP requests. This is not independent browser verification: the independent reviewer's file URL access remains policy-blocked and was not bypassed.

Remaining limitations: no API adapter; no market validation; fixture checkpoint NAV and benchmark summary are synthetic and explicitly labeled. Full benchmark trade ledger is not displayed. Real artifacts, account facts, model qualification, prediction interval and independent OOS/walk-forward remain unimplemented/unconnected. No Library uploads this revision, pending independent source re-review.
