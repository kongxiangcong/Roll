# Spec axis

Reviewed `58e1d21d872556648c4fd353a56ac481e8c17951...62c8e69cb48e8311045dd3b49135327bf89335bc` against spec v1.1, PRD V1.3 and the staged ticket contracts. **2 findings; worst P1.** Review is read-only except isolated METHOD runtime evidence; no external source or model call.

## Missing/partial requirements

Tickets 12 and 19 correctly remain partial; their dependent tickets and genuine forward evidence are not declared delivered. No additional missing requirement identified in delivered scope. The known E2E isolation/polling/documentation debts are separately assigned to the single fix implementer.

## Scope creep

None identified.

## Implemented but wrong

- **[P1] An older overlapping parent resets the fit budget and omits failed sibling trials.** `backend/src/roll/research/registry.py:238` accepts any overlapping predecessor; lines 102–104 and 118–122 count only its ancestry. Public API case: create A, successor B on the same dataset/interval, record five failed PRIMARY_FIT attempts; B's sixth is 409. Register C from A: C's additional fit is 201 and its manifest contains only that one attempt, omitting B's five failures. This violates spec line 291, “登记所有候选…失败与中止”, and PRD line 667 EVAL-09, “保留全部…尝试”. Require the current cumulative overlapping family, or reject a stale-parent sibling that bypasses prior attempts; retain all failed attempts and budget consumption. Proof: `roll-spec-review-family.json`.

- **[P2] Starting a peer host falsely interrupts live research.** `backend/src/roll/research/registry.py:75` unconditionally appends INTERRUPTED for every RUNNING attempt during construction. With the first TestClient host still active, creating a second host for the same SQLite changes its live attempt from RUNNING to INTERRUPTED; the first host's finish returns 409. Spec line 341 requires failures distinguish actual interruption/conflict, and PRD line 741 RUN-01 requires recoverable tasks. Persist/check actual task ownership before interruption, or refuse peer startup while that owner is active. Audit the same constructor pattern in `research/execution.py:179` and `market/resolution.py:56` as part of this fix. Proof: `roll-spec-review-peer.json`.

Evidence directory: `C:/Users/72449/.codex/visualizations/2026/10/07/01a116b0-7a64-7d10-8659-68853d73dbfe/`. Both finite public API cases use fresh SQLite directories, explicit METHOD evidence, and stopped their hosts normally.
