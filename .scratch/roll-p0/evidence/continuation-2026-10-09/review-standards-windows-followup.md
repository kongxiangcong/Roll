# Standards Windows follow-up

Reviewed `f50d19b3430fac46aa91b1b99c96ef14ee5493bc` and its `scripts/public_history_acceptance.py`, `windows-lifecycle-correction.md`, `lifecycle-v3-final.json`, and `lifecycle-startup-failure.json` read-only. This supersedes the earlier follow-up's incorrect assumption that the Windows launcher PID equals the serving Python PID.

**Original P2 isolation finding: resolved by the corrected Windows implementation.** Each startup generates a new token and unique receipt path. The actual child atomically writes its PID, token, and resolved data directory before application bootstrap. The helper accepts HTTP readiness only when the listener identity exactly matches that authenticated local receipt and the launcher remains alive. It does not require `Popen.pid` to equal the actual server PID.

Shutdown first requests the wrapper's token-protected graceful exit. Startup exceptions clean the actual child PID from its receipt, then stop/wait for the launcher. Every completed stop verifies that the listener is closed before restart or completion. These controls remain confined to the acceptance subprocess wrapper.

Actual Windows lifecycle evidence records launcher/server pairs `45416/41916` and `42028/34136`, different startup tokens, unchanged empty account, and two graceful shutdowns with closed listeners. The startup-failure evidence records launcher/server `43084/32488`, no API command steps, and owned-child cleanup with a closed listener. These are meaningful successful-restart and failure-cleanup checks, rather than an assumed PID relationship.

The lifecycle evidence explicitly reports `real_market_acquisition=false`; integrated public-source acquisition/replay v3 remains a separate final acceptance record and is not established by these lifecycle checks.

Findings: **0 remaining Standards** in the requested helper correction.
