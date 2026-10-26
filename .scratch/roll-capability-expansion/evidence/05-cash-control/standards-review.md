# Standards review

Reviewed only the uncommitted CASH-control slice against HEAD `2661420`: service/method, own app routes, panel/cost integration and API/browser tests/config. Original SSE and unrelated changes excluded. Sources: AGENTS.md, domain instructions, GLOSSARY.md, relevant ADRs and the code-review smell baseline. Tool-enforced checks excluded. No tests, network or main-profile operations performed.

No actionable documented-standard breaches, Fowler smells or additional correctness/lineage findings found.

The control explicitly rejects initial holdings, avoiding assumed liquidation or a fabricated cash equivalent for existing lots. Its original cash is held unchanged across every declared METHOD slot, with zero interest, fees, trades and exposure. Candidate points are independently padded with unknown NAV for missing slots; incomplete candidate economics suppress the full-window difference while the fully specified CASH trajectory remains valid. Neither observed dates nor calendar gaps are compressed.

Observed exposure uses the saved long-only candidate NAV and cash from the same frame; missing valuations are excluded explicitly rather than treated as zero exposure. A known exposure breach against the original frozen cap, or a retained base drawdown failure, can yield FAIL despite later unknown NAV. Missing observations do not establish exposure compliance or risk matching. The displayed maximum remains labelled as observed, and aggregate G4 otherwise stays INCONCLUSIVE.

Creation reads checked immutable stress/input artifacts and binds the original statistical-code fingerprint. The service records source manifest/input/method references; reads reuse the parent stress verifier and compare both stored source pointers, covering nested source integrity. Replay derives from the original archived payload and verifies wrapper/statistics fingerprints without consuming current shadow state. Unique ownership and transactional idempotency rechecks remain consistent with adjacent services.

No original simulator, policy, protocol or statistics module differs from the stated base. This slice adds bounded linear descriptive derivation over at most 200 sessions, with no fitting, execution or network path. METHOD, incomplete experiment and NOT_GRANTED remain explicit.

Inspected supplied logs: API **1 PASS/28.88s**, Chrome **1 PASS/30.9s**. The latest exposure-breach-with-unknown regression was still running at assignment and was inspected as code, not independently executed.

Standards findings: 0. Additional requested boundary findings: 0.
