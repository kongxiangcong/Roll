# Company valuation calculator and immutable diagnostic versions

Ticket04 adds `CompanyResearch.calculate_valuation(ValuationCommand)` at `/api/company-research/valuations`. It never writes account valuation, forecasts, permissions, decisions or execution intents. Every saved output is **unreviewed**, `usable_range=false`. Unsupported economic assumptions remain diagnostic until ticket05 provides operating drivers, normalization and controlled economic review.

Ticket05 now supplies a [separate operating model, economic review and safe presentation](company-economic-review.md). It does not mutate04 inputs/results or relax their numeric-origin checks. Summaries use a pinned review ID and explicit presentation purpose; raw calculator prices remain diagnostics.

## Public boundary

- `POST /valuations`: `snapshot_id`, `config`, `assumptions`, `provenance`, optional `parent_version_id`, `change_reason`, `idempotency_key`.
- `GET /valuation-inputs/{version_id}` and `GET /valuations/{valuation_id}`: immutable records, canonical archive validation.
- `GET /valuations/{valuation_id}/bundle`: standalone JSON containing frozen input/result, snapshot/evidence packet, original materials, calculator sources and full licenses. Material originals are bounded to 36 MiB; larger packets use the full backup path.
- `POST /valuations/{valuation_id}/replay`: deterministic replay with no network/model calls. The standalone equivalent is `python -m roll.research.company.valuation_replay --bundle file.json` with the matching Roll method version installed; no SQLite store or external developer checkout is needed.

Replay checks archived source hashes against the exact installed version before calculating. It refuses `CALCULATOR_VERSION_UNAVAILABLE` on source drift, retaining the complete frozen sources for reinstall/recovery. It does not execute code supplied in a bundle. Input changes append a new version and parent reference; published 03 snapshots stay unchanged. The saved valuation links back to snapshot ID/hash, frozen company identity, facts and hypothesis versions.

## Calculator config

`roll.research.company.calculator.calculate(config, frozen_company)` is the deterministic arithmetic seam; the service additionally verifies reference origins and snapshot binding. The licensed `valuation_reference` module is compatibility code, not the controlled publication/review entry.

The config retains upstream FCFF/WACC fields: metadata (`company/as_of/currency/amount_unit/shares_unit/sources/assumptions`), positive `shares`, mutually exclusive `net_debt` or `equity_bridge`, `wacc`, `terminal_g`, and full same-horizon `scenarios`. Each scenario has unique `name` and either annual `fcf`, or annual `revenue` plus `fcf_margin`. Amount/share pairs are `unit/share`, `million/million_shares`, `100_million/100_million_shares`. Monetary values use one model currency; shares have no currency. Rates and margins are ratios.

Scenario weights are optional: omit `probability` for every scenario to omit the weighted price entirely. If supplied for all scenarios, finite nonnegative weights must sum to one and are explicitly researcher assumptions, never event/upside probabilities. No weights are synthesized. The diagnostic scenario range is not a confidence interval or usable price range.

Equity bridge rows retain `name`, signed `amount`, `source`, `treatment` and optional stable `component_id`. Positive deductions, negative additions and zero exclusions preserve `EV - sum(bridge) = parent equity`. Duplicate normalized names or component IDs and contradictory signs are rejected. Restricted cash can remain explicitly excluded (zero adjustment with source/treatment); NCI, associates and nonoperating assets remain individually visible. Whether different named rows economically overlap belongs to ticket05, rather than being inferred from arithmetic.

DCF uses year-end discounting and an explicitly positive final base FCFF, then year N+1 terminal FCFF. Early negative FCFF is valid. Nonfinite numbers, mixed scales and WACC <= g are rejected. Sensitivity accepts `{scenario,wacc,terminal_g}` and saves each valid cell or its rejection; invalid cells do not remove the base calculation. Limits: 10 scenarios, 50 annual periods, 400 sensitivity cells, 128 KiB service request.

EPV additionally requires `{normalized_fcff,applicability:"APPLICABLE",normalization_basis}`; absence of the declaration/basis returns NOT_APPLICABLE. Its input declaration remains unreviewed and must describe maintenance reinvestment normalization; it is never labeled independent validation of DCF. `perpetuity(100,.1)=1000` and `perpetuity(100,.08)=1250` are separate closed-form arithmetic examples, not finite forecast inputs.

## Provenance

Each scalar numeric leaf in `config` has an exact slash path in `provenance`, e.g. `scenarios/0/fcf/0`. Its record is `{kind,references,unit,currency,scope,period}`. Monetary `unit` matches the model amount scale; shares use its share scale with null currency; ratios use `ratio` and null currency; class prices use `price_per_share` and the actual listing currency. Periods/scope cannot be empty.

`ASSUMED` values cite an explicit assumption record (`assumption_id`, `statement`, `anchor_fact_version_ids`, `hypothesis_version_ids`) whose anchors are frozen in this snapshot. This stores the forecast assumption and its limits instead of bare future FCFF. `DISCLOSED` and `DERIVED` cannot cite assumptions or hypotheses as numeric facts: exactly one frozen fact of the corresponding kind must match value/unit/currency/scope and `period_start/period_end`; DERIVED also needs its saved derivation. No implicit unit/currency conversion is performed. Any required conversion must first become an explicit derived fact with its formula and references. Ticket05 supplies the quantitative operating bridge and economic checks; current acceptance of a cited assumption does not endorse its economics. WACC construction and long-run reinvestment reasoning can be retained in explicit assumption statements; missing structured economic checks remain an acknowledged gap until ticket05.

## Market basis and reverse calculation

`reverse` accepts `scenario`, `market_basis` and optionally paired `steady_margins/base_revenue` plus `comparable_margin_basis`. It never accepts a caller aggregate market value or one price times all shares. The frozen company identity determines all required listings, regardless of client `metadata.listing_structure`.

Every class row contains `listing_id`, `shares`, `shares_unit`, `shares_as_of`, positive `price`, `currency`, aware `priced_at`, `share_refs`, `price_refs`; a different currency requires direct `fx:{rate,from_currency,to_currency,as_of,source_refs}`. Counts sum to model shares. All quotes and share/FX dates are the same Shanghai trading day; quotes cannot exceed the exact model cutoff, itself no later than the snapshot. Date-only cutoff means end of the Shanghai date. Same-currency FX is absent or exactly one. The service requires these values to match frozen numeric facts: share/price scope is the listing ID, FX scope is `FROM->TO`, and period is that single day. Their references cannot be replaced by assumed prices.

Missing A/H class, price, FX or incompatible date/units refuses the reverse component while retaining the base diagnostic. Reference corruption is rejected at publication. Required year N+1 FCFF holds all years 1..N fixed. Nonpositive requirements have explicit `no_positive_terminal_requirement` status and empty revenue rows. Revenue conversion requires an explicit same-scope steady FCFF-margin basis and uses N+1 periods for CAGR; it does not identify the market's unique growth assumption or causal explanation.

## Licenses and recovery

The package includes byte-exact frozen upstream code, the adapted calculator, da-damu MIT/license scope and Sirius MIT notices. Original/adapted/wrapper hashes are part of every saved algorithm record, and all sources/input/results are registered with canonical `EvidenceStore` descriptors under raw paths. Existing `Backups` enumerates these originals and validates snapshot/version/identity/archive links and hashes on export/recovery. No network or model is needed for arithmetic, replay or backup.
