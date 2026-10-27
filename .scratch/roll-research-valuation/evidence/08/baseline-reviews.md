# Independent baseline check of the two wide-suite failures

Actual root run, 2026-10-27 Asia/Shanghai. This is an engineering fixture check, not a real post-close cycle or live account/model/source run.

Checkout: `D:/dsh-proj/Roll/.scratch/worktrees/rv-ticket01`, HEAD `2491d98c4da6c734c11154b0a8535ff15a7313d7`. Verified `git diff --name-only ebe3fc88388767731e96504b36dcb5173082b392 HEAD -- backend` produced no paths, and `git status --short` was empty. Thus production backend AND the two tests are identical to the pre-feature captured baseline, despite ticket01 documentation changes.

Command from its backend directory, existing Python runtime, with `PYTHONDONTWRITEBYTECODE=1`:

```powershell
& 'D:/dsh-proj/Roll/backend/.venv/Scripts/python.exe' -m pytest tests/application/test_reviews.py::test_normal_close_keeps_actual_gap_and_overdue_calendar_maintenance_checked_once_on_resume tests/application/test_reviews.py::test_running_day_audit_records_only_actual_seen_days_without_creating_observations -q --tb=short --basetemp=D:/dsh-proj/Roll/.scratch/rv08-root-baseline-reviews01
```

Actual result: **2 failed in 19.27s**, exit1. The following is a concise transcription of observed tool output, not a new raw process-output file:

- `test_reviews.py:192`: expected mature_labels.status `NOT_CONNECTED`, actual `CHECKED`.
- `test_reviews.py:443`: expected unfinished_execution_intents.value `None`, actual `0`.

These are exactly the assertions and actual values in ticket08's retained wide result (`177 passed, 5 subtests passed, 2 failed in 959.72s`). This establishes that those two failures already reproduce in the captured baseline; it does not turn the wide suite green or prove every later report-host revision correct. Do not restore stale disconnected-business behavior merely to satisfy them. Retain them as known baseline mismatches and separately run relevant new/affected checks after actual fixes.

No source/test edits, real model calls, market-source refreshes or real-account changes were performed by this check. Its fixture temporary database is separate from real stores. No hypothetical clock run counts toward ticket12's actual cycles.
