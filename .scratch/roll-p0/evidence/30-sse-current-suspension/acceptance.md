# Ticket30 fifth slice: fixed SSE specified-date suspension receipts

Completion remains **partial**; first Ticket30 acceptance criterion remains unchecked. Source implementation commit `60b4f31` adds one concrete source path and consumers. Accepted integration `133278d1f4b31dc9f88b05bedec1cb4642c6bfb5` was merged before final composition. No production review packet, frozen experiment or old source fingerprint was rewritten.

## Delivered boundary

`POST /api/research/collections/{id}/sse-suspension` captures a server Host-date query through the fixed official `COMMON_SSE_XXPL_JYTS_TFPXX_L` endpoint; there is no caller date/complete/REAL flag. Persistent source policy supports disabling this specific source. Every body is archived before HTTP/schema/identity/date interpretation. Metadata retains literal totals, page fields and date echoes even on refusal. Requests have a two-page ceiling, no retry/redirect, 15-second timeout and 8MiB per-body ceiling; an oversized body stores only a labelled incomplete bounded prefix and cannot become a source original or coverage proof.

`POST .../sse-suspension/check` persists a plan/date claim in genuine SQLite and returns the cached record on repeated triggers. The existing post-close worker source job invokes it once before the closing source path, records the linked receipt and gaps, and cannot increase the same-day request budget through repeat checks. Dead claims become interrupted with an explicit no-implicit-retry gap. No second scheduler or generic provider framework was added.

`GET .../sse-suspension-receipts`, source-gaps, current packet inputs, packet archive and the forward read consumer use the same validated originals. Packets freeze exact receipt IDs, including an empty list; later same-cutoff receipts cannot enter an old replay. Conflicting closing and suspension facts are both retained. Raw body, fixed JS, mapping and receipt corruption produce HTTP409; original request URL/parameters and literal metadata are checked against the bytes on read. Parser fingerprint changes require successors rather than re-certifying old packets.

A selected finite reported suspension preserves source security/page/row, start/end DATE precision, stop text, raw/JS hashes, actual receipt and normalized-known times. It never asserts actual resumption, publication/first availability, risk subtype, listing/relisting or ex-rights completeness. Empty, absent security, zero total, pagination truncation or unverified dates cannot create a normal state, no-events authority, complete status, forward admissibility, start clock or grant. Injected suppliers are explicitly METHOD with `system_usable=false`.

## Observed actual source, one anonymous call

The new isolated API-only runtime `.scratch/t30s-live` made exactly **1 call within the ≤2 page budget**, with no account setup (`version=0`), background worker, provider/model, registry, fitting, SEALED or grant action. Actual Host start `2026-10-11T08:14:02.157123+00:00`, raw receipt `08:14:05.619772+00:00`, normalization/finish `08:14:05.638633+00:00`; query `SEARCH_DATE=2026-10-11`. HTTP200 JSON original is **13367 bytes**, SHA `986c403e89bf4aab9f260034f1d301126daa0de9ff62926f90cf798768eeb958`, saved under `runtime/source-assessment/`. Receipt ID `3ed7b56f-1403-4c46-807b-7094893f3d43` remains `REAL_SOURCE_ASSESSMENT`/`REPORTED_PARTIAL`, `system_usable=false`, `forward_started_at=null`, `NOT_GRANTED`.

The response reports `pageNo=1/pageCount=1/pageSize=100/total=26`, and 26 rows. **`queryDate=""`, `pageHelp.searchDate=null`, no PRODUCT_CODE600362**. Reported start dates span 2024-10-28 through 2025-03-19; every reported end is `"-"`. They are open-ended scheduled records, not evidence of original publication, expiry, actual resumption or current applicability. Numeric total equality only describes this returned set. Exact date selection, current target state and full status coverage remain unknown; no second HTTP attempt was made, and this one response is not a claim that the endpoint permanently lacks current data.

`request-contract-audit.json` separately checks the exact pinned JS bytes: first `var suspension` block, URL line7, SQL10, uppercase SEARCH_DATE11/44, `yyyy-MM-dd` calendar26, page fields12–16 and rendering70–83. The actual query casing/date format match. JS default size25 differs from the **explicit fixed historical manifest GET size100**, whose historical response and this response both report100. This slice uses that previously captured anonymous JSON GET variant; the script's declared POST/JSONP transport is not reproduced or elevated into equivalent full front-end semantics. The separate newer `suspension_stock`/commonSoa route is not silently queried. No parameter casing/date format error was observed, but current filtering remains unproven.

## Verification lineage

| Stage | Actual outcome |
| --- | --- |
| New receipt API valid product RED | 1 failed / 5.96s (404) |
| Receipt vertical GREEN | 1 passed / 5.63s |
| Current packet binding valid product RED | 1 failed / 7.65s (missing fixed IDs) |
| First two receipt/consumer GREEN | 2 passed / 12.47s |
| Existing worker binding valid product RED | 1 failed / 8.43s (missing source receipt) |
| First worker GREEN attempt | 2 passed + 1 fixture assertion failed / 18.39s; all worker/cached-budget assertions passed, account baseline expected0 incorrectly instead of established1. Corrected to compare the captured public baseline; no product weakening. |
| Refused literal metadata valid product RED | 2 failed / 9.96s (missing reported metadata; selector matched date and echo scenarios) |
| Corrected receipt/worker/refusal GREEN | 7 passed / 39.09s |
| Fixed product source affected suite | **32 passed / 167.22s**: new17 plus existing post-close15. Two-page201/200, second-page target, duplicate target/changed totals, date/security/page refusal, four original dependencies, source disabled0HTTP, bounded incomplete byte prefix, conflicts, old empty IDs, immutable replay. |
| Added saved-real-raw offline/current forward read/mixed-history/ungranted caller | **4 passed / 22.00s**; saved real bytes are supplied as METHOD, no extra actual HTTP. |
| Final accepted integration route/worker/old obligation-ID/ungranted caller composition | **4 passed / 22.65s**. Previous stage counts are not summed into a new full-suite run. |

All test runtimes use own-tree PYTHONPATH and independent short `t30s-*` basetemps, the root venv and injected public suppliers. Escalated execution avoids the previously documented sandbox TestClient shutdown hang. No full unrelated suite, benchmark, OS failure rerun, browser or build was needed for this backend-only slice. Test and actual assessment processes exited before new bytewise preservation.

`source-live-before/after.json` and `source-composition-before/after.json` record source stability, the exact two manifest-named public originals, protected15 Git identities and original19 bytewise SHA `ec46257c4420f69c245791778c49079355700615cc3ed7b94d8027bd4dcf66c4`. No SQLite-open of original19 or old saved runtime occurred. Twelve newly owned runtime directories were copied only to `continuation-ticket30-sse-current-suspension`: **2717 files / 420677469 bytes / 0 SHA or length mismatches**. Exact records are in `runtime-preservation-manifest.json`/`runtime-preservation-receipt.json`. Prior13989/2570/2657/3048 preservation targets, original schedules and all frozen mappings remain untouched. Worktree is retained for independent acceptance.

## Concrete unfinished work

This is a delivered finite producer path, not complete production source coverage. [Next-slice.md](next-slice.md) separates the current stop/resume interval caller/parser, listing/relisting and risk authority, exact yunhq units/turnover, current action pagination and revision/cancellation/fulfillment reconciliation. Some exact official interfaces remain internally unadapted; others require additional primary schema or actual source evidence. The user notification configuration is irrelevant to those gaps. Current complete_action_coverage and pending_older_obligations_complete stay false, unresolved obligations stay UNKNOWN, no real forward begins and Ticket30 does not automatically unlock32.
