# 02 TDD execution

Base and integration: 13caf303195c5316000eb906911d86e7f67d6d02; ancestor check passed and worktree clean before claiming.

Public boundaries already confirmed by user: CompanyResearch public service / HTTP API, and existing backup/recovery entry points. Tests use isolated Ledger/EvidenceStore and actual SQLite/original archive. Source HTTP is mocked only at transport boundary. Identity registration/resolve, material/fact/check consumers and backup export are caller-facing boundaries. No private helpers or SQL asserted as test outcomes.

Vertical cycles and actual outputs are appended below.

| Cycle | Observed red | Observed green |
| --- | --- | --- |
| 01 identity/AH/ambiguity | Missing company module, collection error | 1 passed |
| 02 shared material/unknown time/reopen | Missing MaterialCommand | 2 passed |
| 03 restatement/conflict/company isolation | Missing fact commands | 3 passed |
| 04 check coverage/last success | Missing CheckCommand | 4 passed |
| 05 fact basis/storage fault boundaries | 2 failed, 4 passed | 6 passed |
| 06 existing market archive reuse | Missing ExistingSourceCommand | 7 passed |
| 07 HTTP import/download/no account confirmation | Expected route returned404 | Selected1 passed |
| 08 backup/recovery/structured corruption | Corrupt JSON was not refused by backup | Selected1 passed |
| 09 actual financial/news source shapes | Wrong balance start and news body receipt | Firstgreen:1 passed/1 fixture failure; corrected fixturegreen09b:2 passed |
| 10 existing identity/source URL safety | Conflicting existing identity was not refused | Selected1 passed |
| 11 public pagination/internal correctness | Page parameters absent | Selected1 passed |
| 12 existing receipts/unchanged capture dedup | Existing-source supplier returnedFAILED | Selected1 passed |

Final regression command (run from worktree root with existing Python; Windows ACL/process behavior outside sandbox):

```powershell
& 'D:/dsh-proj/Roll/backend/.venv/Scripts/python.exe' -m pytest backend/tests/company_research/test_shared_evidence.py backend/tests/application/test_company_research_sources.py backend/tests/application/test_backups.py backend/tests/test_assistance.py -q --tb=short -o faulthandler_timeout=45 --basetemp=D:/dsh-proj/Roll/.scratch/rv02-final01
```

Actual result **42 passed in246.15s**. New service/API/source/restore behavior tests and existingbackup/assistance tests are alloffline/METHOD; the separate reallocalPDF receipt is not a freshsource/model acceptance. All red/green output files are retained, including the malformed test supplier failure. No production validation rule was loosened for that supplier.
