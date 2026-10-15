# Standards review

Reviewed only the uncommitted successor-probability binding slice against HEAD `e0be816`: host service/method, own app insertion, new panel/integration, API/browser tests/config. Original SSE and unrelated changes excluded. Sources: AGENTS.md, domain instructions, GLOSSARY.md, relevant ADRs and the code-review smell baseline. Tool-enforced checks excluded. No tests, network or main-profile operations performed.

No actionable documented-standard violations or Fowler smells found.

## Requested transitive integrity audit

- **Original P2, now resolved:** binding reads/replay checked direct probability/block manifests without their nested source/method archives, so nested corruption could still yield `matches_original=true`. This was an integrity correctness finding, not a Fowler smell.

Creation otherwise checks the original predecessor complete fingerprint and model fingerprints, block→probability ID/manifest/cutoff, and frozen 0.60 threshold before binding. Only SOURCE block cases contribute support; artificial METHOD cases remain excluded. Calendar holes retain excluded same-day events, and mature/class/selected/bin/interval support gaps remain explicit. CAL reuse remains INCONCLUSIVE rather than independent calibration validity or qualification.

The new code performs bounded linear event aggregation in a normal synchronous API handler, with no process, network or fit calls. Persistence uses immutable manifests, a unique freeze/key constraint and writer-transaction idempotency rechecks. Original account/protocol/attempt state is not modified. The parent reported API 1 PASS/22.75s; no independent rerun was performed.

## Focused repair re-review

Confirmed `get()` now invokes the existing read-only probability and block readers, which verify each manifest and its source/method archives, then compares both returned parent manifests to the binding's immutable stored snapshots. No scoring, fitting or model-run consumer is introduced. The P2 is resolved.

The isolated regression corrupts each newly generated probability/block source in turn, requires 409 from both GET and replay, restores original bytes in `finally`, and confirms normal replay after restart without library runtimes. Inspected `integrity-green.log`: **1 PASS/22.33s**; `browser-final.log`: **1 PASS/28.5s**. The original failing 200-versus-409 evidence remains recorded. No independent rerun or network operation performed.

Final Standards findings: 0. Open additional boundary findings: 0.
