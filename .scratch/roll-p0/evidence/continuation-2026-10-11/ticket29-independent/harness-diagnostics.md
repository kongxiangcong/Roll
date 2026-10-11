# Independent harness lineage

Public run `public-api.log`: 3 PASS / 1 FAIL, 39.22s. The failed execution case stopped at a Windows long destination path during a byte copy before any product assertion. The donor/saved database was never connected. Extended paths and a short fresh target fix only the acceptance harness.

`public-api-completion.log`: the previously blocked execution case PASS; the extra RUN02 harness failed because it called the nonexistent GET `/api/reviews/tasks` and iterated its error dictionary as a task list (AttributeError). Aggregate 1 PASS / 1 FAIL, 38.40s. The supported read-only `/api/reviews/history` now locates the already saved audit; only that case reran in `run02-completion.log`: 1 PASS, 11.37s. No task was created or advanced.

Default byte-integrity process reported `Failed to find real location of C:\Users\72449\AppData\Roaming\uv\python\cpython-3.13-windows-x86_64-none\python.exe`; interrupted that owned process and used the approved Host invocation. Its first invocation incorrectly compared a composite source fingerprint to a raw file SHA (AssertionError at the ninth source guard); only the independent harness was corrected to verify pinned normalized source bytes plus the exact fingerprint recipe. `byte-integrity-final.log` and `byte-integrity-postmerge.log` PASS. These are harness failures, not product RED evidence.

Default noff attempt was rejected by filesystem permissions at `.git/ORIG_HEAD.lock` before merge. The same authorized fixed-OID noff ran in Host permission and succeeded without conflict. No reset, clean, stash, deletion or push occurred.
