# Spec review: METHOD threshold stress

Reviewed own additions relative to `63200a2`: threshold service/worker/method, routes, UI and tests. Original dirty SSE changes are excluded. No tests, network, main-profile operations, code edits or commits performed.

**[P2, closed] Post-START preparation terminal handling.** Targeted rereview confirms directory preparation, worker execution and successful finalization now share the post-START try/except. A real isolated directory/file conflict regression checks FAILED run and three FAILED events with same-key de-duplication. Recovery now rechecks terminal state inside its write transaction and safely returns an already-terminal run when two initializers race; a Barrier-based dead-owner fixture checks only three INTERRUPTED events. [api-final02.log](api-final02.log) records 1 PASS/33.38s including these paths, preserved training attempts, unknown-return risk failure and nested corruption. Open findings: zero. This reviewer inspected code/logs without rerunning tests.

Otherwise the slice matches [05](../../issues/05-policy-freeze-validation.md) and [spec ID-05](../../spec.md):

- Three registered entry thresholds are all reported with fixed support threshold and unchanged costs, horizons, quantities/cooldown. Original probabilities are reused; every base0.60 prefix must match full original state. There is no fitting or winner selection.
- Distinct METHOD events are committed before worker evaluation; `partition=null` and METHOD_DECLARED_SLOTS avoid mislabelling training data. Family/lineage manifests include sibling METHOD starts and terminal records beside unchanged training manifests. Old registry/research_attempts semantics and fit/CAL/SEALED budgets remain unchanged.
- Worker failure/cancellation handlers preserve failed/interrupted outcomes; dead-owner recovery appends terminal evidence. Tests explicitly describe their abandoned-owner setup as a fixture, not an actual process-kill experiment. Success means execution completed, distinct from a scenario risk FAIL.
- Full slot spans, unknown valuation and observed hard-risk failures remain separate; incomplete full-window return stays null. G5 never PASS, complete freeze remains false and real/independent evidence remains missing. Source/method/result fingerprints and nested archive checks protect reads/replay without new attempts on replay.
- Tests cover positive threshold differences, fixed support exits, idempotency, source preservation, adverse unknown-return exposure, nested corruption, restart replay and family interruption manifests. Final extended/browser checks were still being recorded; no fresh pass is claimed by this reviewer.

Migration lot/scope auditing and a versioned engineering-completeness checker remain feasible offline consumers. Missing real authority, independent support and absent penalty/lookback artifacts are separate evidence/budget conditions.
