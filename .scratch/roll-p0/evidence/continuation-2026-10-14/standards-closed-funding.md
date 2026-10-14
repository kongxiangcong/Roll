# Standards review — closed funding fee facts

Scope: accepted `7311e68508a9f7d54043210f40f98da92f696d87`, merged into integration at `a020be4225beb8d88f62feee7bad2a37862b4922`; delta from `555ab7a7f0172495714c80094335a32945c98653`. Read the actual `broker_costs.py` change and parametrized public application test, with the existing AGENTS, project-layout and twelve-heuristic standards baseline.

## Documented standards

No actionable violations. The fee-fact confirmation removes an unrelated active-funding prerequisite while preserving expected account, funding and tariff version checks, source archiving and immutable idempotent persistence. Its owner remains the decisions module; it neither mutates funding nor issues capabilities. The public FastAPI test checks both REVOKED and PAUSED funding in isolated SQLite and verifies unchanged funding plus empty capabilities/grants. This follows the requirement that missing unrelated authority must not block recording known facts.

## Judgement smells

All twelve Fowler heuristics considered; no actionable findings. The narrow existing condition is simplified, and one parametrized regression exercises two meaningful business states without additional abstraction, scattered ownership or repeated financial rules.

Standards findings: 0 documented violations, 0 actionable judgement smells. Scoped `git diff 555ab7a..HEAD --check` passes. The four known dirty-file hashes checked immediately before and after this merge are unchanged, and tracked dirty state remains three files/eight added lines. The first two document hashes differ from the earlier preservation snapshot because the root subsequently committed its own authorized notes; this review verifies the immediate pre-merge state rather than relabelling the historical snapshot. No tests, HTTP, real database, provider calls, cleanup or runtime operations performed.
