# Ticket30 eighth offline price successor

Completion remains **partial**, first criterion open. Source commit `4cb7162342aaeaaf6c07d70b6da690075e8ece4d`; accepted seventh base870b451 and docs5827edfe merged before minimum composition. Only app routes and one specific price-successor module/test were implemented. Existing `post_close_packet.py`, company contract, old parser `cae8f942a6f95b138743c54fb24348987bf288b8d960658120acf3a28083a0fc`, old receipts/packet identities and fields remain unchanged. No generic provider/version compatibility framework.

Public POST `/api/research/collections/{id}/sse-price-quotes` accepts only source_receipt_id+basis. It verifies the existing source receipt and exact raw/doc dependencies, then appends a separately fingerprinted assessment. GET list/current reads only explicitly created known assessments. New parser fingerprint **11a8063025fe548fb1c996923be6c9f818d5e1dd74f47382ed145ecf73019de1**. Source known/received/available time stays distinct from derived normalized_known_at. Publication/effective/first historical availability and source timezone remain unknown; no backfill.

The saved actual409B raw SHA bc097123…92942403 yields exactDecimal last42.5100/open41.4500/previousclose41.8900/high42.6600/low41.0600. Turnover raw151 and fixed JS3736/3767/3802 ÷100 plus percent display gives exact1.51%; high-precision literal beyond float/display precision is preserved. Full original E110 and old volume/amount/fp/unit/phase facts are retained. Five prices must be finite positive; last/open are inside low-high; previousclose is separately previous-period and need not be inside today's OHLC. Missing/invalid/nonpositive/OHLC or refused source quote rejects409; a concrete non-object source500 was fixed to409. P1 preserves raw price evidence but withholds current quote display. Friday20261009/162905 is not Sunday current. Current-date METHOD display availability is not complete daily input, status or trading authorization.

Public POST `/sse-price-packets` requires explicit predecessor_packet_id/source_receipt_id/assessment_ids. It verifies the original predecessor via its original replay, requires that predecessor's source identity, and consumes only unique known assessments for that exact source. The saved PRICE_SUCCESSOR stores the full original predecessor, fixed IDs, exact quote facts and cutoff-specific quote states. Dedicated GET verifies originals and fixed replay; common replay dispatches only an actually saved PRICE_SUCCESSOR ID. Default old packet creation/query/replay does not implicitly change type or reinterpret old source fields. Same-cutoff later assessment, later unknown ID, duplicates/missing/other-source IDs and restart cannot reselect old packet inputs. `/source-gaps` appends a concrete price assessment/current view while original inputs and forward checks stay unchanged.

All successors retain `system_usable=false`, `model_daily_input_allowed=false`, `forward_admissible=false`, NOT_GRANTED/null actual forward start. Quotes are not DAILY/closing-price/session-complete authority. Listing/risk/fullphase/currentaction/old unresolved obligation gaps persist. Client complete/current/actual/system/cutoff flags reject422. Five scenario-owned archive dependencies damaged individually refuse new query/replay409 (snap, fixedJS, oldreceipt, newassessment, newpacket); old source/current packet remains byte-bound.

## Truthful test lineage

| Stage | Actual outcome |
| --- | --- |
| First public assessment valid RED |404:1 failed/6.55s|
| First green attempt fixture failure |1 failed/6.08s: new module METHOD clock was not aligned with source; not product RED|
| Fixture corrected assessment |1 passed/5.59s|
| Explicit consumer valid RED |404:1 failed/6.59s|
| New assessment+consumer |2 passed/12.75s|
| Finite quote/date/P1/precision/original-damage run before refusal repair |22 passed/104.33s|
| Concrete rejected non-object source valid RED |500:1 failed/5.95s|
| After repair: affected case,3date cases,unique/cross-source,exact409B,old/newpacket |7 passed/35.62s|
| Accepted582 composition: new current E/P1 plus existing fixed source-worker IDs and27 ungranted pause caller |4 passed/21.33s|

Counts are separate historical stages, not a claimed current full24-case rerun. Public application/genuine own SQLite/archive only; controlled MockTransport and clocks are METHOD, including replay of actual public bytes. No real collection was repeated. No OS/browser/build/unrelated fullsuite repeated.

## Protection, preservation and remaining frontier

`source-composition-before.json` and `-after.json` are identical: protected15 and all old source/reference Git identity, two fixed official documents317019B, named409B raw, unchanged old global parser, new source inventory. Original19 SQLite SHA ec46257…c66c4/165814272B checked bytewise only; no SQLite connection/account/old saved namespace opened. No actual HTTP/document fetch/Codex/DeepSeek/provider/fit/forecast/SEALED/funds/grant/actualforward or notification; no root index/docs edits, push or worktree cleanup.

New runtime preservation is separately recorded in `runtime-preservation-receipt.json` and exact SHA/length manifest; only the nine explicitly owned `t30q-*` directories in the new target are copied, including real REDs, the clock harness diagnostic and intentionally corrupted METHOD originals. Prior13989/2570/2657/3048/2717/2881/1577 saved namespaces are unopened and unmodified. Never SQLite-open the byte-preserved copies for independent acceptance: copy the necessary SQLite/WAL/SHM trio to a fresh independent directory first.

Remaining **internal** adapter/caller work: precise company dividend/send-share query requests and actual response-backed identity/pagination parser, fixed successor inventory IDs into consumers; revision/cancellation original authority IDs and lifecycle caller; full current status/risk/listing/relisting/exrights fields; session-complete daily quote/turnover scope. Corresponding **source proof gaps**: authoritative response schema/current date bounds/complete category inventory, effective status/enum semantics, first availability/corrections, confirmed cumulative session/closing meaning, all older pending obligations and actual fulfillment. Existing14 schedules and empty/finite past results do not prove these. User notification configuration is unrelated.

Next smallest concrete finite source plan is [next-slice](next-slice.md): only fixed JS action-query leads, offline literal contract then a separately frozen proposed two-attempt raw-first assessment, parser only after actual schema is saved. No request from that proposal executed in this slice; no currentcoverage/payment/entitlement/fulfillment inferred.
