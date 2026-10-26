# Spec review: income statement slice

Reviewed current uncommitted ticket 09 financial modules, semantic-reference manifest, API/UI integration and tests. Preexisting dirty SSE changes are excluded. No code changes, commits or tests performed.

## Closed finding

**[P2, resolved] Revision linkage when verified semantics change.** Targeted rereview confirms `collect()` now identifies observations by instrument, statement, report period and fixed upstream/API stream, rather than semantic scope. Changing revenue and `UPDATE_DATE` retains an immutable version 3 pointing to version 2. Scope/unit remain UNKNOWN when the reference no longer matches, and `comparable_with_superseded` requires every scope/currency/unit/period-basis field to be known and equal. This preserves [spec ID-06](../../spec.md) revision history without asserting financial comparability. The new regression changes both fields and checks the chain and false comparability; [revision-green.log](revision-green.log) records 2 PASS/15.68s after the retained RED. No actionable findings remain in this review's scope. This rereview inspected code and logs without rerunning tests.

## Other observations

- Raw HTTP entities are archived before normalization, the date-index original is retained despite the explicit SDK latest-five derived view, and no DataFrame is called an original. The SDK version/source hash and finite transport are pinned. Original monetary fields remain decimal strings; unknown semantics are not guessed.
- Publication dates, first receipt and normalized availability remain separate. Comparative 2025-H1 data explicitly lacks historical PIT eligibility, and semantic-document receipt constrains normalized availability. The UI identifies METHOD, source dates, units, scope, raw fields and originals.
- Tests provide positive fixed-response persistence/UI paths, idempotent repeat/deduplication, failure and cancellation cases. Old/account state is not written. Production parent-deadline/cancellation behavior remains distinct from the injected worker cancellation test.
- The subprocess now flushes each application-received entity chunk and journals its hash/length before waiting for more input. The fixed-response hard-kill regression kills the paused child and checks the surviving 8192-byte prefix, matching hash and incomplete flag. This supports prefix retention on forced termination; it does not count as another live upstream request or a full production cancellation run.
- Real `actual-source/capture.json` records three successful captured entities. SDK/API/browser checks use fixed responses, with API evidence explicitly METHOD and zero network. The independent JS/PDF evidence does not establish a second production API capture. Production API→subprocess→persist→query→UI live acceptance remains outstanding; no acceptance.md existed at review time, and ticket 09 remains in progress. These evidence boundaries must remain explicit in delivery.
