# Standards review

Reviewed committed increment: `git diff d279a0c551d96bb2e7dededd5f77d195aad06a12...e655be7cbca943482ad3b4df35667eef700d1c7b`. Preexisting working-tree changes excluded. Sources: root AGENTS.md, domain instructions, GLOSSARY.md, ADRs 0001–0004, and the code-review smell baseline. Tool-enforced checks excluded.

No documented-standard breaches found.

One non-blocking judgement-call finding:

- **[P3] Possible Duplicated Code — shared saved-evidence query behavior.** `frontend/src/components/action-evidence-panel.tsx:13–17` and `status-evidence-panel.tsx:13–17` repeat the same collection lookup, instrument filtering, cutoff serialization, and parallel per-plan query. Both contain `const params=cutoff?\`?known_by=${encodeURIComponent(new Date(cutoff).toISOString())}\`:''` and `plans.filter(p=>p.instrument===instrument).map(...)`. The host-current cutoff correction already requires identical edits in both consumers. Extract just this existing request behavior into a small shared function, parameterized by the evidence endpoint and response type; retain each domain's rendering and state handling. This addresses a demonstrated repeated responsibility without introducing a general panel framework.

The backend returns complete saved assessments and obligation audits rather than constructing upgraded account facts. Reported action dates and amount strings match their validated producer contracts; incomplete inventory, unverified units, unknown fulfillment, and NOT_GRANTED remain explicit. Empty current cutoffs are resolved by the host. No implementation changes or tests performed for this review.

Standards findings: 1 low-priority smell; 0 documented-standard violations.
