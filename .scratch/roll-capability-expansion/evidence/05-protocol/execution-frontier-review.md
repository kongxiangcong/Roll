# Read-only execution frontier review

05 has an offline execution-stress frontier. It is not wholly blocked by source authority. Existing contracts determine the scenario grid, but v2-specific order/lot behavior must be registered before results rather than silently borrowed from v1.

## Existing exact contracts

- `research/design.py:55-56,61-65`: next declared daily OHLC execution; partial/missed 0/50/100%; NEXT_OPEN, NEXT_CLOSE, ONE_MORE_SESSION_OPEN and OUTSIDE_ALLOWED_PRICE_NO_FILL. No fill is not a prediction loss; unresolved support remains INCONCLUSIVE.
- `research/validation.py:180-189,222-225`: original G5 consumer evaluates each delay at full fraction, then NEXT_OPEN at 0/.50/1; it does not automatically evaluate the full Cartesian product. It reruns candidate and all original comparators together and preserves hard failures/unknown statistical validity.
- `research/shadow.py:104-108,135-157,224-231`: v1 delay changes pending **BUY** entry point/destination (next close or observation+2 open); zero fraction explicitly misses, half quantity floors to the registered increment, below-lot support fails explicitly, and unfilled reservation is released without automatic resubmission. Horizon remains observation+20; scheduled liquidation is not fraction-scaled. START_HOLD still has no automatic exit.
- `research/successor_shadow.py:85-180,231-236`: v2 currently has no scenario parameter. Pending BUY/ADD and early SELL execute only on the exact next consecutive session OPEN and are removed after that attempt. Missing target sessions cannot substitute a distant bar. Migrated lots keep their original CLOSE schedule; each new fill creates an entry+20 lot. Sellability/T+1, fixed bounds, cash/exposure checks and cooldown history remain essential.

## Directly implementable

Register the fixed delay/fraction grid, resource bounds and immutable source-prefix identity, then add a separate versioned METHOD diagnostic with save/list/read/replay and known-failure/INCONCLUSIVE outputs. First prove its default NEXT_OPEN/full returned state **exactly equals** unchanged original `successor_shadow.simulate` across BUY/ADD/early EXIT, scheduled exits, missing slots and migrated lots. No new fit, SEALED read, source query or economic threshold is needed. Keep old engine files/fingerprints and all old artifacts unchanged. Do not implement alternate execution by replacing bar OPEN with CLOSE or shifting timestamps: that also corrupts valuation, price bounds, exposure and horizons.

## Decisions to freeze before alternate outcomes

Start with the inherited **entry BUY/ADD-only** stress scope; preserve v2 early SELL and scheduled exits unchanged and label that limitation. This most closely matches v1's pending-BUY consumer. Applying fractions/delays to early sells, forced/horizon exits or every order is a separate extension, not already determined by v1. Register actual target-slot behavior, reservation lifetime, no distant substitution, lot rounding and partial remainder disposition; preserve later policy ADD decisions rather than claiming the portfolio can never fill again. Each actually filled new v2 lot keeps entry+20; migrated lots retain their original deadline.

NEXT_CLOSE needs an explicit deterministic CLOSE event priority and correct execution-point exposure valuation; ONE_MORE_SESSION_OPEN must require both declared intermediate/target coverage rather than borrow the next available bar. Preserve unfilled/unknown outcomes explicitly. These are implementable engineering contract choices to document before evaluation, not grounds to call all 05 externally blocked. If ambiguous cases are excluded from the first method, expose that exclusion and retain G5 INCONCLUSIVE; never advertise complete execution-stress delivery.

Review only: no implementation, tests, fitting or network performed.
