# Ticket 20 independent merge acceptance

Date: 2026-10-11, Asia/Shanghai. Status: PASS for ticket 20 engineering acceptance after the independently identified non-empty baseline defect was corrected.

Authorized implementation commit: `fe4a98c23f41b417ad65de0fa0415428852bdcbc`.
Local no-fast-forward merge: `72002e20ff830bf47e623a3fa02487018f081203` on `codex/roll-p0-integration`, based on `eabc7a3ae3462821bedc80c2d6c8b2a88d04b19c`. No push.

Correction implementation: `4a099d891360b5f428de4ea6063826b7bcf1524e`; authorized local no-fast-forward correction merge: `b321f40a16bcf7a9ad3d392b7088508f9cce6edb`. This is the stable source version used for the final independent run.

## Independent acceptance blocker

The public complete-freeze API was exercised with cash `100000.00` and one frozen `SSE:600519` holding: quantity `200`, acquisition cost `20000.00`, acquisition date `2025-12-31`, before the frozen CAL window. `POST /api/research/protocols/{id}/complete-freezes` raised `re.PatternError: min repeat greater than max repeat at position 16`. `Position.quantity_valid` passed scale zero to `ledger.number`, producing an invalid decimal regex. The all-cash fixtures did not cover this path.

Reproducer: [independent20.py](independent20.py), initially using only a newly created isolated METHOD runtime at `D:\dsh-proj\Roll\.roll-data\implementation-evidence\20\independent-api-runtime`. The first run failed at complete freeze, before the remaining scenarios. The implementer and root were notified immediately. The correction stays inside ticket 20's position validator; upstream ledger and model dependency sources remain unchanged. The implementation's public red regression is preserved in [holding-red.txt](../20/holding-red.txt).

## Final independent acceptance

The same public-API script ran successfully on corrected integration `b321f40` in a fresh runtime `D:\dsh-proj\Roll\.roll-data\implementation-evidence\20\independent-api-runtime-fixed`. [Structured result](independent20-results.json) records PASS, shadow revision 2, two overlap refusals, actual account version 1, preserved non-empty baseline, restart replay, complete-protocol archive corruption rejection and replay-input archive corruption rejection. Each corruption check restored only its own isolated fixture bytes and verified that no new shadow revision was created. A confirmed account baseline update and an account-conditional diagnostic left the entire saved shadow response unchanged. Mature refused outcomes remained diagnostics and did not create realized strategy losses. Actual/ historical/ shadow/ conditional queries stayed separate; forward start remained null and capability NOT_GRANTED.

[Runtime manifest](independent20-profile-manifest.json) records SHA256 and length for all 193 final independent METHOD files. The final fixed browser runtime is separately retained at `D:\dsh-proj\Roll\.roll-data\implementation-evidence\20\browser-method-holding-fixed`, with all 312 copied files verified; [fixed profile manifest](browser20-fixed-profile-manifest.json). The original browser profile remains historical evidence with its original algorithm fingerprint.

The corrected implementation's single scoped API run passed seven tests in 88.98s, the fresh actual browser flow passed one test in 59.0s, and TypeScript/Vite build passed. The independent script is separate acceptance evidence, not an added test total. No further source edits followed those checks; all twelve ticket 19 fingerprint source files remain byte-for-byte unchanged after both merges.

## Passed evidence at the original merged version

- Root merge acceptance ran the six scoped FastAPI/real-SQLite/statistical-method checks: `6 passed in 74.65s`; [output](merge20-tests.txt). This does not override the independent failure.
- Implementer evidence records six API checks, fifteen upstream checks, the actual browser flow, and TypeScript/Vite build passing before this additional path was found.
- Independent visual inspection of the final browser screenshot confirmed readable ACTUAL/HISTORICAL/SHADOW/ACCOUNT_CONDITIONAL cards, explicit METHOD_CASE and FITTED_UNVALIDATED status, historical price cutoff disclosure, and no formal execution control.
- All twelve upstream ticket 19 fingerprint source files have identical SHA256 and length before and after the merge; [before](upstream19-before20.json), [after](upstream19-after20.json). Initial protected untracked paths remain present and were not modified by merger operations.
- The stopped final browser METHOD runtime was copied to `D:\dsh-proj\Roll\.roll-data\implementation-evidence\20\browser-method-final`; all 312 files were individually verified by SHA256 and length. [Manifest](browser20-profile-manifest.json). This profile records the original merged algorithm and must be retained as historical evidence if the fix changes its fingerprint.

All checks concern deterministic engineering with explicit METHOD fixtures. No production account, credentials, protected real SEALED partition, real research-family budget, forward clock, statistical PASS or capability grant was consumed or claimed.
