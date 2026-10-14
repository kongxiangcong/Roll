# Spec findings resolution

Fixed comparison: `git diff a23a808...69ada314`, product fix `a856990`, integrated root `50a1bf4d073b12557e5c47e4890a594cf8e27243`. Reviewed successor shadow implementation, two added public API tests and acceptance records. Static review only; no tests, real databases, providers, fits or SEALED access.

**Both follow-up P2 findings are resolved.**

1. Scheduled horizon CLOSE now passes its exact `lot_id` into execution. SELL eligibility filters by that target as well as instrument, entry session and known sellable quantity. Zero or UNKNOWN sellability for the original lot therefore produces `SELLABLE_QUANTITY_UNKNOWN_OR_INSUFFICIENT`; an eligible later ADD lot cannot satisfy the scheduled exit. Ordinary position-wide exits retain their existing allocation behavior. The added public test checks original100@3 plus ADD100@23 through session4, unchanged cash after the purchase, both retained lots, refusal evidence and deterministic replay. This satisfies the reviewed requirement “original baseline lot horizon CLOSE independent of ADD lot horizon”.

2. Freeze rejects nonempty `added_lots` or an `original_remaining_quantity` differing from baseline quantity with422 `SUCCESSOR_BASELINE_REQUIRES_ORIGINAL_MIGRATION_LOT`, before saving any freeze. The subsequent valid baseline using the same proposal/key succeeds in the added public test. Split provenance is no longer accepted and silently collapsed; original-only migration baselines remain supported. This preserves ticket25's “政策变化保留持仓迁移安排”.

No residual actionable spec finding identified in this narrow fix delta. The earlier public evaluator ADD-follow-up resolution remains intact. Author red/green evidence and root independent verification are distinct; this static review does not claim either was rerun.

Whole tickets20/25 and complete v2 protocol/validator/production dispatch remain unfinished. UNVALIDATED, INCONCLUSIVE, NOT_GRANTED and no actual forward start retain their prior meanings; engineering findings closure does not establish economic or actual qualification.
