# Spec review: lot and registered-scope audit

Reviewed own additions relative to `84d8736`: migration consumer/method, routes, UI and tests. Original SSE changes are excluded. No tests, network, main-profile operations, code edits or commits performed.

**[P2, closed] Per-frame position identity.** Targeted rereview confirms every observation now compares position_id with the original baseline binding; a new lot's expected position_id comes from its BUY order/lot ID rather than the observation being audited. The audit also rejects increases in a lot's remaining quantity. Fixed METHOD derive regressions replace a baseline identity, replace a new lot's first identity, and increase remaining quantity from 50 to 100; all report engineering inconsistency while G5 remains INCONCLUSIVE. [api-final.log](api-final.log) records 1 PASS/22.88s including the public positive/replay path. Archived source material is not modified by these negative fixtures. Open findings: zero. No tests rerun by the reviewer.

Other reviewed behavior matches the bounded scope:

- Original migration receipt fields, proposal/policy identity, initial quantity/instrument/deadline and effective session are read from immutable source material. New lot identity is linked to a BUY event and entry-plus-frozen-horizon deadline. Overdue blocked lots retain their original deadline and saved blocking reasons instead of receiving a new horizon.
- Scope/rule instrument sets and observed bar/signal/position instruments are checked. Registered but unobserved names remain separate; registration does not prove transfer to another security, market or regime. Empty initial positions are explicitly NOT_APPLICABLE for original-lot migration, not a positive migration case.
- Audit output distinguishes engineering inconsistency from G5 validity. It never simulates trades, modifies the original ledger, fits models, reads SEALED or grants real admission, independent support, complete freeze or qualification.
- Source manifest/input, method and original statistics bindings protect saved reads/replay. UI exposes each lot's timeline, migration activation and unknown scope-transfer evidence. The public test provides a positive blocked original lot plus independently timed new lot, idempotency, original-state/account preservation, later-frame-independent replay, nested corruption rejection and restart retrieval. Final browser/build checks were being recorded; no reviewer execution is claimed.

The proposed versioned engineering-completeness checker is feasible offline. It must bind actual consumer manifests and unfinished METHOD attempts, while retaining real authority, absent fitted neighbor artifacts and independent/forward qualification as separate unmet conditions.
