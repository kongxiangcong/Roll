# Standards review

Reviewed committed increment: `git diff e655be7cbca943482ad3b4df35667eef700d1c7b...78be4ea7142d36cabac0f0adb88b15e245da46a2`. Sources: AGENTS.md, domain instructions, GLOSSARY.md, ADRs 0001–0004, ticket 05, its acceptance record, and the code-review smell baseline. Dirty implementation changes and tool-enforced checks excluded. No tests run.

No documented coding-standard violations or new Fowler smell findings. Prior P3 duplication is resolved by the narrow `savedEvidence` helper.

## Requested resource/prefix boundary audit

- **[P2] Bound verification to the recorded prefix before replaying it.** `backend/src/roll/research/successor_protocol.py:158–160` loads and verifies the complete history through `self.successor.frames(...)`, then returns `frames[:revision]`. That existing verifier re-simulates each cumulative prefix. Consequently, a validation for revision 3 verifies arbitrarily many later frames despite its frozen `maximum_method_frames: 1000` resource plan and request revision limit. Later unrelated frame corruption also prevents replay of an otherwise intact recorded prefix. Fetch and verify only revisions through the requested boundary, retaining their continuity, input, and result fingerprint checks. This is a resource/reproducibility correctness finding from the requested boundary audit, rather than a Fowler smell or an invented repo coding rule.

SQLite writers use BEGIN IMMEDIATE, recheck competing owners and idempotency keys, and retain unique constraints. Archives, code, registered protocol, successor binding, and stored-prefix input fingerprints are checked. Missing valuation bars remain null and yield incomplete descriptive economics; METHOD, INCONCLUSIVE/FAIL, NOT_GRANTED, and `complete_experiment_frozen=false` remain explicit. Those partial consumers are acknowledged limitations, not review findings.

## Focused repair re-review

Reviewed only the uncommitted prefix repair in `successor_protocol.py` and its regression addition in `test_successor_protocol.py`; ticket 09 and other working-tree changes excluded.

The P2 finding is **resolved**. SQL retrieval now includes `revision<=?`, and the bounded verifier checks revision continuity, expected revisions, command hashes, simulated results, and result fingerprints before returning the prefix. Later frames are neither read nor simulated. The original `successor_shadow.py` remains unchanged, preserving existing frozen source fingerprints; reusing its pinned `simulate` avoids a second policy implementation. The small local verifier is justified by that compatibility constraint rather than grounds for reopening the prior duplication finding.

The regression corrupts frame 4 after storing a revision-3 validation and confirms revision 3 still replays successfully. Inspected the supplied `prefix-green.log`: **1 passed in 20.87s**; no independent test rerun performed during review. METHOD-only and incomplete-experiment boundaries are unchanged.

Final Standards findings: 0. Open additional boundary findings: 0; original P2 resolved.
