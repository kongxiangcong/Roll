# Training preflight merge acceptance

2026-10-09. Fixed review: `git diff 81abcb9...1baba13`; commit list: `1baba13 Add read-only research training preflight`. Implementation tip `1baba13dfc0f9b3871833722ccc3a2a07d489e5c` is based directly on integration `81abcb961dd2b628b7466b8ecb08eb249c992a26`; implementation worktree was clean. The 17-file scope comprises the new query, five app lines, application tests, contract and implementation evidence. Parent research files were not modified or staged by the merger.

## Standards

Independent reviewer `/root/historical_costs_merger/preflight_standards`: **0 hard violations, 0 judgement-based smells**. Static review only; no tests or actual runtime data accessed.

- The GET remains composition in `app.py`, calls the same research query, and adds no router/service/repository layers, consistent with `project-layout.md`.
- `training_preflight.py` uses ordinary functions and registered metadata. Its `get`, `dataset` and `attempt_manifest` dependencies only query SQLite registration and events; no partition, source bytes, labels, SEALED, network, fit or mutation calls.
- Application tests use FastAPI with real isolated SQLite. SQL for the legacy fixture constructs a persisted external state; assertions use the public API. Engineering fixtures are distinguished from real research evidence.
- Contract/evidence retain the glossary and ADR 0003 distinction between engineering evidence and actual qualification. No baseline smell identified.
- `models.py` base and tip Git blob are both `672aee8ab755d092627f9c7c3a08ff2116ffeda4`.

## Spec

Independent reviewer `/root/historical_costs_merger/preflight_spec`: **0 substantive findings**: no missing slice requirements, scope creep or incorrect implementation. Static review only; no tests, actual runtime database, SEALED or private credentials accessed.

- New GET reads only registered metadata; it does not enter partitions, labels, originals, network/fitting or write events, attempts, models or qualification.
- Family-wide PRIMARY_FIT/G5 limit five and CALIBRATION limit one count all states, siblings and successors, retaining legacy ownerless records.
- METADATA_ONLY, ready_to_fit=false and inputs/support NOT_CHECKED remain explicit. SEALED independence is not a ticket 19 freeze prerequisite. Protocol 404, purpose 422 and value domain match the slice.
- Unchanged `models.py` preserves existing POST attempt-before-fit and failure accounting. Documentation does not claim actual ticket 19 research completion.

Axis totals: Standards 0 findings; Spec 0 findings; neither axis has a blocking issue.

## Merge and necessary final checks

Scoped `--no-ff` integration merge `f953d71c5d74c740a14fdeb389b52ad110a21709` has parents `81abcb961dd2b628b7466b8ecb08eb249c992a26` and `1baba13dfc0f9b3871833722ccc3a2a07d489e5c`. No conflicts or push. `git diff --check 81abcb9..HEAD` passed; models.py blob remains unchanged after checkout.

Final merged HEAD verification: **5 passed in 38.97s**, exit 0. Exactly four new read-only preflight API tests plus `test_method_artifacts_time_isolation_forecast_and_offline_replay`; implementation's prior related 21-test result remains separate. No repeat of the full 412 suite, browser or frontend checks.

Raw captured stdout is `merge-backend.txt`; command, timestamps, stdout SHA256 and before/after SHA256 are in `merge-test-receipt.json`. App, query, models and both test files remained byte-identical during this run. Test basetemp, invocation helper and raw copies were confined to this evidence directory's `.roll-data/merge-tests`, using the root backend interpreter/configuration and synthetic temporary SQLite/archives. No actual runtime DB, SEALED samples, actual-source qualification, real fits, calibration budget mutation or formal capability accessed. These five cases are fixed engineering evidence; actual source metadata diagnostics belong to the parent task's separate receipts.

This slice does not complete ticket 19 or unlock ticket 20. The merger does not archive the implementation worktree; the parent owns preservation and managed archive. Only this acceptance and the merger's two captured test files are committed by the merger; parent evidence/index scope stays separate.
