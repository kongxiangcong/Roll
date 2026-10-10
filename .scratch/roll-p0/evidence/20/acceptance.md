# Ticket 20 — complete protocol and continuous shadow

Date: 2026-10-11 (Asia/Shanghai). Starting integration: `eabc7a3ae3462821bedc80c2d6c8b2a88d04b19c`.

## Scope and evidence meaning

This delivery implements immutable full protocol bindings, deterministic constrained policy, a separate continuous ledger, matched continuous comparators, and independent account-conditional diagnostics. Tests use the approved FastAPI entrance, real SQLite and isolated content archives. The financial tax example additionally uses the narrow arithmetic seam allowed in Testing Decisions §2.

All generated training and shadow fixtures remain METHOD_CASE. No production `.roll-data`, credentials, protected SEALED input, real research-family fit budget or actual forward start was consumed. Executable statistical arithmetic validation does not verify real sampling assumptions. FITTED_UNVALIDATED remains distinct from a full protocol freeze, independent validation, and formal qualification.

## Primary acceptance

| Scenario | Input and expected result | Actual evidence |
|---|---|---|
| AT-39 | Historical simulated BUY/SELL with positive or negative PnL must never enter actual account returns | `test_continuous_joint_budget_replay_and_actual_backfill_do_not_reset_shadow`: separate SQLite projections; actual account updates leave the entire saved shadow response byte-for-value identical; browser account remains version 0 |
| AT-62 | User inverse SELL, late old trade, actual fee resolution and correction update mirror while keeping saved shadow state/history | Same test confirms baseline, inverse SELL, FEE_ADJUSTMENT and CORRECTION through account draft/confirm endpoints, version advances to 4; existing shadow stays unchanged, including after host recreation |
| AT-63 | Overlapping opportunities cannot both spend the same budget or be summed as strategy wealth | Two same-day forecast records sort deterministically, one BUY and one overlap refusal; canonical logical key retains equivalent-event identity. New baseline 5000 refuses both as insufficient joint cash; cash remains 5000. Continuous curves are separate from mature counterfactuals and account snapshots |
| AT-74 | Changed baseline creates linked successor, never resets or concatenates prior performance | Frozen protocol mutation/attempt rejected. A linked successor reuses its explicitly linked frozen model without a new fit, saves a distinct full freeze and distinct shadow revision. Parent shadow remains revision 0; no forward clock starts |

## Frozen bindings and reproducibility

The complete record binds model/calibrator/features/input/data/model-code hashes, policy/rules/fees/daily execution and missing assumptions, preregistered G5, formal monitoring, complete design, executable statistical code, worked numerical method results, all linked-family attempts, baseline and cash-flow policy. Missing submitted fingerprints/attempts, unknown cash, incompatible scope and frozen mutation fail. Artifacts are content-verified before binding. Attempt IDs are rechecked under the SQLite write transaction. Statistical/code bindings are independent of the unchanged upstream ticket19 model-code fingerprint.

Continuous policy reserves an observation-based upper-band price plus fees before allowing another order. Execution uses next open, explicit daily price window, Decimal fees/tick rounding and later 20-session close. Missing or blocked exits retain inventory and coverage gaps. Distributions follow frozen record/payment dates; sale tax is deducted once, unpaid receivable remains gross. The independent literal tax example yields cash 99760 and receivable 200/NAV 99960 after selling before payment; later cash becomes 99960 without a second tax deduction.

Every opportunity preserves its selected or refused reason. Mature rejected outcomes remain HISTORICAL prediction diagnostics and do not create model losses or enter the SHADOW NAV. CASH, START_HOLD and MA5_MA20 have separate continuous cash/inventory/valuation traces under the same starting baseline, rules, cost scenarios and budget. These descriptive curves are not independent evidence of model value.

## Verification

- Red/green: absent freeze endpoint returned 404, then complete binding test passed. Absent continuous entrance returned 404; source binding and Decimal defects were corrected before its green result. Frozen-attempt mutation initially returned 201, then was rejected as 409. Statistical bindings have separate preserved red/green logs.
- Scoped API output: [api-tests.txt](api-tests.txt). Upstream model/protocol regressions: 15 passed in 83.29s, [upstream-tests.txt](upstream-tests.txt).
- Executable statistics acceptance: [statistics-red.txt](statistics-red.txt), [statistics-green.txt](statistics-green.txt), [statistical-method-notes.md](statistical-method-notes.md).
- React TypeScript + Vite build passed.
- Actual React/FastAPI browser flow: [browser-tests.txt](browser-tests.txt), [four namespace screenshot](shadow-isolation.png). Freeze, archive a historical opportunity, advance, save one account snapshot diagnostic and offline replay; no formal execute control; five navigation entries preserved. Screenshot visually reviewed for legible namespace separation.
- The stopped final METHOD browser runtime is preserved outside the disposable worktree at root `.roll-data/implementation-evidence/20/browser-method-final`: 312 files copied with SHA256 and byte-length equality verified by the merger. Its manifest is recorded in `evidence/continuation/browser20-profile-manifest.json`; this keeps the full protocol, saved inputs and SQLite state available for independent replay after cleanup.

No real forward observations, independent CAL validation, strict historical PIT, G1—G7 PASS, capability grant, or investment advantage is claimed. Confirmation and forward consumers still require their independently admitted inputs and maturity/independence evidence.

## Contract for tickets 21 / 25 / 27 / 30

`POST /api/research/protocols/{id}/complete-freezes` creates one immutable complete record per protocol. `GET /api/research/complete-freezes/{id}` retrieves it. This is distinct from the legacy incomplete `/freeze` refusal, which cannot stand in for an actual complete record.

`POST /api/research/shadow/{freeze_id}/advance` consumes `through_date`, all newly archived `forecast_ids`, and `expected_revision`. The current HTTP adapter intentionally admits only the model's frozen historical CAL window; dates and predictions cannot be backfilled into an already processed prefix. `GET` returns the latest full state and `POST .../replay` recomputes from saved inputs with zero networking. `GET /api/research/results?freeze_id=...` separates ACTUAL/HISTORICAL/SHADOW/ACCOUNT_CONDITIONAL. Conditional commands save an account snapshot and deterministic diagnostic decisions without changing a shadow revision or creating execution intent.

Conditional valuation uses the single submitted observation date, refuses mixed dates, and saves the historical price date/RAW inputs separately from the current account snapshot recording time. Missing conservative available cash remains a refusal, not the account's total balance interpreted as spendable money. The complete protocol archive hash, archived content binding and protocol fingerprint are checked at the query/consumption boundary; corrupted original protocol refuses advance before a new shadow revision. Empty zero-cash/no-holding baselines are refused because continuous-return NAV has no valid positive denominator.

The reusable pure `simulate(frozen, inputs, forecasts, through_date, comparator=None)` takes immutable full-freeze data plus admitted archived facts/calendar/optional statutory schedules and cash events; returns constrained continuous events, all opportunities, holdings, cash, receivables, coverage gaps, valuations and exposure curve. Ticket21 must admit its confirmation partition separately and feed the admitted immutable input to this function, preserving the frozen code. Ticket30 must admit and archive real future forecasts through its own future input entrance; the current CAL-only model forecast API is not a real forward entrance. Public advance does not read SEALED or create a future clock.

`calculate_policy(...)` is the ordinary deterministic action/refusal calculation for ticket25; formal authorization and execution gates remain its responsibility. `statistics.py` exposes frozen `method_manifest`, `paired_block_interval`, `probability_summary`, `continuous_summary` and `fingerprint`. Probability consumers should pass `opportunity_key` as the canonical key; repeated forecast IDs cannot inflate effective support. G5 neighbor fitting retains the existing five-fit/one-CAL family budget; insufficient evidence stays INCONCLUSIVE. Monitoring descriptions/thresholds/checkpoints, frozen feature/input dependencies and their hashes are available to ticket27; this ticket does not manufacture long-term monitoring observations.

## Layout

One concrete `research/shadow.py` ledger/policy implementation and one used numerical `research/statistics.py` module, FastAPI commands/queries, a research-page component and key tests were added. No DSL, strategy framework, generic repository, extra package dependency or external service was introduced.
