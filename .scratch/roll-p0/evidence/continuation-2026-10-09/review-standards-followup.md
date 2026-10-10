# Standards follow-up

Reviewed source revision `d267b84` (`scripts/public_history_acceptance.py` and `fixes.md`) and calendar presentation revision `c46a22` read-only.

**Original P2 finding: fixed.** The helper now asks the kernel for an available port by default and rejects an occupied explicit port before creating a child. Before any API mutation, every initial startup and restart must return the generated acceptance token, exact resolved data directory, and current `Popen.pid`, while that child remains alive. A generic `/api/health` response from another service can no longer authorize writes. `start()` also owns cleanup of its child when startup raises before the outer process variable has been assigned. The identity endpoint exists only in the acceptance subprocess wrapper; production API contracts are unchanged.

The recorded occupied-port CLI check is consistent with this control flow: exit 1, no SQLite, zero-byte process log, and no child startup. Successful source acquisition and both ownership-verified startups remain separate integrated acceptance evidence to be produced; the occupied-port check alone does not establish them.

Calendar UI copy now matches the actual SSE 2013–2026 / SZSE 2026 coverage and explicitly retains unknown historical trading phases/rules. No residual actionable Standards finding in these repairs.

Findings: **0 remaining Standards**.
