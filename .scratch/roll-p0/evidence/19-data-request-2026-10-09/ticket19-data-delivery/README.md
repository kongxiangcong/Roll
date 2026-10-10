# ticket19-data-delivery — SSE:600362 external evidence package

    Generated: 2026-10-09T16:30:55.576261+00:00
    Delivery status: **PARTIAL_DELIVERY**
    Qualification decision: **HOST_REVIEW_REQUIRED**
    Window status: **COLLECTION_CANDIDATE_NOT_PREREGISTERED_DEV_CAL**

    ## What this is

    Raw, traceable external evidence for the Jiangxi Copper A-share (`SSE:600362`) used by ticket 19.
    It contains **no model fit, no labels, no window selection, and no recommendation**. Raw is not proof of
    point-in-time availability, and this package does not claim it is.

    ## Read this before using the data

    1. **No point-in-time guarantee.** Every bar is `evidence_class = CURRENT_QUERY_ONLY`. It proves the values
       exist *now*, not that a given version was public before any prediction cutoff. `historical_availability`
       coverage is 0.
    2. **`RAW` means unadjusted.** Prices are exchange-reported, not adjusted for splits/dividends.
    3. **`reported_preclose` is null everywhere by design.** Sohu exposes no preclose column. A provider preclose,
       where it exists, may be an **ex-rights reference price**, not the prior RAW close. Do not reconstruct it
       from adjacent rows.
    4. **Two independent sources carry the bars.** Sohu (volume in `手`, amount in `万元`) and Wind (volume already
       in 股, amount already in 元). The delivered `volume_shares` / `amount_yuan` conversions are now validated on
       1916 overlapping dates, not one. Original units are preserved in `original_units`.
    5. **Suspension days are typed, not traded.** The 8 Feb-2016 rows from the second source are
       `row_kind = SUSPENSION_PLACEHOLDER` with a FROZEN price and null volume/amount. They are not observed bars.
    6. **Absence is not NORMAL.** `security_status.jsonl` has an explicit coverage note. A missing status row
       must not be read as normal trading, and ST must not be inferred from a missing ST field.
    7. **Missing bars are still reported honestly.** After the second source closed 29 session dates,
       exactly 1 session date has no bar from either source (2018-12-31, shown to be a
       holiday). No bar was invented to make the series look complete.
    8. **Corporate actions are not a complete catalogue.** Both sources are individually sourced rows; the status for
       any year not listed is `SEARCHED_NO_HIT`, never `EXPLICIT_NO_EVENT`. The second source adds base shares and an
       explicit null bonus/capitalization ratio.
    9. **Broker commission is UNKNOWN, not zero.**

    ## Scope

    | window | range | role |
    |---|---|---|
    | requested | 2016-01-01 .. 2023-12-31 | the collection candidate range |
    | context-only | 2015-10-01 .. 2015-12-31 | extra context, clearly marked, **not** part of the requested scope |

    No window was shortened to manufacture sufficiency. No year was chosen on the basis of returns or class labels.
    No market observation after 2024-01-01 was requested. No `SEALED` payload was read.

    ## Directory layout

    ```
    ticket19-data-delivery/
      manifest.json                    per-file sha256 / bytes / format / record_count
      README.md                        this file
      data/daily_bars.jsonl            3922 rows = 1977 Sohu (requested + context) + 1945 Wind
      data/trading_calendar.jsonl      3020 rows (derived SSE calendar, second-source corrected)
      data/security_status.jsonl       3 rows (suspension + ST-negative + coverage note)
      data/corporate_actions.jsonl     31 rows (cninfo dividends + Wind structured dividends + announcement hits)
      data/historical_rules.jsonl      10 rows (fees / taxes / mechanism)
      data/revisions.jsonl             45 rows (observed input versions)
      evidence/sources.jsonl           7 rows
      evidence/evidence_index.jsonl    84 rows
      evidence/search_log.jsonl        16 rows
      evidence/raw/                    67 real originals (byte-preserved, sha256-named)
      reports/coverage.json
      reports/gaps.json                8 gaps
      reports/conflicts.json           9 entries (incl. explicit no-conflict records)
      reports/cross_source_validation.json  Sohu-vs-Wind field-level comparison over the whole window
    ```

    ## Key coverage numbers

    | metric | value |
    |---|---|
    | daily bars delivered — Sohu, requested scope | 1916 |
    | daily bars delivered — Sohu, context only | 61 |
    | daily bars delivered — Wind, requested scope | 1945 |
    | exchange sessions in requested scope (derived calendar) | 1946 |
    | missing bar dates (after second source) | 1 |
    | missing bar dates (before second source) | 30 |
    | session dates recovered by the second source | 29 |
    | dates with explicit status row | 1 |
    | Sohu-vs-Wind overlapping dates compared | 1916 |
    | ... of which exact agreement | 1914 |
    | ... of which volume/amount mismatch (OHLC equal) | 2 |
    | longest consecutive delivered session run | 1095 |
    | 21-bar calendar-consecutive raw candidates | 1826 |
    | historical_availability coverage | 0 |
    | revision_chain_completeness | 0 |
    | cross-source conflicts | 8 |

    Two independent sources now carry the daily bars. Where they overlap, **both rows are delivered** (`DB-SOHU-<date>` and
    `DB-WIND-<date>`), each marked via `overlaps_source_ids` / `overlap_note`; neither is silently preferred. The
    field-by-field comparison is in `reports/cross_source_validation.json`.

    `metadata_candidate_21_row_windows` is a **raw-series denseness count only**. It is not a maturity count, not a
    support-condition check, and it does not assert that any window is usable.

    ## Provenance chain

    Every fact carries `evidence_refs` (non-empty) pointing to an `evidence_index` row (`evidence_id` + `locator`),
    which points to a real byte-preserved original under `evidence/raw/`. Originals are named by the lowercase
    64-hex SHA256 of their real bytes.

    ## Why this is PARTIAL_DELIVERY

    The bars (two independent sources), calendar, filings and rule originals are delivered and traceable. Two axes
    could not be established within this collection round:

    - **Point-in-time availability** — no reachable source exposes an as-of / revision view. `web.archive.org`
      became unreachable mid-collection (CONNECT tunnel 502 through the local egress proxy), so captured historical
      versions could not be retrieved and **nothing was fabricated** to fill the hole. The second source is also
      `CURRENT_QUERY_ONLY`, so cross-source *agreement* does not upgrade availability.
    - **Per-day security status** — only per-date suspension lists were reachable; no complete per-day status
      history (incl. ST flags and applicable price limits) could be obtained. The ST question specifically IS
      answered in the negative by the second source (explicit empty ST-event result + an abbreviation that has never
      changed), but a negative is not a status history.

    See `reports/gaps.json` for the full list, including which items need external authorisation.

    ## What the second source changed

    - Closed 29 of 30 session dates that Sohu had omitted, as real observed bars.
    - Found and fixed a calendar derivation error: **2018-12-31** was a 元旦 holiday, not a session.
    - Added a structured dividend table supplying `基准股本` and an explicit **NULL** bonus/capitalization ratio.
    - Delivered the Feb-2016 suspension as `SUSPENSION_PLACEHOLDER` rows (frozen price, null volume) — never as trades.
    - Answered the ST question negative, corroborated by two independent signals.
