# 集成双轴审阅

固定起点 `58e1d21`，被审阅源码 `62c8e69`。后续根提交仅任务状态/保全记录；12/19部分完成与15待执行票仍按真实依赖保留。

## Standards

Reviewed `58e1d21d872556648c4fd353a56ac481e8c17951...62c8e69cb48e8311045dd3b49135327bf89335bc`, the captured commit list, repository agent/domain/ADR instructions and `.scratch/roll-p0/project-layout.md`. Known testing/documentation debts remain separately identified by the integrator.

1. **[P2] Share the critical-review input contract before persisting a request.** `backend/src/roll/runtime/reviews.py:42–60` repeats `backend/src/roll/market/verification.py:19–37` with weaker bounds: `reason: str = Field(min_length=1)` versus `Field(min_length=1,max_length=2000)`; `fact_id` and `field` similarly omit the consumer's maximum lengths. `verification.py:116` later runs `VerificationCommand.model_validate(request['request'])`. A public API/real SQLite METHOD_CASE reproduction saved a 2,001-character reason successfully (201), then `/api/reviews/verification-requests/{id}/verify` returned an unhandled 500. This is **Duplicated Code, a judgement-call smell with a confirmed failure**, rather than a general request to add layers. The repository's `.scratch/roll-p0/project-layout.md:98` says validation belongs at external inputs and known failures need actionable reasons; line 89 permits a small shared interface for actual callers. Reuse one public Pydantic input contract for both request creation and verification, retaining the original-observation cutoff checks in Reviews. Reject an oversized new request at its creation boundary; if already-persisted incompatible input remains possible, return a bounded actionable error without rewriting history. Verify through the public API, including the normal request-consumption flow.

Reproduction: `roll-standards-reproduce.py` and `roll-standards-reproduction.json` in this report's directory. No actual external network or SDK calls; the isolated application has closed. No other actionable documented-standard breach or baseline smell was established. The concrete modular monolith, shared short SQLite transactions and current two-provider seams are consistent with the repository's explicit constraints; blocked future tickets are not missing implementation findings.

**Findings: 1 (judgement call); worst Standards issue: accepted critical-review input fails at consumption with HTTP 500.**

## Spec

Reviewed `58e1d21d872556648c4fd353a56ac481e8c17951...62c8e69cb48e8311045dd3b49135327bf89335bc` against spec v1.1, PRD V1.3 and the staged ticket contracts. **2 findings; worst P1.** Review is read-only except isolated METHOD runtime evidence; no external source or model call.

### Missing/partial requirements

Tickets 12 and 19 correctly remain partial; their dependent tickets and genuine forward evidence are not declared delivered. No additional missing requirement identified in delivered scope. The known E2E isolation/polling/documentation debts are separately assigned to the single fix implementer.

### Scope creep

None identified.

### Implemented but wrong

- **[P1] An older overlapping parent resets the fit budget and omits failed sibling trials.** `backend/src/roll/research/registry.py:238` accepts any overlapping predecessor; lines 102–104 and 118–122 count only its ancestry. Public API case: create A, successor B on the same dataset/interval, record five failed PRIMARY_FIT attempts; B's sixth is 409. Register C from A: C's additional fit is 201 and its manifest contains only that one attempt, omitting B's five failures. This violates spec line 291, “登记所有候选…失败与中止”, and PRD line 667 EVAL-09, “保留全部…尝试”. Require the current cumulative overlapping family, or reject a stale-parent sibling that bypasses prior attempts; retain all failed attempts and budget consumption. Proof: `roll-spec-review-family.json`.

- **[P2] Starting a peer host falsely interrupts live research.** `backend/src/roll/research/registry.py:75` unconditionally appends INTERRUPTED for every RUNNING attempt during construction. With the first TestClient host still active, creating a second host for the same SQLite changes its live attempt from RUNNING to INTERRUPTED; the first host's finish returns 409. Spec line 341 requires failures distinguish actual interruption/conflict, and PRD line 741 RUN-01 requires recoverable tasks. Persist/check actual task ownership before interruption, or refuse peer startup while that owner is active. Audit the same constructor pattern in `research/execution.py:179` and `market/resolution.py:56` as part of this fix. Proof: `roll-spec-review-peer.json`.

Evidence directory: `C:/Users/72449/.codex/visualizations/2026/10/07/01a116b0-7a64-7d10-8659-68853d73dbfe/`. Both finite public API cases use fresh SQLite directories, explicit METHOD evidence, and stopped their hosts normally.

Standards 1项，最重为有效核验请求消费HTTP500；Spec 2项，最重为同窗分叉绕拟合预算及遗漏失败。两轴分别保留，不合并重排。

三项发现与既有E2E账户隔离/SDK20秒等待/README和可重跑路径/三个源码EOF债交给一个独立实现工作树统一修复；修复和最终验证另附，不覆盖原红证据。
