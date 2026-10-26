# Standards review

Reviewed the uncommitted ticket 21 slice against `50fa11d`: block host/worker/method, own app insertion, block panel/probability integration, block tests/config, locked dependencies and block documentation. Preexisting SSE and other changes excluded. Sources: AGENTS.md, domain instructions, GLOSSARY.md, ADRs 0001–0004 and the code-review smell baseline. Tool-enforced checks excluded. No tests, network or main-profile operations performed.

No actionable documented coding-standard violations or Fowler smells found.

## Requested runtime-bound audit

- **Original P2, now resolved:** `cases_for()` executed the frozen 2,000-replicate bootstrap on the API event loop before the worker deadline, so complete large windows could block requests and cancellation. This was a resource correctness finding rather than a Fowler smell.

Paired-date handling otherwise preserves the complete source calendar, distinguishes unknown mature-event dates from observed empty conditional groups, and keeps same-date members together. Source gap cases and six positive artificial METHOD cases are separate. Actual arch indices are checked against grouped formulas; different random generators are explicitly distinguished from numerical disagreement, and endpoint claims remain limited.

The service consumes verified saved probability/source archives, records input/method/source manifests, and verifies them during persisted reads/replay without re-running arch. Unique keys plus a writer-transaction idempotency recheck protect report ownership. Hypothesis/independent validity/qualification remain ungranted. API and edge tests were still in progress at assignment and were not independently run here.

## Focused repair re-review

Confirmed that the host only builds aligned groups, with no frozen-function import or execution. The worker verifies normalized `statistics.py` bytes against the payload SHA, selects the original `rounded` and `paired_block_interval` AST definitions, and executes those exact definitions alongside arch within the parent-enforced 30-second kill/wait boundary. The original business module and frozen numerical algorithm remain unchanged. The original P2 is resolved.

Also inspected the same-day excluded-event repair: any excluded observation adds an explicit unknown score even when other events on that date are mature; the new builder regression checks both mixed and entirely missing dates. That regression was still pending at re-review.

Inspected supplied logs: final API/edges **2 PASS/22.42s**, Chrome **1 PASS/28.9s**. No independent rerun performed.

Final Standards findings: 0. Open additional boundary findings: 0.
