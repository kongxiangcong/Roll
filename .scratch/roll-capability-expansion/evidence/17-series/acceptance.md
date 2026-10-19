# Ticket17 acceptance — pending independent review

Dependency16 is complete at0e4f412, as limited research only. This slice reuses15 recorded event IDs and16 frozen saved classifications; no new inference, training or source HTTP. It does not change the16 model, object projection, reject thresholds or primary evaluation. Production default/grants/accounts remain unchanged.

## Delivered behavior

Public POST `/api/market/sentiment-series/{instrument}` registers an immutable snapshot; GET latest, `/snapshots`, `/source-runs` and `/runs/{id}` expose versions and replay. One reference/classification/rejection/association/grouping lineage per snapshot; later event bridges start a successor epoch. Binary neutral stays unsupported/null. Counts and proportions use unique new events including rejected events as denominator. Exact reprints increase visible source support without extra event weight. Revisions known by one checkpoint coalesce to the latest version once; later-checkpoint revisions appear separately. No composite sentiment index.

Registered observation checkpoint POST_CLOSE_1505_V1 uses Asia/Shanghai15:05 and supported15:00 source boundary. After-close/weekend/holiday information and classifications unavailable by the checkpoint move forward; unknown calendars/rule eras stay gaps. Snapshot creation is current and explicit: retrospective observation reconstruction, never an old forecast. Calendar/raw/reference/source-run fingerprints are preserved; source originals are integrity checked. Range92 days,366 complete runs and2000 unique saved facts bound each reconstruction. The existing research page exposes source coverage, class support, rejection, versions, cutoff/creation time, pending events and missing/nontrading states. Unverified provenance is visibly unverified.

## Actual saved-source reconstruction

`runtime03-freeze.json`, `run-real-series03.py`, `real-runtime03.log`, `real-runtime-summary.json`, `real-legacy-series.json`, `real-research-series.json`. Fresh complete isolated data copy `.scratch/r17-runtime03` includes original lifecycle journal; original legacy/modern DB SHA unchanged. Actual clock, no source or classification worker overrides, network0/model0, account version0→0; restart and idempotent public replay identical.

Legacy source run6da30e94-28d8-4889-b55c-dde74899b760:10 real archived events first consumable2026-10-19, positive2/negative0/rejected8, neutral unsupported. Old failed evaluation is inherited. New Chinese FinBERT rune35499f2-3cb6-445e-bfcb-b482ddee235e:12 archived events actually available/classified after today's close; all deferred to2026-10-20T15:05+08, no future counts. Its limited challenge-set quality flag remains distinct from natural-flow coverage. Current receipt is an observation reconstruction, not prospective collection, independent validity or a forecast archive.

## METHOD / checks

Pytest15 passed74.25s: new5 series tests plus old sentiment/research/evaluation compatibility. Fixed clocks and source/inference fixtures prove exact copies, revised source versions, revision coalescence, successor bridge epochs, model changes, missing/unsupported labels, postclose/weekend/holiday/calendar gaps, idempotency/conflict, restart and account isolation. `pytest.log`; no fake fixture is treated as real model performance.

Build passed3.42s, existing >500kB bundle warning retained. Chrome channel, independent complete copies/free server ports: real browser1 passed16.8s (18225/15225), METHOD browser1 passed12.9s (18226/15226). METHOD browser fixture explicitly uses fake clocks/worker; verifies3 unique events from4 sources, opposing-company direction, proportions, missing day, weekend and old-version replay. Real browser checks binary/three-class lineage selection, after-close deferred events, old-model quality limits and immutable API reads.390px pages have no horizontal overflow; desktop/mobile screenshots inspected. Evidence browser logs/JSON, `desktop.png`, `mobile.png`, `method-mobile.png`, METHOD preparer/receipt. No model POST from real browser and no account change.

## Failures preserved

Initial METHOD tests3 failed because explicit BEGIN transaction lacked commit; fixed with commit and full suite passed. Full first pytest log was accidentally overwritten after a wrong relative backup path; `pytest-attempt1-excerpt.txt` honestly preserves only observed failure excerpts and cause. Attempt2 full14-pass log retained. Initial runtime bootstrap omitted journal backups, causing duplicate lifecycle origin before any API build; failed directory/log/freeze retained. Successor02 copied complete journal and passed. Successor03 adds proportions/revision coalescence; previous02 reports retained separately and old snapshots never rewritten. First Chrome/build passed; final checks repeated after the targeted semantic/UI changes.

## Versions / remaining limits

Python3.13.12, existing FastAPI/SQLite/Pydantic/React/Vite/Playwright dependencies unchanged; no install. Series `sentiment-event-series-v1`, news association/grouping1, exact saved16 reference SHA per lineage. Protocol/attempt freezes record source file fingerprints. New source runs now explicitly save grouping/association metadata; accepted old runs inherit their recorded-v1 producer semantics.

Only actually saved sources are covered. No independent class effectiveness, complete feed, old forecast timing, return probability, policy dispatch, forward start, source authority or funds are granted.16 limitations and failed old holdouts remain.18/22 must separately deliver their slices.26 still requires02/03/04/05/06/07 and other named blockers. Standards/Spec reviews must pass before this ticket becomes complete.
