# Independent triage of Codex ReviewRecord objections

Reviewed root `5a7f86e89cf978aa74ba637ce8db677673391aab` (product behavior remains `25d9b9a`), the five provider source files, spec/PRD and frozen design/policy contracts. Provider record: run `ed0d834e-049b-4356-b5a7-1ff5bc853aef`, review `2c05d94c-33a0-4353-9078-aed0060d7c6e`; only the sanitized `actual-codex-continuation-results.json` and acceptance receipt were read. No App, actual profile, provider, credentials or SEALED access; calculations used synthetic in-memory inputs.

## comparator-fidelity — partly confirmed

The ReviewRecord cites `code-shadow` SHA `432e5a164043f2140ff1c0aaa1d4261614812d95c7e491141cee850775a8cdf0` and `protocol-and-attempts` SHA `3da931f77f494e247f07610f4a8378557f4ae98487957d2a639acc459c86a1bf`.

**Confirmed crossover entry defect.** `design.py:30` freezes “fixed5/20-day moving-average crossover”; `shadow.py:210-212` instead creates an opportunity on every day MA5 > MA20. `shadow.py:216-218` uses the shared fixed lot/horizon, so an unchanged above-MA regime repeatedly reenters after horizon exits. This violates frozen comparator fidelity (spec ID-14 lines293/295; PRD EVAL-01 line665), even though no qualification has been granted.

Independent literal: starting cash100000, no positions, quantity200, zero fees/slippage, cap.50; 20 preceding prices and 45 observed days continuously increase by.1 from100, so MA5 > MA20 throughout, with **zero observed up-crosses**. Existing MA simulation nevertheless buys **Jan22, Feb11, Mar3** and sells **Feb10, Mar2**. A level condition cannot represent a crossing event.

**Do not infer a mandatory 50% target or mandatory down-cross exit.** Frozen START_HOLD text is “same start, budget/lot/rules,50% initial allowed exposure”; allowed exposure is an upper bound, not an instruction to maximize it. The same literal START_HOLD correctly keeps200 shares with initial realized exposure.2042 under.50. The full policy separately freezes `HORIZON_SESSION20_CLOSE`; no explicit down-cross exit is recorded. Changing sizing to50% or assuming a conventional sell-on-downcross is a policy redesign, not a proven repair. State concrete comparator entry/exit/sizing semantics in a successor full freeze; implement actual up-cross detection under that declared contract.

**Confirmed reporting gap:** `validation.py:97-99` reports baseline return/drawdown and a static shared-cap description, but comparator realized average/max exposure and occupied time are absent. Spec295/PRD665 require reported position/risk differences. Add measured comparator exposure/occupation and explicit differences; a common cap alone does not establish risk matching.

Acceptance: never-cross/one-cross/repeated-level fixtures; crossing uses only known historical bars, with explicit equality convention; exits honor the frozen contract; blocked/missing input cannot manufacture a cross; candidate/hold/MA share costs and budgets; measured position/risk differences are queryable. Do not relabel or recompute old frozen results as the new method.

## sparse-subset-intervals — confirmed algorithm gap

The record cites `code-validation` SHA `ed713e7561f61c15c27b7333857c7e7ecb7e99d306a723acb2ca74b814960c79` and `code-statistics` SHA `506bc42ebb8cc090135c22109d0d1c772b8d5d23c8481a6a4b4c6427582e7d9c`.

`validation.py:146/153` turns observed nonmembership into `None`; `statistics.py:40-42` rejects any such date. Calendar preservation is correct, but no bin or selected subset can have a numerical interval unless it contains every eligible date. This is not genuine missing evidence. Spec297/ticket21 require uncertainty for reliability and selected subsets while handling date dependence.

Independent literal: **1200 fully observed, mature** synthetic daily opportunities; p.2/.8 alternate, labels0/1, baseline.5. Selected count600, two occupied bins600 each, unobserved checkpoint count0. Whole20/40-block intervals are exactly.21 (block upper bounds60/30). Every subset/bin interval instead returns `INCOMPLETE_ALIGNED_CALENDAR_SCORES`. Algebra: every selected member's improvement=.21; bin1 error=.2, bin4 error=-.2. Every contiguous20/40-day block has nonzero membership; correct conditional sum/count arithmetic therefore has finite constant endpoints, while retaining all dates.

Repair direction: preserve calendar blocks and same-day joint grouping; carry observed membership separately from genuinely absent/unmatured/unknown evidence. Resample numerator and member count jointly, then compute conditional ratios. Do not compress dates, fill genuinely unknown outcomes with zeros or treat empty resample denominators as evidence. Freeze the new method/version and maintain independent support/assumption gates.

Acceptance: alternating membership above; unequal membership counts; zero-member dates retain calendar identity; empty subset/denominator stays insufficient; true missing, unknown labels and unmatured cases stay explicit; duplicates do not increase support;20/40 sensitivity and deterministic seed/replicates remain fixed. No threshold, family budget, cutoff or PASS-look relaxation.

## Qualification boundary

Keep all four real BLOCKING issues unresolved: `historical-admission`, `probability-validity`, `economic-and-robustness-failure`, `forward-and-deployment`. A verified COMPLETE technical review and these engineering repairs do not supply missing historical/independent/G5/G6/G7 evidence. Current actual diagnostic G4/G5 FAIL, other gates INCONCLUSIVE and NOT_GRANTED remain authoritative. Preserve the original ReviewRecord and links; any repair response/new evidence is an append-only successor, not an edit clearing the provider's objections.
