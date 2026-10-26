# Independent Spec follow-up fixes

Independent fixed-snapshot review identified two P2s after the initial10-case result. Both were reproduced through public FastAPI/owned synthetic SQLite: **2 failed / 47.02s**, [red](spec-red.log). This does not invalidate or relabel the earlier run; it adds missing scenarios.

Scheduled migration-horizon CLOSE orders now target their immutable `lot_id` and check only that lot's sellability. An original100-share lot@session3 with sellable0 stays unresolved; ADD100 filled at session3 OPEN retains its own session23 horizon and is not stolen by the blocked original horizon at session4. Forecast-driven aggregate exits remain separately checked by the policy.

The successor freeze accepts only an original declared migration baseline. Split `added_lots` or a reduced `original_remaining_quantity` returns422 before any freeze persists. The positive original-lot command succeeds afterward with its original horizon20. Explicit split-lot state remains supported in the separate public proposal evaluator; it is not silently compressed into a baseline.

Current directly affected file: **7 passed / 166.79s**, exit0, [green](spec-green.log). This is the two new regressions plus five existing successor-shadow cases. The unchanged proposal file and earlier10 suite were not rerun. No browser, provider, real training/data/SEALED/grant or notification.

Source/model protections and all previously disclosed engineering gaps remain. Original runtime preservation verified5204 files/331926371B, zero SHA/length mismatches; a Windows path-length copy failure was retained then resumed with extended paths and compare-before-copy, no deletion. New spec red/green runtime directories are appended separately after their processes exit. No cleanup before complete preservation and root acceptance.
