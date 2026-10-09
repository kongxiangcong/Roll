# Ticket 19 backend admission slice — 2026-10-09

Base: integration `1bf2260`; implementation branch `codex/ticket19-real-path`.
Seam: existing FastAPI commands/queries, actual isolated SQLite and archives, per project-layout and TDD skill.

## Delivered

- `POST /api/research/protocols/{id}/models` with RESEARCH now uses the existing metadata-only training preflight **before** a primary attempt is registered. Known source/window/path/support-readiness gaps return HTTP 409 `TRAINING_ADMISSION_BLOCKED`, blockers/checks/budget and `attempt_started: false`.
- Repeated admission rejection preserves family history, models, account/audits and unused budget. Regression explicitly retains two old FAILED primary attempts and the remaining three primary/one calibration allowances, including across restart. Damaged source bytes prove the metadata gate does not decode source or partitions to rediscover known gaps.
- METHOD_VALIDATION accepts only the registered METHOD_CASE source kind; it cannot relabel PUBLIC inputs. METHOD_CASE cannot become RESEARCH. Admission failure consumes no attempt.
- An already exhausted family calibration allowance blocks starting another METHOD primary fit. Started fits still use the existing transactional primary and calibration checks, and failures/interruptions are retained.
- Existing METHOD numeric diagnostics/forecast/replay semantics stay explicit: the synthetic fixture's 20 total CAL labels remain below the real 20-per-class criterion and cannot be real acceptance.

## Red/green evidence

Original stdout: `admission-red.txt` / `admission-green.txt`, `purpose-red.txt` / `purpose-green.txt`, `calibration-budget-red.txt` / `calibration-budget-green.txt`. Each red fails at the public HTTP status boundary (201 where 409 is required), each final green passes.

Windows restricted-token pytest setup could not enumerate its newly created mode-0700 private directories (WinError 5), before the test body. The failed setup was not counted as a red business result. Tests were rerun with the authorized elevated interpreter and separate private basetemp directories in this implementation worktree. Two test-fixture fixes (existing source directory and required predecessor lineage) preceded final purpose green; neither changes production admission behavior.

The initial broad five-module and first redirected four-module runs were interrupted while still running and are not passes. The final visible four-module regression passed **24 tests in 122.94 seconds**, recorded in `backend-regression-final.txt` from successive tool stdout chunks (CRLF normalized). Command: `python.exe -u -B -X utf8 -m pytest tests/application/test_training_preflight.py tests/application/test_transparent_models.py tests/application/test_research_acquisition_import.py tests/application/test_research_protocol.py -vv --basetemp=.pytest-ticket19-regression-visible`. Full suite is run after root integration. `git diff --check` passed.

## Explicit incomplete work

This is an independently useful admission/budget guard, **not** a qualified real training implementation. Existing acquisition registration has no host-verifiable historical PIT/status/complete-rights admission contract and no registered real DEV/CAL windows. `features()` still refuses all non-METHOD facts, executions have no qualified real label path, and model/calibrator/forecast/freeze remain METHOD-only. `REAL_TRAINING_PATH_NOT_IMPLEMENTED` and unchecked-input/support blockers therefore remain truthful; no boolean claim, mock, current snapshot or removal of blockers grants readiness.

No actual runtime, actual source partition, real label, actual research SEALED data, real fit/calibration, capability or forward start was accessed or changed. Existing isolation regression cases access only explicitly synthetic test partitions. No new modules or dependencies. Ticket 19 remains partial and ticket 20 stays blocked. Known cash-rights work can be integrated separately but cannot confer complete event coverage or real training eligibility.
