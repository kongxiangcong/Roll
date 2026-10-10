# Standards review

Fixed point: `01563d614bf1ea9671b7d1a9fede3edcc4ad1e63`. Reviewed `git diff 01563d6...codex/ticket19-public-history`, `git diff 01563d6...codex/ticket19-historical-calendar`, integration `5c64c65`, and the pending `scripts/public_history_acceptance.py` checkout override.

Standards sources: `.scratch/roll-p0/project-layout.md`, `docs/agents/{issue-tracker,triage-labels,domain}.md`, `GLOSSARY.md`, and accepted ADRs 0001–0003; Fowler smell baseline applied as judgment calls, subordinate to repository rules.

## Finding

- **[P2] Prove the acceptance script owns its HTTP runtime before writing.** `scripts/public_history_acceptance.py:55–62` returns the newly spawned process whenever any service at fixed port 8191 answers `/api/health` with HTTP 200. It checks child exit only after this success branch. If an existing Roll runtime with an empty account occupies that port, subsequent watch, identity, acquisition, and dataset commands can write to it while the report names the fresh `--directory`. This breaches `project-layout.md:121`: tests use “真实 SQLite/隔离归档”. Reject an already occupied port before spawning; use a free port and verify child startup/ownership before the first mutation, including the restart. This is a static control-flow finding; no existing service was mutated to reproduce it.

No other actionable documented-standard breaches or smell findings identified in the public RAW adapter, source registry, historical calendar, official disclosure reconstruction, or fixture cutoff correction. Source/method limitations remain explicit, and no speculative framework was introduced.

Findings: **1 Standards**; worst issue: acceptance runtime isolation.
