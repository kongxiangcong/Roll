# Ticket25 additional historical runtime preservation

This is preservation only, after Ticket25's independent acceptance at `759033c8bf87af1fecd7dff9021232b33542df0b`. It does not rerun or upgrade historical acceptance results.

- Source retained: `D:/dsh-proj/Roll/.scratch/worktrees/ticket25`.
- New independent destination: `D:/dsh-proj/Roll/.roll-data/implementation-evidence/ticket25-cleanup-additional-2026-10-11`.
- Copied and verified: **10,108 files / 824,294,955 bytes**.
- Each copy was checked against its original SHA-256 and length immediately; a second complete pass verified both source and destination against those original values. Source modification times also remained unchanged.
- Copy failures: **0**; `roll-ticket25-cleanup-additional-failures.json` contains `[]`.
- Classification: 8,088 raw archive files; 611 opaque SQLite-family files; 1,409 other runtime records. No dependency or cache files occurred in the uncovered runtime inventory. SQLite/WAL/SHM were copied as bytes only, without a SQLite connection.
- Six `auth.json` files, **432 bytes by filename metadata**, were excluded from reading, hashing and copying. Their exact pytest paths map to tracked `METHOD_CASE_ONLY` fixture definitions in `backend/tests/application/test_codex_only_scope.py:52-59` and `backend/tests/application/test_capabilities.py:301-306`. This is provenance from fixture definitions, not a content assertion. They remain in the source tree; root owns their eventual cleanup decision.
- Existing five manifests cover 3,135 unique source paths / 264,329,777 declared bytes; their manifests and archived targets were not overwritten or rehashed. Together with this addition, coverage is 13,243 source paths / 1,088,624,732 declared bytes; the six excluded authentication fixtures account for the remaining paths of the 13,249-file runtime metadata inventory.
- The coverage JSON contains **46** runtime prefixes with uncovered files. The old plan prose says 45; that plan was left unchanged and the actual 46-prefix mapping is retained here.
- Source/destination ancestors and all 58 inventory runtime directories were ordinary directories. Runtime inventory found no reparse entries. The dependency junctions `backend/.venv` and `frontend/node_modules` were outside this scope and were not traversed.
- Source HEAD remained `759033c8bf87af1fecd7dff9021232b33542df0b`; tracked files and index were clean before and after. No Git mutation, application import, test, provider call, model fitting, database connection, deletion or cleanup occurred.
- The attached before/after checksum list covers exactly **12 frozen source files + 3 allowed artifact/config files + original Ticket19 SQLite** (16 entries), all unchanged. This is not the current root's protected 15-source list; root separately owns its final 15-source verification. The original19 SQLite checksum remains `ec46257c4420f69c245791778c49079355700615cc3ed7b94d8027bd4dcf66c4`, 165,814,272 bytes.
- The earlier successful exact-tree process inventory with count 0 is cited from `roll-cleanup-batch-metadata.json`; no new process query or process termination was performed.

Evidence alongside this report:

- `roll-ticket25-cleanup-additional-manifest.json`: complete source/destination mapping, per-file SHA/length, final verification and exact checksum guards. SHA-256 `24b5e32692348db6459ef14f96e546f9ed12373b79bdce012d5a713b49f2472d`, 8,717,987 bytes.
- `roll-ticket25-cleanup-additional-report.json`: counts, scope, before/after source state and per-prefix counts.
- `roll-ticket25-cleanup-additional-inventory.json`: metadata-only original runtime inventory and coverage comparison.
- `roll-ticket25-cleanup-additional-exclusions.json`: six unread/unhashed/uncopied fixture paths and tracked fixture provenance.
- `roll-ticket25-cleanup-additional-boundaries.json`: metadata-only ordinary-directory boundary checks.
- `roll-ticket25-cleanup-additional-failures.json`: retained copy diagnostics, currently empty.
- `roll-ticket25-cleanup-additional-execution.json`: utility exit statuses and nonfatal Python launcher warning.

The original worktree remains intact. Independent acceptance and any cleanup are root-owned follow-up actions.
