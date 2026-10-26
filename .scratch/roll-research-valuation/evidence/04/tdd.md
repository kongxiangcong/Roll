# Ticket04 TDD public seams

Previously user-confirmed calculator entry, CompanyResearch/API and Backups. No reconfirmation.
Calculator slice1: full annual FCFF with optional researcher weights; literal worked EV/equity bridge.
Slice2: input rejection, provenance, EPV/sensitivity/reverse and frozen A/H identity.
Slice3: immutable snapshot-bound versions, canonical archives, independent offline replay.
Slice4: API, backup/restore and corruption rejection.

Commands run from rv-ticket04 with python D:/dsh-proj/Roll/backend/.venv/Scripts/python.exe -m pytest -c backend/pyproject.toml backend/tests/company_research/test_valuation.py --basetemp=D:/dsh-proj/Roll/.scratch/rv04-<round>. See captured red/green outputs.
Initial setup attempted relative root paths from backend and failed with StopIteration before writing files or running tests; corrected explicit workdir.

Selection by round: red01/green01 all then-current tests; 02 `-k reverse`; 03 `-k diagnostics`; 04 `-k snapshot_bound`; 05 `-k shanghai`; 06 `-k api_backup`; 07 `-k numeric_origin`; 08 upstream module plus `-k 'canonical or bridge_restricted or ValuationTests'`; 09 `-k optional_sensitivity`; 10 `-k service_ah`. Final includes backend/tests/company_research, application/test_backups.py and test_assistance.py. Each basetemp token matches the output name (04 green retries suffix b/c,06 unsandboxed red06b). No internal mocks were used.

Initial green02 CAGR expected .1767004887 was a transcription error. Independent Decimal(1.6292) ** (Decimal(1)/3) - 1 at precision45 = .17667935510860516426721623608470930711884351; final literal is .176679355108605.
