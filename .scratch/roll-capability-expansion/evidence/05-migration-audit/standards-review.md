# Standards review

Reviewed only the uncommitted migration-audit slice against HEAD `84d8736`: service/method, own app routes, panel/integration and API/browser tests/config. Original SSE and unrelated changes excluded. Sources: AGENTS.md, domain instructions, GLOSSARY.md, relevant ADRs and the code-review smell baseline. Tool-enforced checks excluded. No tests, network or main-profile operations performed.

No actionable documented-standard breaches, Fowler smells or substantive correctness/integrity findings found.

The audit consumes the immutable cost-stress base events and exact saved frame positions rather than rerunning execution. Original baseline positions are bound to migration position/instrument/quantity/deadline, proposal and policy. New lots are associated with actual saved BUY fills and retain entry-plus-original-horizon deadlines. Each observation checks identity, original horizon, supported quantity/sellability and migration reference. Overdue positions retain their original deadline and the saved blocking reasons, while migration effectiveness is shown separately from registration.

Registered allowed instruments are compared with the frozen rules and actually observed bars/signals/lots. Unobserved registration remains visible and does not count as transfer evidence. Empty initial holdings mark baseline migration as inapplicable while retaining new-lot/scope checks. Engineering consistency is not promoted into real scope-transfer evidence, G5 PASS or formal capability; G5 remains INCONCLUSIVE even for an internally consistent package.

Input size, frame count and complete declared span are limited to 8 MiB/200/200. Missing integer slots remain explicit. Work is bounded inspection over saved records, with no subprocess, market access, fitting or new execution. The existing simulator, policy and statistical modules have no diff against the stated base.

Reads verify the audit manifest, reuse the stress verifier for nested input/method integrity and compare the exact stored source pointers. Replay checks audit-method/statistics fingerprints and derives again only from archived source. Unique keys and writer-transaction idempotency rechecks preserve immutable ownership. The API covers original blocked deadlines, new-lot horizon, later-history independence, nested corruption/restoration and restart.

Focused follow-up: the Spec review's position-identity P2 is resolved. Inspected the new per-frame `position_id` comparison, new-lot identity derived from the BUY order ID rather than the first observed position, and monotonic remaining-quantity check. Pure METHOD adversaries cover replaced baseline/new-lot position IDs and quantity regrowth without altering persisted source artifacts; public positive/restart/replay coverage remains.

Inspected final logs: `api-final.log` **1 PASS/22.88s**, `browser-final.log` **1 PASS** (body41.5s; rounded total1.0m). Build was already PASS with no subsequent TypeScript changes reported by the parent. No independent rerun performed.

Standards findings: 0. Spec position-identity repair verified. Open review/acceptance caveats: 0 within this slice.
