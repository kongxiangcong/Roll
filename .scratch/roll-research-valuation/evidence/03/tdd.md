# TDD commands

All commands ran with explicit workdir `D:/dsh-proj/Roll/.scratch/worktrees/rv-ticket03`, public research/API/Backups seams confirmed by user. Interpreter `D:/dsh-proj/Roll/backend/.venv/Scripts/python.exe`; environment `PYTHONPATH=backend/src`. Each run used a unique workspace-local --basetemp. MODEL fixtures are METHOD only.

```powershell
& D:/dsh-proj/Roll/backend/.venv/Scripts/python.exe -m pytest backend/tests/company_research/test_analysis_snapshots.py -q --basetemp=.scratch/rv03-test-red01
```

01 red used all current tests (one), green01 same, green01b same after hash correction. 02 red used `-k candidate_rejects`, green02 all current (two). 03 `-k model_failure`; 04 red `-k freeze_preserves`, green04 all current (four); 05 `-k snapshot_api`; 06 `-k backup_restores`; 07 `-k stale_candidate`; 08 `-k one_disclosure`; 09 `-k reusing_published`. Replace basetemp with the corresponding filename token. Each stdout/stderr capture is the matching `redNN.txt`, `greenNN.txt`, suffix b where retried. Red05/green05 sandbox runs stalled and were terminated; red05b reran the prior API without the new routes outside sandbox and produced 404, before restoring routes for green05b.

Security regression uses `-k 'malicious_source or wrong_company'`, basetemp `.scratch/rv03-test-security`; captured as `security-regression.txt`. It exercises existing bounded runtime behavior with an external METHOD process, not a real model. All network/model acceptance is separately `real-command.txt` and `attempt01/`.

Final affected regression:

```powershell
& D:/dsh-proj/Roll/backend/.venv/Scripts/python.exe -m pytest backend/tests/company_research/test_analysis_snapshots.py backend/tests/company_research/test_shared_evidence.py backend/tests/application/test_backups.py backend/tests/test_assistance.py -q --basetemp=.scratch/rv03-final-regression
```

Windows child-process/API/backup runs used escalation because sandbox TestClient stalled. No dependency install or old gate relaxation was used. Final compileall, freeze verification, git diff/check and integration merge are recorded in README/verification output.
