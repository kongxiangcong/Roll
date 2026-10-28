# 2026-10-28 local project preservation and branch integration

The user requested a commit of all current local project changes and resolution
of the local/remote branch divergence. No publication or model execution was requested.

## Preserved inputs

- `942d98c0`: original `D:/dsh-proj/Roll` working changes, 267 files
  (27 modified tracked files and 240 new project files, approximately 10.5 MB
  of new source/tests/docs/specs/evidence).
- `0275bbdb`: company research/valuation integration, including tickets01–11
  and the actual blocked ticket12 checkpoint.
- `a2a3f56b`: remote terminal workbench, including remote main `aa7b71cc`.
- Common historical base: `e47013fd`.
- Original branches and all history are retained. No reset, rebase, stash,
  force push, database migration, source refresh or model execution.

Approximately 231,830 previously untracked paths were inventoried by name/size.
Local database stores, credentials, dependency/model caches, temporary test
directories and tool state remain on disk. Local-only `.git/info/exclude` rules
hide these runtime artifacts; their contents were not mass-staged. Existing
ignored `.env` and SQLite files were not added. The selected new project files
had no observed OpenAI-key/private-key/JWT literal pattern matches.

## Conflict decisions

- Preserve local assistance cancellation, idempotency and main-board guards,
  alongside identity-bound company research, fixed snapshots and source archives.
- Preserve both the terminal workbench and independent company-report entry.
- Combine multi-company research with the remote finite-list observation sources
  and immutable daily reports. Unsupported price collectors remain explicit.
- Scope new cooldown state by instrument and task kind. Read older research key
  order and the historical JCC-only keys without applying them to another issuer.
- Allow reading already saved history after watch removal, while new collection
  and queued execution still require an eligible holding/watch scope.
- Retain implemented issue/spec status instead of reverting to an unimplemented
  draft. Ticket12 remains blocked; this Git merge is not financial acceptance.

## Validation

| Check | Actual result |
|---|---|
| Python source compilation | PASS |
| Frontend TypeScript and production build | PASS; existing >500kB bundle warning |
| Initial affected backend batch | 53 passed, 4 failed, 280.90s; original failures retained |
| Four corrected failures plus legacy cooldown isolation | 5 passed, 98.49s |
| Shared observation queue after compatibility fixes | 10 passed, 149.92s |
| Offline terminal workbench | PASS; keyboard/cancel/account draft/confirmation/responsive layouts |
| Offline company-report webpage | PASS; task/retry/download/history/company isolation |
| Offline multi-company daily webpage | PASS; switching/pinning/failure/retry/reload/mobile |
| Resolved source conflict-marker and whitespace check | PASS |

The test updates preserve intent under the newly combined features: explicitly
watch a security for a legacy idempotency test, test manual queue execution
before the scheduler checkpoint, accept the now-supported watched-issuer news
request, and use the normalized issuer-local health response key. Test clock
control is METHOD evidence and does not count as a real postclose cycle.

Evidence is in [evidence/](evidence/). Overlapping test runs are not summed as
independent cases. These are merge regressions with isolated/fixed data, not new
real-model or investment-quality acceptance. The user's latest instruction to
keep model requests offline remains in force; the previous four real requests
are preserved and no remaining chapter allocation was used.

The integration is local only. The primary worktree has fast-forwarded to the
verified combined history on `codex/roll-capability-expansion`. Local main has
fast-forwarded to remote main `aa7b71cc` (0 ahead / 0 behind). The combined code
commit `b69b25a5` contains every commit of remote main, remote terminal workbench
and local research/valuation (0 missing commits from each). The primary and
integration worktrees were clean. No push, PR or deployment is included.
