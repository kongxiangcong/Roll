# Ticket30 sixth slice: new-stock interval producer and finite source plan

Ticket30 remains **partial**, first criterion unchecked. Source commit `018536c042bc7f858bfcb8708b06bb759dd77e00`; accepted integration `6bb32bab8302183a3bfe6612d9034557feb169e6` merged before the four-case composition, followed by newly accepted27 integration `77f729f6dce6114aefc4e53ed7697581de28aa1d` and three related caller checks. New code is one specific `StockSuspensions` module for the pinned SSE new-stock client, not a generic provider/scheduler/lifecycle framework. Old actual receipts/source fingerprints/frozen mappings and qualification are not rewritten.

## Concrete delivery

Public `POST /api/research/collections/{id}/sse-stock-suspension`, GET its `-receipts`, and POST its `/check` use fixed JS32fc98 and named historical empty15a118 dependencies. Source policy supports independent disable and bounded health/cooldown. The caller archives a Host-clocked server-built capture plan before HTTP, then one TRADEDAY/bizDate query; only one unambiguous valid reported beforeTradeDay may determine the explicit600362 interval through actual Host date. The client-supported three-year range is an interface bound, not a new research/checkpoint horizon. Missing/future/unsupported date is refused with no current-date or old-route fallback.

The independent budget is **trade-day1 + interval≤2 = actual attempts≤3**, no retries/redirects, timeout15s and decoded body≤8MiB. Every available body is archived before HTTP/schema/date interpretation. Streaming failure/oversize retains only labelled incomplete received bytes and a refused receipt. Literal SQL/page/total/date metadata survives refusal. Identity, row interval, pagination size/no/total stability and duplicate events are checked. Requested dates, reported event dates and receipt/normalized-known times are distinct; report end date never proves actual resumption. Schedule events retain opaque type/control/time/reasons and unknown end precision. `suspension`, actual resume, risk/listing/exrights/current full status remain UNKNOWN, not client-signed pass flags.

Genuine SQLite plan/date source jobs cache results and interrupt dead owners without hidden retries. The existing post-close worker invokes the new job separately from old date/closing source budgets. Source-gaps exposes specific receipts/jobs/gaps. Current inputs, packets and the forward read consumer share verified raw dependencies; packets freeze exact new IDs, including empty/nonempty lists, and never reselect after same-cutoff append. Damage to trade-day/page/JS/mapping/reference-empty/capture-plan/receipt archives refuses query/replay409. Whole normalized receipts and request URL/parameters are checked against originals. Successor fingerprints are required when producer code changes.

## Actual finite outcome

Pre-capture plan `finite-execution-plan.json` SHA **ade9be5caeef8f3bf61e09043d17e07f3ecbe5321e98a79ce503ac5da226186c**, parser **075f4cb1f82fafe96d4da833c80b10bafe1893899def0e786ff52ecbd723f7b8**. The server capture-plan archive is SHA **bd683675fed06a84d38bf2a86bd32352c0c4b52321e55c830f2965a251a56258**, created before raw responses and bound to receipt `798e5acd-344f-47eb-afb7-ff7a33b2e44c`/collection `b3ea23a2-7d0a-4825-b4d5-fdc7ade2b302`.

One fresh API-only `.scratch/t30i-live` assessment used **2/≤3 calls**, then stopped without further attempts. Actual Host start `2026-10-11T09:20:35.730578+00:00`; trade-day received `09:20:36.046535+00:00`; interval received `09:20:36.092172+00:00`; finish/normalized-known `09:20:36.112711+00:00`. No account setup, account version0; no background scheduler, provider/Codex/DeepSeek/ntfy, training/forecast/SEALED/registry/grant/funding/real-forward action.

| Actual official original | Request and literal response |
| --- | --- |
| TRADEDAY SHA **f45a2a21a972c1150d69db7a60e8506932974bc1bdd216d3f6d052a5cdc7fc22**, **599bytes**, HTTP200 | commonSoaQuery.do/sqlIdGW_PL_JYTS_TFPXX_TRADEDAY/bizDate20261011. Single result beforeTradeDay`20261009`; extra lastTradeDay`20261015` is retained only in raw and has no adopted meaning because the pinned client consumes only beforeTradeDay. queryDate blank/searchDate null; latest trade-day authority remains unverified. |
| Interval SHA **7fd45879b5af75c7e0cb7f4c92ce9ad6fa31ddca8ad472deb83b66f3bbfd1c6f**, **481bytes**, HTTP200 | sqlIdGW_PL_JYTS_TFPXX/productCode600362/startStopDate20261009/endStopDate20261011/keyWords empty/isPaginationtrue/pageSize25/pageNo1. result[]/data[]/total0/pageCount0/beginPage0/endPage null, date echoes blank/null. No second interval page requested. |

This differs from the fixed historical empty response, whose total10/result0/request-size100/response-size1000 remain an independent historical gap. Neither empty return proves normal, absence of events, current full coverage or actual resumption. Actual receipt stays `REAL_SOURCE_ASSESSMENT`/`REPORTED_PARTIAL`, latest_trade_day_verified=false, system_usable=false, complete_status_verified=false, no_event_authority=false, forward_started_at=null and NOT_GRANTED. No second actual run was made.

The fixed script's actual new-stock keys/casing/basic date formats and page-size25 are used. Its declared POST/JSONP transport is not replicated: anonymous JSON GET is based on the already saved exact commonSoa GET manifest variant; equivalence to the full front end is not claimed. Only actual declared fields were adapted; no inferred alternate endpoint or meaning for lastTradeDay.

## Test lineage and scope

| Stage | Actual result |
| --- | --- |
| Receipt valid RED→GREEN | 404:1 failed/5.17s → 1 passed/5.25s |
| Fixed packet IDs valid RED→GREEN | missing stock receipt IDs:1 failed/6.40s → 2 passed/10.82s |
| Initial bounded contract/refusal/dependency checks | 16 passed/75.30s |
| Server finite-plan audit valid RED→GREEN | missing capture_plan:1 failed/5.87s → plan + two existing worker callers3 passed/19.28s |
| Stream interruption valid RED | observed prefix lost:1 failed/5.40s; corrected to archive received prefix/original_complete=false before propagating ReadTimeout |
| Fixed product source appropriate affected tests | **24 passed/112.43s**:19 new source scenarios +5 direct worker/current consumers, including fixed empty mismatch, wrong dates/security/page/interval, seven damaged dependencies, budget3, disabled source, explicit caller flags, interrupted prefix and current packet/read seams |
| Added saved actual two-body offline replay/current consumers | **3 passed/18.84s**, suppliers explicitly METHOD; old nonempty IDs survive append, no actual HTTP |
| Final merged route/existing-worker/old-obligation-ID/ungranted caller composition | **4 passed/24.10s** |
| Subsequent accepted27 composition | **3 passed/18.63s**: saved actual originals/old nonempty IDs, existing bounded source worker, and ALL_MONITOR pause preserving facts/backup; no actual qualification or external request |

Counts are separate actual stages, not a sum asserted as a new full-suite run. Source fingerprint stayed fixed across actual capture and subsequent offline/merged composition. Own PYTHONPATH, `-B`/PYTHONDONTWRITEBYTECODE, short independent t30i basetemps, real SQLite/archive and approved METHOD suppliers were used. No unrelated40/full suite, OS failure rerun, browser/build or numerical benchmark was needed. Own test/assessment processes exited before preservation.

`source-live-before/after.json`, `source-composition-before/after.json` and `source-composition27-before/after.json` prove source stability at their respective stages, protected15 Git identity/no reference diff, exact two named fixed originals (39627+483bytes) and original19 bytewise checksum **ec46257c4420f69c245791778c49079355700615cc3ed7b94d8027bd4dcf66c4**. `git-original-identity.json` independently confirms both actual raw Git blobs retain exact SHA/length. No original or saved SQLite connection; no old preservation namespace read/write. Twelve new own runtime directories are preserved only under `continuation-ticket30-sse-stock-suspension`: **2728 files/375082862 bytes/0 SHA or length mismatches**, with exact paths in the manifest. Accepted27 composition has its own append-only target and separate manifest/receipt; it does not overwrite the twelve-directory manifest. Preserve all earlier13989/2570/2657/3048/2717 targets unchanged. Worktree retained, no push or cleanup.

## Remaining internal frontier

The accepted27 append namespace `continuation-ticket30-sse-stock-suspension-composition27` contains **153 files/20080223 bytes/0 SHA or length mismatches**. Sixth total across these two new targets is **2881 files/395163085 bytes**. Both test native processes and preservation helpers exited; no own background service remains. The original twelve-directory manifest was not overwritten.

[Next-slice.md](next-slice.md) lists exact unfinished consumers/source requirements: full stop/resume lifecycle and negative coverage, current yunhq units/turnover/date completion, listing/relisting and risk subtype, current action pagination/revision/cancellation and fulfillment/old obligations. Official600362 company HTML and its explicitly declared relevant JS are the next bounded discovery/adaptation entry; labels or generic rules cannot substitute for endpoint transforms. Do not mark internal callers/parsers complete merely because this finite observed return is empty, or blame user notification configuration. The first acceptance criterion remains open, complete_action_coverage/pending_older_obligations_complete remain false, no real forward clock or formal capability starts.
