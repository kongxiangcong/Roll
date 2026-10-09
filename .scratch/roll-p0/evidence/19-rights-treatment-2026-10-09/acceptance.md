# Ticket19 source-bound cash-rights slice

Completion: partial (substantive deterministic rights processing delivered; complete action/status coverage and real training remain outside this slice).

## Scope and actual evidence

Started from integration1bf2260 in isolated managed worktree; created codex/ticket19-rights-treatment. Existing integration files and private operational data were not read or modified. No actual database, credentials, sealed input, labels, fitting or calibration accessed.

Fourteen actual issuer cash-distribution implementation PDFs for SSE:600362,2013—2025, were copied from the pre-exposed public inventory after length/SHA256 verification. Every previously selected page extract was compared byte-for-text with pypdf extraction of the actual PDF. Required raw notices are deployment references, not annual-report predictor inputs. Three previously archived MOF tax originals were verified and copied; full SHA/publication versus receipt metadata remain in sources.json.2024/2025 differentiated listed-share ex-reference deductions are distinct from ordinary eligible-share gross dividends; no dividend is assigned to issuer buyback accounts.

Live official source inspection corrected an unsupported30/365-day recollection: the2012 official Q&A uses natural calendar month/year, acquisition through disposal's preceding day. Actual Shanghai STA original (34244bytes, SHA256 dd8f61c32cf67a0fe73762df48751001fdfd4a0c67ded660cf5c4f03c8631a5e) was retrieved2026-10-09; its displayed publication is2012-11-20 14:59, preserved as DATE metadata plus display clock, never converted into independently proved historical availability. Its worked example confirms May24 purchase/June24 disposal still<=one month, June25 medium tier. URL: https://shanghai.chinatax.gov.cn/zcfw/zcjd/201211/t400944.html . STA national full-notice URL returned403; retry failure bytes/hash and successful request/receipt records are in ignored .roll-data/retrieval.json. Initial403 before the preserved retry is observable in tool output but not counted as an archived original. Fourteen PDFs plus four official tax HTML sources total18 unique deployment originals.

## Contract and boundaries

POST /api/research/cash-rights/assess accepts instrument, entry_date, exit_date, positive strict-integer quantity, timezone-aware consumer_cutoff, and optional fixed FRESH_DOMESTIC_INDIVIDUAL_NEXT_OPEN lot_scenario. It is an explicitly retrospective known-event calculation, not an account ledger, historical predictor or caller-supplied proof switch. Direct integration: assess_cash_rights(CashRightsCommand(...)) in roll.research.corporate_actions.

Entitlement requires entry<=record_date<exit for the next-open fresh lot. The2015_101 regime applies to registration dates after2015-09-08; earlier registration retains2012_85 irrespective of later disposal. Tax uses natural-month/year anniversaries inclusive,20%/10% and old5% versus new0% long-holding rates. Undefined Jan31/Feb29 anniversaries remain tax-unknown, with an actionable blocker; no unverified endmonth clamp. Deterministic per-lot fen HALF_UP is explicitly a study rounding scenario, not actual broker settlement.

Response events expose gross_entitlement_yuan, final_tax_yuan, net_economic_entitlement_yuan, initial_payment_withholding_yuan, supplementary_tax_liability_yuan, cash_paid_by_exit_yuan and net_receivable_at_exit_yuan. Gross entitled cash and listed-share ex-reference deductions remain separate. Payment after disposal remains a net receivable; source DATE payment on disposal day does not prove spendable cash at NEXT_OPEN (INTRADAY_UNKNOWN). Supplementary tax collection clock and actual user receipt are NOT_ESTABLISHED. Source originals received after consumer_cutoff are omitted with explicit blockers; this wall-clock evidence-consumption condition does not prove/refute past public availability. Publication DATE, actual2026 receipt and historical_prediction_admissibility=NOT_ESTABLISHED remain separate.

Every response is scorable=false and coverage=INCOMPLETE for supported issuer (UNKNOWN outside scope), because the14 known cash events do not prove all actions/rights/splits or all daily status. No zero-action certification or production qualification. Host verifies pinned manifest and18 raw bodies by SHA256 and byte length on each call; modified/missing evidence yields409. Account unchanged and query restart gives identical structured result with code/source fingerprints.

## TDD and validation

Agreed seam is the project-layout/spec FastAPI application boundary with real isolated SQLite and archived reference sources; no unit-only financial substitute.

- First tracer: registered2013 gross50/tax10/net40 receivable before payment; red404, green1 passed.
- Missing reference: red500, green409 actionable integrity failure.
- Exchange-timezone boundary: red422 for valid Shanghai date represented in prior UTC day; fixed and green in combined run.
- Cent conservation: red supplementary0.08 versus expected0.07; quantize initial and final separately, green1 passed.
- Additional cases: record-close entry/exdate ineligibility, raw0.60 versus exref0.5970, payment date ambiguity, natural-month/year tiers, earlier policy at later disposal, unknown anniversary, unknown instrument, invalid quantity/naive cutoff/trust toggle, raw/manifest tamper rejection and restart replay.

Combined earlier8 rights tests plus4 metadata preflight tests:12 passed in61.20seconds. Final rights/preflight regression:14 passed in66.62seconds; result in test-results.txt. Tax publication DATE metadata was then made explicit and re-pinned; the actual-document receipt below rechecks all18 bodies after that metadata-only edit. Engineering scenario dates/lot quantities are not actual trades or trained research evidence.

No new dependencies, abstract framework, schema migration, persistent ledger or approval workflow; one concrete research module, one endpoint, source references and one application-test file. Ticket19 overall remains needs-info/partial;20 not unlocked. Further complete historical action/status and continuous PIT price coverage remain required before any real training attempt.

## Actual public-original application receipt

[Executable receipt](actual-public-original-receipt.py) uses only packaged actual18public originals plus an empty temporary SQLite application. Current timezone-aware cutoff is the calculation receipt time. Two explicit study scenarios (100shares,2013-07-22→2013-08-01 and2024-07-22→2024-07-25) produce known-source gross/tax/net40 for2013 and gross-per-eligible-share0.60 versus listed-share ex-reference0.5970 for2024. Full structured source-bound responses and raw checks are in [receipt JSON](actual-public-original-receipt.json); known events are CALCULATED while aggregate coverage remains INCOMPLETE/scorable=false. No actual personal trade/account, trained model or historical predictor evidence is implied.

Before/after account and capabilities are equal; protocol list remains empty. External connections are rejected at socket boundary; Windows asyncio's OS loopback socketpair is explicitly logged and allowed. An initial attempt blocking all connects failed before TestClient startup because Windows uses loopback for that internal pipe; the successful receipt reports this distinction. No HTTP/provider fetch during calculation, no fitting, no SEALED routes requested. Script AST parses and script fingerprint are saved in JSON. Root will verify same-code regression/full suite after integration.

Ignored source-retrieval originals must be preserved before managed worktree cleanup; [preservation inventory](ignored-preservation.json) records exact paths, lengths and SHA. No raw private fixture or database is included.
