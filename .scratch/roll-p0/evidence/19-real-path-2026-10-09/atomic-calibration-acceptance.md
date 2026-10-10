# Standards P2: atomic calibration prerequisite — 2026-10-09

Base integration: `7eae269a74d5fe87a62cda3b38ed28c99933be65`; scoped implementation worktree/branch `ticket19-real-path` / `codex/ticket19-real-path`.

## Finding and fix

An HTTP metadata preflight can report unused calibration allowance, then a competing family calibration can start before transparent PRIMARY registration. The old PRIMARY transaction checked only its own five-fit budget, consuming a scarce primary attempt even though calibration was already impossible at registration.

Within the existing SQLite `BEGIN IMMEDIATE` in `start_attempt`, exact transparent PRIMARY configuration (`candidate=PRICE_VOLUME_LOGIT_V1`, `purpose=RESEARCH|METHOD_VALIDATION`) now checks the family's calibration attempts before INSERT. Any prior calibration—including aborted/failed/running/interrupted—records `ATTEMPT_BUDGET_REFUSED` and returns HTTP 409 `CALIBRATION_BUDGET_EXHAUSTED`, `attempt_started: false`. No PRIMARY or model run is registered.

This checks availability at registration; it does not promise a reservation of a future calibration slot. Existing calibration transaction checks and immutable attempt history remain in force. Generic manual PRIMARY metadata lacking this exact executor purpose retains its existing primary-budget policy, including arbitrary JSON configuration metadata.

## TDD and checks

The deterministic FastAPI/real isolated SQLite test pauses the external clock boundary at first PRIMARY timestamp, after HTTP admission and before write registration. While paused, another public API call registers and aborts CALIBRATION. Releasing PRIMARY yields the genuine old failure (201 FAILED, primary budget spent), then the required fixed behavior (409, only competitor CAL retained, five PRIMARY slots unused, audit refusal recorded, no model). No internal service/registry/database collaborator is mocked.

Original logs: `atomic-calibration-red.txt` / `atomic-calibration-green.txt`; red fails on HTTP status 201 versus 409, green passes. Compatibility is checked through public manual attempt registration. Final relevant suites are saved in `backend-atomic-final.txt`.

Final result: **23 passed in 134.52 seconds** across `test_training_preflight.py`, `test_transparent_models.py`, and `test_research_protocol.py`. Command: `python.exe -u -B -X utf8 -m pytest tests/application/test_training_preflight.py tests/application/test_transparent_models.py tests/application/test_research_protocol.py -vv --basetemp=.pytest-ticket19-atomic-final`, saved directly through PowerShell Tee-Object. This includes preserved numerical fingerprint, forecast/offline replay, family attempt lifecycle, the deterministic prerequisite race, and generic manual compatibility.

`git diff --check` passed. Numerical `models.py` remains original Git blob `672aee8ab755d092627f9c7c3a08ff2116ffeda4`; no artifact fingerprint compatibility exception. No modules/dependencies were added. No actual runtime DB/source/SEALED/fit/calibration was accessed, historical attempt modified, or research eligibility granted. Test inputs and competing attempts are explicitly engineering fixtures, not real research evidence. Disposable private pytest directories may be removed after tests; no required ignored source originals are created by this fix.
