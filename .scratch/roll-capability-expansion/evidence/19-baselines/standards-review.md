# Standards review

Reviewed only the current missing-baseline repair against HEAD `b427e16`: performance host/renderer/panel, performance API/reference/browser tests and baseline Playwright config. Existing SSE and other dirty changes excluded. Sources: AGENTS.md, domain instructions, GLOSSARY.md, relevant ADRs and the code-review smell baseline. No tests, network or main-profile operations performed; tool-enforced checks excluded.

No actionable documented-standard breaches, Fowler smells or additional integrity findings found.

The shared `saved_interval` extracts an already-required calculation used by both candidate and comparators. It requires independently ordered, unique dates equal to the original complete calendar, positive finite NAV and no unknown observations. It performs no date intersection, reindexing, forward-fill or synthetic return insertion. Only candidate/baseline pairs passing those checks receive descriptive return differences or overlay plots. Shared dates also ensure monthly bar positions represent the same observed months.

The host now reads the three actual saved comparator curves from the same source report/state revision and archives them with renderer inputs. CASH remains its saved trajectory, including initial holdings; it is not replaced with a constant or forced zero return. The API test compares every baseline's original points and first/last-NAV return independently. This corrects the earlier inaccurate claim that the donor had no saved baselines.

Absent comparator entries remain absent; present entries with missing curves or mismatched dates retain incomplete-window status. The frontend reports those cases separately from saved versions containing no comparator collection. A malformed baseline does not silently shorten a candidate window. Relative values remain descriptive, with risk-matching qualification explicitly ungranted.

Prior report IDs and idempotency results still return their original verified archives. Optional `benchmarks` handling preserves old manifests and figures rather than adding present-day baselines on read. Generating a new artifact binds the new source revision; no trade ledger or research result is recalculated.

Inspected supplied logs: API **1 PASS/22.34s**, Chrome **1 PASS/31.6s**, build PASS. The fixed numerical edge result was reported by the parent; not independently rerun here.

Standards findings: 0. Additional requested boundary findings: 0.
