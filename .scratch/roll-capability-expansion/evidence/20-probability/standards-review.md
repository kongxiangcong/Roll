# Standards review

Reviewed the current uncommitted ticket 20 slice against `60703b2d6e332e265a6518102864ace89d1b6975`: probability reference host/worker/method, app routes, probability panel/report integration/styles, and corresponding tests. Original SSE and committed ticket 19 changes excluded. Sources: AGENTS.md, domain instructions, GLOSSARY.md, ADRs 0001–0004, ticket 20, and the code-review smell baseline. Tool-enforced checks excluded. No tests or network requests performed.

No actionable documented-standard violations or Fowler smells found. The worker exposes a numerical scoring boundary rather than another fitting/calibration service; existing shadow/model readers and content-addressed archives remain the source owners.

## Requested source-binding audit

- **[P2] Bind consumed pointers to the frozen model manifest.** At the inspected snapshot, `ProbabilityReferences.source()` compares the mutable model row's `artifact_fingerprints` dictionary to the frozen dictionary, but then consumes the row's input/model/before/after prediction pointers independently. A pointer substitution can retain that dictionary while changing a consumed vector. Verify each consumed artifact pointer against the original archived model-freeze manifest before reading/scoring. The parent has already identified this issue and is implementing the fix and a before/after pointer-swap 409 regression; that uncompleted fix is not counted as verified here. This is a source-integrity correctness finding from the specifically requested audit rather than a Fowler smell.

The inspected persistence uses a unique freeze/key constraint and writer-transaction idempotency recheck. Reads verify the derived manifest and archived method/source without requiring the library runtime. Mature-source rows and excluded rows remain explicit, duplicate conflicts reject, and aligned/default clipping and bin conventions remain separate. The fixed method is archived before vector evaluation. The worker rejects network access, has bounded events/result size and a host-enforced 20-second deadline, and never invokes estimator/calibrator fitting. METHOD CAL reuse is not presented as independent validation or a new qualification.

Inspected supplied logs: API 1 PASS/15.09s; numerical edges 1 PASS/2.94s. Chrome 1 PASS/23.7s and build PASS were reported by the parent, not independently rerun here.

## Focused source-binding repair re-review

The original P2 pointer-substitution finding is **resolved**. Reviewed the focused `source()` checks and isolated SQL mutation regression only. The service now verifies the archived model-freeze manifest against the frozen manifest content, binds the model row's freeze-manifest SHA to it, and compares model, calibrator, input, before-prediction and after-prediction SHAs individually to the immutable manifest. Consumed calibration first/last dates, event, fixed 20-session horizon and instrument scope are checked against the original input/frozen design. Keeping the old artifact dictionary while swapping after→before can no longer substitute the consumed source vector.

The regression expects 409 on the pointer swap, restores the model row, and confirms stored reference retrieval/replay after restarting without the scoring runtime. Inspected `binding-green.log`: **1 passed in 15.18s**. The earlier 201 failure is retained in `binding-red.log`; no test rerun or original-profile operation performed for this review.

Final Standards findings: 0. Open additional boundary findings: 0; original P2 resolved.
