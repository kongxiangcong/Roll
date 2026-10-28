# 06 implementation evidence

Date:2026-10-27 (Asia/Shanghai). Scope is ticket06 only;07–12 remain pending. Worktree `D:/dsh-proj/Roll/.scratch/worktrees/rv-ticket06`, branch `codex/rv-ticket06`, initial integration base `4802c99db488e1a675e3320bf2477023c71bdc02`.

## Public behavior and boundaries

[Public service/API and semantics](../../../../docs/research/company-change-api.md) documents explicit same-company snapshot comparison, immutable source/quote context, three change categories, fixed old-path price requirements, parameter/method revisions and ordered model counterfactuals. No new network provider/model call, daily worker/UI, report/PDF or feature export was added. Accounts, ForecastBundle, Decision, CapabilityGrant, ExecutionIntent, old budgets and SEALED were unchanged.

Context children advance overall knowledge `as_of` to actual binding time, while retaining old operating research basis/generated dates and unchanged core. Both source check recency and original material report/disclosure ages are retained separately. A successful zero-new check is not unchanged operations; failed/partial checks do not renew old verification or successful-check dates. Newly versioned hypotheses from the same facts do not become new operating evidence.

The comparison pins05 valuation/economic-review/model references; it never picks an independent latest record. Original04 diagnostics remain unreviewed. CURRENT_PRICING quick summaries deliberately contain no archived current-price scenarios; explicit BASELINE_RESEARCH only exposes safe dated conditional scenarios. Expanded arithmetic has diagnostic-only labels and never upgrades reviews. Missing/adjusted/unknown quote bases, A/H class gaps and incompatible method, scale, currency, scope or horizon are refused with both references and reasons.

A necessary05 defect was found while exercising06 scope comparison: the generated FCFF scope was consolidated even when original drivers/ratio source scopes were partial. New economics reviews now include a hard `operating_scope` check, and safe presentation rechecks older immutable models. Group revenue cannot use a segment margin merely by declaring its forecast consolidated. Old records/source archives are preserved. The original04 calculator/valuation/replay/vendor source bytes remain exact, demonstrated by [five-file Git-base check](method-source-check.json).

## Red/green and honest failures

Tests use the already confirmed public research-service/API, arithmetic and backup/recovery seams. Corruption injection only sets up an externally malformed stored/archive record; the assertion is at the public Backups boundary.

| Slice | Actual result |
| --- | --- |
|01|`red01.txt`: absent perpetual comparison entry; `green01.txt`:1 passed. Helper lives separately in `change_calculator.py`, preserving04 source bytes.|
|02|`red02.txt`: absent command; first implementation script hit default GBK reading Chinese service source before writing that module; `green02.txt` retained missing method failure. Explicit UTF-8/apply_patch correction: `green02b.txt`,2 passed.|
|03|`red03.txt`: absent context boundary; `green03.txt`:3 passed, including independent SUCCESS_NO_NEW/FAILED/PARTIAL and aging.|
|04|`red04.txt`: quote context refused; `green04.txt`:1 passed, complete A/H quote sources and fixed old finite path yearN+1 conditions.|
|05|`red05.txt`: two same-value quotes were wrongly counted as price changes when their source/time refs differed; mixed example already passed. Compare numeric quotation bases separately; `green05.txt`:3 passed.|
|06|Sandbox TestClient attempt produced empty `red06.txt` and stalled. Host CIM initially unavailable in sandbox; escalated CIM identified only PIDs29420/31360 whose full commands included `rv06-red06`; stopped exactly those. Same test outside sandbox: `red06b.txt`404, `green06.txt`1 passed after API/archive/restore/replay implementation. Empty output is not a product result.|
|07|`red07.txt`: same-fact hypothesis re-versioning incorrectly marked new evidence. `green07.txt`:1 passed after separating evidence/hypothesis revision and material/check ages.|
|08|Supplemental acceptance of already implemented refusal boundaries: `review08.txt`5 passed/1 failed because generated scope masked original driver scope. Compare original provenance too; `review08b.txt`5 passed. This was not labeled an invented red cycle.|
|09|`red09.txt`: rehashed quote999 still backed up despite source10; exact quote/fact/time/currency/scope checks added. `green09.txt`:1 passed.|
|10|`red10.txt`: group revenue+segment margin source wrongly conditional. `green10.txt`:1 passed with hard operating-scope review/presentation guard.|

`pre-final.txt` records16 passed before the additional scope-review slice. The final affected regression is saved separately in `final-regression.txt`; completion/count are recorded below only after its actual result. No whole-repository run, real new source/model, browser/PDF or actual after-market cycles is claimed.

## Independent arithmetic and concrete replay

`change_calculator.compare_perpetuity` tests the separate closed form100/10%=1000,100/8%=1250(+25%), with operating cashflow unchanged. At fixed10%,1250 requires125; at fixed100 it requires8%. These are multiple conditional explanations, not identified market motives.

FiniteDCF METHOD case: old revenue1000×margin20%×(1−25%) gives FCFF150, with depreciation20 offsetting maintenance20, no other reinvestment. At10%, EV1500; debt300 less cash100 gives equity1300. Synthetic separate classes A60 and H40, direct HKD→CNY1, quotes10 yield equity1000; quotes12.5 yield1250. Holding years1/2 at150 and all old valuation parameters fixed, year3 terminal FCFF requirements are113.7 and143.95.

Mixed case changes FCFF150→165 (margin22%), quotation10→12.5 and rate10%→8%. Fixed operating→price→parameters order gives equity-minus-market gaps300→450→200→612.5; step contributions150,−250,+412.5. Independent old-path rate-only equity1675 implies an operating/rate interaction37.5. Inputs, each output and the alternate parameter-only reference are in [saved immutable change set](method-change-set.json). This is model arithmetic and path dependence, not unique market causal attribution.

[Actual METHOD command](method-command.txt) and [receipt](method-receipt.json) prove canonical save, exact isolated backup/restore, same DAILY/REPORT child snapshot, matching06 replay, matching original04 arithmetic replay and account version0. All materials/quotes/forecasts in this example are synthetic METHOD inputs, despite the reused test identity; they are not actual 江西铜业 financials or market quotes.05's actual露露 rounded market cap and unknown raw-price basis were not turned into a confirmed quote or used for reverse pricing.

Reproduce from this worktree root, using new empty stores:

```powershell
& D:/dsh-proj/Roll/backend/.venv/Scripts/python.exe -m pytest -c backend/pyproject.toml backend/tests/company_research backend/tests/application/test_backups.py backend/tests/test_assistance.py -q --basetemp=<new-isolated-directory>
& D:/dsh-proj/Roll/backend/.venv/Scripts/python.exe .scratch/roll-research-valuation/evidence/06/create_method_example.py --data-directory <new-method-store> --restore-directory <new-restore-store> --output-directory <new-evidence-directory>
& D:/dsh-proj/Roll/backend/.venv/Scripts/python.exe .scratch/roll-research-valuation/evidence/01/verify_contract_freeze.py
```

The example script uses committed METHOD fixture builders and public services; new executions create new IDs and do not pretend to reproduce old UUIDs. Replay of the stored record recomputes deterministic arithmetic without model/network. Comparison-policy source hashes and original04 method hashes must match installed versions; unavailable versions are refused and archived code is never executed. Existing backup is the portable recovery path;06 adds no standalone JSON bundle importer.

`source-freeze.txt`:27 frozen files/94 gate call sites PASS. `compileall.txt` is empty with successful exit0. Original04 exact source check is5/5. Final test result and integration-tip merge/commit are appended on completion.

Before delivery the isolated branch fast-forwarded the integration tip `9af5d01db9b5e527ca51b29a97416f5b270945bc` (coordination-only change), without conflict. The original working checkout was not edited.

Independent parent-agent read-only check under this06 code: the existing05 restored real露露 review `c29b0d46-576b-4b36-afc5-4c9bef8eccde` in `rv05-real-restored01` remains `BASELINE_RESEARCH conditional/usable=true/2 scenarios`, while CURRENT_PRICING stays blocked with empty scenarios; account version0, no network/model. This verifies the added scope guard preserves the frozen same-scope real conditional case. Original05 evidence/archives were not edited.

Final affected regression: **111 passed,5 subtests passed in509.45s**, after the last product change (`final-regression.txt`). This is the94-test05 baseline plus17 ticket06 cases. `git diff --check` and staged diff check passed. [Staged source-byte check](staged-source-check.json) verifies9/9 relevant staged sources equal their working/captured policy bytes, preventing line-ending drift. Ticket06 Completion complete; whole spec remains in-progress, next07. No additional product changes were made after this final suite.
