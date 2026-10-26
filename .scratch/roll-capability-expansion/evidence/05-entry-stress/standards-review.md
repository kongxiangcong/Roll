# Standards review

Reviewed only the uncommitted entry-stress slice against HEAD `993fbfa`: host/worker/versioned engine/method, own app routes, panel/cost integration and API/browser tests/config. Original SSE and unrelated changes excluded. Sources: AGENTS.md, domain instructions, GLOSSARY.md, relevant ADRs and the code-review smell baseline. Tool-enforced checks excluded. No tests, network or main-profile operations performed.

No actionable documented-standard violations, Fowler smells or additional implementation correctness findings found.

The copied versioned engine is justified by preserving old artifact fingerprints while adding an explicit new contract. The worker compares complete default state against both the original engine and every saved prefix, rather than assuming parity from totals. Existing simulator, policy, shadow and statistics modules have no diff against the stated base.

Alternate mechanics apply only to BUY/ADD entry orders. Early SELL and lot horizons retain their original behavior. Delayed entry requires consecutive declared intermediate/target frames and attempts only the exact target; missed coverage cannot substitute a later bar. Original reservations remain counted while delayed orders wait, duplicate pending entries are refused, and partial/missed attempts release the remainder once without automatic resubmission. Original later ADD decisions remain explicit.

NEXT_CLOSE entries execute after original scheduled horizon closes and before closing valuation/policy observation. Exposure checks value all existing lots at the actual execution point. Quantity rounding, minimum lots, price bounds, usable input and cash checks remain enforced. Missing slots and unknown valuation stay null; observed risk failures remain independent of incomplete full-window economics.

Verification and six fixed scenarios execute inside the 30-second kill/wait worker with 200-frame/span and 8 MiB input/output limits; network paths are denied. Reads reuse the stress verifier and check stored parent pointers plus nested input/method artifacts. Replay uses original archived payload and wrapper/inherited dependency fingerprints, ignoring later history. Unique keys and transactional idempotency checks preserve immutable ownership.

Acceptance follow-up: the earlier `api-final.log` failure remains recorded. Reviewed the fixture correction for migration effective at session 2: unknown input now occurs at session 5, actual ADD fills at 3, migrated-lot horizon sale at 4 and early exit at 7. Every frame still asserts complete original/extended state equality. Inspected `api-final02.log`: **2 PASS/49.73s**; Chrome **1 PASS/45.7s** (test body 24.4s); build PASS. The coverage caveat is resolved. No independent rerun performed.

Standards findings: 0. Open review/acceptance caveats: 0 within this slice.
