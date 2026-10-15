# Standards review

Reviewed the current uncommitted ticket 09 slice only: financial service and pinned SDK worker/reference documents; AKShare additions to source configuration/app wiring; financial panel/market insertion/styles; financial API, SDK-process and browser tests/fixtures. Preexisting SSE and other dirty changes excluded. Sources: AGENTS.md, domain instructions, GLOSSARY.md, ADRs 0001–0004, ticket 09, and the code-review smell baseline. Tool-enforced checks excluded. No tests or network calls performed for this review.

No documented coding-standard breaches or actionable Fowler smells found. The narrow provider transport extension preserves the actual pinned SDK API; normalization and persistence remain in the host service rather than a second crawler. Source configuration, content-addressed archives and immutable fact versions reuse existing boundaries.

## Requested cancellation/raw-first boundary audit

- **[P2] Persist active-response prefixes before hard cancellation.** In `akshare_financial_process.py`, `send()` accumulates received chunks in an in-memory `bytearray` and writes the ordinal raw file only inside its finalizer. `FinancialIncome.process()` handles cancellation/deadline by killing the child. If an entity has yielded bytes and then stalls, that kill prevents the finalizer, losing the received prefix; the parent archive recovery skips its missing raw file. Previously completed entities survive, but the active entity does not. Write bounded received chunks to the ordinal file as they arrive and checkpoint enough journal metadata to archive it as incomplete after termination. Exercise this with the actual subprocess against a fixed slow response, because the current cancellation test cancels only an injected sleeping supplier. This is a correctness finding from the specifically requested boundary audit, not a Fowler smell.

The existing byte/call/deadline limits, no-redirect anonymous transport, original-before-normalization ordering, explicit unknown semantics and METHOD provenance otherwise remain apparent from inspection. Source-bound financial versions retain raw fields and references; old versions are not overwritten.

## Focused repair re-review

Reviewed only the active-entity prefix repair and its real-SDK fixed-transport subprocess regression; unrelated current changes excluded. The P2 is **resolved**: each application-received chunk is now written and flushed to its bounded ordinal file before awaiting more response data, and the journal records the current prefix SHA, byte count and incomplete status. A parent hard kill therefore leaves recoverable bytes rather than depending on the child's finalizer. The host archives existing ordinal files before validating completeness/integrity and does not normalize incomplete captures into facts.

`test_hard_kill_keeps_the_active_entity_prefix` uses the pinned SDK subprocess and a fixed slow entity, waits for an 8192-byte prefix, kills the child, and checks exact original-prefix bytes, matching SHA and `original_complete=false`. Inspected supplied logs: `sdk-prefix03.log` **3 passed in 10.16s**, covering successful, HTTP-503 and hard-kill paths; `revision-green.log` **2 passed in 15.68s**. Earlier Windows journal-read race failures remain recorded rather than overwritten. These are inspected test results; no independent rerun or network request was performed in this review.

Final Standards findings: 0. Open additional boundary findings: 0; original P2 resolved.
