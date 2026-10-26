# Baseline verification — 2026-10-26

Integration baseline: ebe3fc88388767731e96504b36dcb5173082b392, parent e47013f.
This baseline snapshots pre-existing production/source/documentation changes from the original checkout. It is not newly implemented valuation functionality. The original checkout was left untouched. See ../../baseline-paths.txt for the copied paths.

Command, run from integration worktree backend/ with the existing Python runtime:

```powershell
& 'D:/dsh-proj/Roll/backend/.venv/Scripts/python.exe' -m pytest tests/test_assistance.py tests/application/test_sse_daily.py tests/recovery/test_sse_daily_process.py -q --tb=short -o faulthandler_timeout=40 --basetemp=D:/dsh-proj/Roll/.scratch/rv-baseline-temp02
```

Actual result: **28 passed in 100.63s**. This was an offline regression suite using existing fixtures, not a real source/model acceptance run. No new tests were authored.

Earlier attempts retained as limitations: default sandbox Temp caused 20 fixture setup errors (8 tests passed); a retry using a workspace basetemp made progress but was interrupted after prolonged silence. The final run requested execution outside the sandbox for Windows ACL and child-process recovery behavior, used a new isolated workspace directory, and completed successfully. No product changes were made to bypass these conditions.

New-code testing is pending the public-boundary confirmation required by the invoked TDD skill. No live financial source or model was called in this baseline check.
