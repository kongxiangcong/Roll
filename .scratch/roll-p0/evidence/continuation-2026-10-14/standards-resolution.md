# Standards resolution review — 2026-10-14

Scope: final delta `92ca6dd8a3be7fc3ff6ddf0c15af99bdc65722b8...69ada314e8f52518becac71a42ba2066adcb3c6d`, integrated at `50a1bf4d073b12557e5c47e4890a594cf8e27243`. Inspected the three executable paths: `backend/src/roll/research/successor_shadow.py`, `backend/tests/application/test_successor_shadow.py`, and the owned `preserve_owned.py` evidence helper. No tests, HTTP, SQLite, provider calls, cleanup or runtime operations performed.

## Documented standards

No actionable violations. The lot selector belongs to the existing simulation execution routine and is consumed by a real scheduled-horizon caller. It retains ordinary market sells while restricting a scheduled original-lot sale to its identified lot. Split-baseline rejection occurs at the external freeze command boundary rather than silently rewriting a lot horizon. Both regression tests exercise public FastAPI operations with isolated SQLite and synthetic inputs. The preservation helper's optional named-directory selection supports the actual follow-up owned runs, validates exact directory names, and keeps the original manifest alongside the extended manifest; it adds no production configuration or generic infrastructure.

## Judgement smells

All twelve Fowler heuristics were considered, with no actionable findings. The optional lot identifier has an existing caller and a concrete integrity requirement, so it is not speculative generality. Existing command and simulation shapes are retained without a new forwarding layer, domain hierarchy, workflow framework or scattered ownership. Validation is at the documented execution/freeze boundary. The added tests demonstrate two independent failure modes rather than mirroring an implementation detail.

Standards findings: 0 documented violations, 0 actionable judgement smells. Source-only diff checks pass. The combined diff retains one whitespace flag at `spec-red.log:24`, which is unmodified raw pytest RED output and is excluded from standards findings. The original three dirty documents and `start-roll.ps1` hashes remain equal to their baseline values; the seventh merge checkpoint is recorded in `preexisting-preservation.json`.
