# Factual broker tariff registration with closed funding

2026-10-14, isolated `codex/t25-closed-funding` from integration `555ab7a`.

Removed only the `funding.state == CONFIRMED` requirement from tariff confirmation. Saving user-confirmed cost facts no longer requires enabling a revoked funding authorization or resuming a paused one. Exact current positive account/funding versions, confirmation, source archive, decimal bounds, scope and effective interval remain enforced. No funding state, permission, grant or action eligibility is mutated.

Public FastAPI / isolated real SQLite TDD:

- RED: new `enabled=False → REVOKED` and `pause=True → PAUSED` cases both returned 409 `BROKER_COST_ACCOUNT_OR_FUNDING_VERSION_CONFLICT`; **2 failed / 19.86 seconds**.
- GREEN: both now return 201, funding JSON remains byte-value equivalent to its prior response, `allowed_actions=[]` and grant list is empty. Existing immutable registration/restart/source bytes/idempotency and scoped literal fee/interval/version estimate regressions remain passing; **4 passed / 25.80 seconds**.

Logs and generated test SQLite/archives are isolated in `.scratch/closed-red.txt`, `.scratch/closed-green.txt`, `.scratch/t25-closed-red` and `.scratch/t25-closed-green`. Existing venv used through an absolute path; no new dependencies, production SQLite, provider, fit, SEALED, external notification or frozen math changes.

Root owns independent acceptance, source/destination preservation receipt and worktree cleanup. This is an engineering boundary repair, not formal qualification or a resumption of funding.
