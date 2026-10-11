# Final review repair handoff — awaiting independent acceptance

Fresh own tree `.scratch/worktrees/final-review-fix`, branch `codex/roll-p0-final-review-fix`, accepted base `fbc8bd58c48b40c82e664970d211e88a060bdd19` (ancestor verified). Scoped product `e75c14e`; parent docs-only `897d76b05aab38d976719830063fde72b4feda53` merged as `bbb84a57f624dec9351b32373fd9d10e1447eed3`. Independent Spec follow-up found the concrete first-lookup race; owner repaired it as `4a975c629379cba4cbee34178bf5d2ac4452d87c`. Root owns final ticket completion and aggregate ledger; the frozen-policy/production-fee/expiry partial remains unchanged.

## Concrete behavior and authority

1. `Capabilities.current` presents its already-checked immutable grant/lifecycle/recovery facts. `formal_judgment=ENABLED` requires an actual system-usable `GRANTED` status; qualified METHOD stays DISABLED. Profit, independent risk, their scopes and engineering scope are separate. Current projection contains no fresh clock/random field. Per-grant queries project only that grant; global projection does not let a last METHOD conceal another valid capability. Today/settings consume host headline. No admission conditions, financial thresholds, fitting or actual qualification changed.
2. Reports preserve absent risk proposed fee as `None`, `proposal_fee_status=UNKNOWN`, `fee_comparison=PROPOSAL_FEE_UNKNOWN`. Actual confirmed SELL fee remains a separate known 7.00 in both REDUCE/EXIT cases. Existing frozen BUY fee comparisons remain intact. JSON/text report export is read-only; saved shadow result remains byte/semantic unchanged.
3. New `execution_intent_prepare_receipts` stores the entire first prepared response atomically with the intent. It is a different command domain from existing declaration receipts. Exact prepare retry consults this immutable receipt before journal refresh/current action gates and rechecks under writer lock. First receipt and legacy queries are in one explicit read snapshot. Current listing/reservation/partial fills remain current; receipt recovery does not authorize another intent. Content conflict409; new key with old action409. Existing mutable intent/minimal event lacks original full response: explicit `LEGACY_PREPARE_RECEIPT_UNAVAILABLE`, with no speculative backfill.
4. Maintenance and qualification are collapsed by default. Material/review dropdowns read existing strictly checked saved materials and existing per-material CODEX runs. Stored conclusion/experiment/evidence limits remain visible; missing review disables submission. Proposal/admission still performs existing host checks. Material archive errors remain concrete errors rather than silently treating materials as usable. The supplementary list is read-only and reuses `get_material` checks.

## Actual test executions, kept separately

| Stage / original log | Result | Scope |
|---|---|---|
| red-capability.log | 1 FAIL / 11.92s | Real public METHOD status lacks host headline |
| green-capability.log | 1 PASS / 8.22s | First vertical slice |
| green-capability-all.log | 5 PASS, 1 FAIL / 18.67s | Owner found per-grant pause headline wrongly borrowed another METHOD grant |
| green-capability-scope.log | 6 PASS / 20.79s | 3 public SQLite cases and 3 pure display-contract cases, distinct evidence levels |
| red-risk-report.log | 1 harness FAIL / 4.86s | Disposable donor copy destination long path; before TestClient/SQLite connection, not product red |
| red-risk-report-short.log | 1 FAIL / 12.77s | Actual public REDUCE→prepare→confirmed SELL→report500 |
| green-risk-report.log | 2 PASS / 22.65s | REDUCE/EXIT, actual SELL allocation, original shadow, JSON/text |
| red-prepare.log | 1 FAIL / 7.77s | Same-key prepare returned mutated OPERATION_PENDING intent |
| green-prepare.log | 2 PASS / 13.94s | Immutable retry through permission/expiry/restart and partial/successor evaluation |
| red-saved-materials.log | 1 FAIL / 6.53s | Required read-only saved list404 |
| green-saved-materials.log | 1 PASS / 5.46s | Original checked archives unchanged, no review/grant started |
| red-settings-chrome.log | 1 FAIL / test11.7s | Actual Chrome default folding absent |
| green-settings-chrome.log | 1 PASS / 17.5s | Actual Chrome fold, material/review selection, host refusal, today DISABLED |
| green-prepare-legacy.log | 1 PASS / 5.81s | New verified copy of real pre-fix public runtime; missing original receipt boundary |
| affected-callers.log | 15 PASS / 138.66s | Restore lock, old permission/expiry callers, competing prepares, existing read-only reports |
| green-settings-research-chrome.log | 1 PASS / 17.6s | Same product source, fresh Chrome profile; explicit research registration navigation/disclosure added |
| red-prepare-race.log | 1 FAIL / 7.22s | Two public requests, actual empty SQLite fetch paused; B201 committed then A wrongly409 LEGACY |
| green-prepare-race.log | 3 PASS / 17.48s | Race returns identical201; original legacy and conflict/permission/expiry/restart preserved |
| frontend-build.log | PASS | TypeScript + Vite66modules using installed shared dependencies |

These are separate executions, not a claimed single whole-suite run. No benchmark was run or old performance receipt overwritten. Three actual-GRANTED display literals are explicitly parent-approved pure projection contracts: no host admission, archived G-gate evidence or real grant was produced. Public positive grants all remain source-bound METHOD_ENGINEERING with `system_usable=false`. Browser review uses the preexisting fixed local worker only: synthetic authentication, METHOD material, blocking real-evidence issue; it is not an actual OpenAI review. Existing affected notification test uses only `httpx.MockTransport` at `ntfy.example.test`, not real channel delivery.

## Original legacy capture, preservation and guards

The closed `red-prepare` runtime was opaque-copied into root `.roll-data/implementation-evidence/final-review-fix/legacy-profile`: 32 files / 2431548 bytes, dual source/target0mismatch, no SQLite connection. `legacy-profile-manifest.json` SHA256 `b42835a26089245b8435c14f827e3bc3afc550b6c8d2401f9636ac561e2e6cca` is pinned by the public legacy test; original JSON bytes including CRLF are preserved. The test connects only another freshly verified copy. The externally captured original API response is evidence, not guessed DB migration input.

`source-guard-before.json`, `source-guard-final.json`, `source-guard-race-final.json`: exact current15 protected sources in both root and own tree (30 checks per guard), 3 separately allowed model/calibrator/config bytes, original real19 SQLite checksum only, all0mismatch. Current Roll production source inventory75. Original real19 stays165814272bytes / `ec46257c4420f69c245791778c49079355700615cc3ed7b94d8027bd4dcf66c4`; no original SQLite connection. Research donor copied from the pinned193file METHOD manifest before any connection, with dual byte checks.

Runtime full-union preservation final counts and source/target mappings are in `runtime-preservation-manifest-v2.json`. Source groups include every owned `.fr` red/green/failed/mid-run profile, own pytest cache and built dist. Exact private exclusions are metadata-only; all original tree files remain. Root/shared dependency junction is declared and not copied. No deletion, push, root index mutation or protected artifact writes.

Historical preservation attempt `preserve-first-attempt.py` stopped at normal destination `stat` on a long path after157 verified files (158th copied but validation failed). Its partial independent root namespace `runtime`, original log and diagnostic remain; new `runtime-v2` uses extended Windows paths for mkdir/copy/hash/stat/enumeration. Failure occurred alphabetically at `test_json...`, before private notification lock; it was not read/hashed/copied. First CIM serializer attempt hit PowerShell automatic `$Matches` collision and wrote no saved receipt; successful `cim-process-proof.json` and `cim-before-preservation-v2.json` use named arrays and show own/shared project candidates0, no stops. Raw CRLF fixed manifest produced initial `diff --check` warnings; evidence-only attributes now retain exact raw bytes while treating CR-at-EOL correctly. No history or pinned SHA was rewritten.

Final runtime preservation: 4872 files / 299928587 bytes / 9744 dual endpoint checks / 0 mismatches, exactly5 private metadata exclusions, no SQLite connection. Manifest 3651911 bytes, SHA256 042deedef5f872cb935cb6929eb913f4104955e026d523545a6f612e831684ee, source product4a975c6. Legacy32 is a subset of the same normalized own source union, retained separately for fixture use; do not inflate union by adding it twice. Private auth writer pointer correction: original v2 manifest's line22–24 hint refers to the fixture cases; the actual synthetic auth writer is final_review_method_app.py lines19–21. The exact file/producer identity is unchanged, raw manifest bytes are preserved. channel.lock is also excluded metadata-only (not reached by failed first copier). Final preserved-final protected guard30 plus separate3/original19 remains0difference; CIM after preservation shows own/shared executable+argv candidates0 and no stops.

Git evidence check retains generated pytest/Chrome log trailing spaces literally; final evidence-only *.log -whitespace avoids diagnosing the raw tool output as source style. Source, tests and Markdown checks remain enabled. The failed raw-log check was not normalized or hidden by rewriting its original bytes.
