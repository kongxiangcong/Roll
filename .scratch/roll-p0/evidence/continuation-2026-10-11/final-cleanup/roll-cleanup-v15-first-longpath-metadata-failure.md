# First control-continuation metadata diagnostic

The first metadata-only continuation builder stopped with Python WinError 3 at an already accepted saved Ticket 28 backup raw path exceeding the legacy Windows path limit. The original accepted Preflight remained byte identical; only its exact archival copy and the one-clause v15 executor copy had been created. No source content sweep, private content read, SQLite connection, private move or worktree deletion occurred.

The builder was corrected to use the Windows extended path prefix for metadata-only os.stat and to verify its two already-created control files before retrying. The corrected invocation actually returned CONTROL_CONTINUATION_PASS: all ten corrected source file sets and all 353101 prior proof/inventory metadata entries matched, original acceptance time retained. This is a control continuation of the original complete byte proof, not a second source byte sweep or business acceptance.

First failure: roll-cleanup-build-v15-control-continuation.py line 40, FileNotFoundError [WinError 3], saved path ending test_partial_fill_is_atomic_wi0/data/backups/25a12208-d251-428b-a5c6-079a8772c282/raw/26011a5639447e0e1a291aea852fcde448ba1e0433af5aba5810900b0f455e30.raw.
