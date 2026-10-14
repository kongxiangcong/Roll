# Standards review

Reviewed committed increment only: `git diff 4cfa76b2cd61e79ef7d2254cfb74b474b5a89c02...d279a0c551d96bb2e7dededd5f77d195aad06a12` (status query, route, UI, tests, and daily-query invalidation). Preexisting working-tree changes excluded.

Sources: root `AGENTS.md`, `docs/agents/domain.md`, `GLOSSARY.md`, ADRs 0001–0004, and the code-review skill's smell baseline. No additional coding standards source was found; tool-enforced checks were excluded.

No actionable documented-standard violations or baseline smell findings found.

Unknown/null handling remains compatible with the pinned producers: listing dates and status effective times may be null; stock suspension end dates may be null; actual resumption remains unknown. Company state descriptions are strings enforced by the existing producer. The query keeps complete receipts, raw hashes, source timing, and original evidence kinds, while returning UNKNOWN, unverified negative coverage, and NOT_GRANTED rather than elevating reported descriptions to complete status.

Daily-query invalidation remounts panels at the start of parent actions and disables inspection during refresh, removing the previously observed stale snapshot. The added browser assertions cover removal after source-policy mutation.

Standards findings: 0. No tests run for this read-only review.
