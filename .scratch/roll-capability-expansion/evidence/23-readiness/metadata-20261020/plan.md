# Historical real-family metadata audit

2026-10-20; baseline b21796e. Prior goal turn made product/evidence progress. Current continuation checks a concrete omission in the previous two-store inventory: P0 ticket19 names `.roll-data/reconstructed19-v1` as its actual research store.

Read only named SQLite stores `.roll-data/reconstructed19-v1`, `.roll-data/reconstructed19`, and the startup script's default `%LOCALAPPDATA%/Roll`. Use SQLite mode=ro and query_only, one read transaction per store. Project only protocol identity/lineage, dataset provenance/use, attempt identity/category/status/timestamps and terminal event status. At most100 protocols/100 attempts/200 terminal event metadata records per store; abort instead of truncating silently. Do not read label values, dataset partitions, result metrics, configurations, archives or SEALED material. No app startup, migrations, new registration, fitting, CAL use, network or financial mutations.

Budget arithmetic follows existing registry.py family lineage and feature_protocol.py shared5-fit/1-CAL limits, including failed/aborted attempts. Observed copies are never summed as independent budgets. Purpose is to locate the actual family and determine whether a lawful ready frontier exists, not create one.

Before the corrected audit: sandbox LOCALAPPDATA resolves to an isolated package directory, not the user's normal startup destination. Initial audit.json retains this observation and must not be used to assert the host store is absent. The explicit host path `C:/Users/72449/AppData/Local/Roll/roll.sqlite3` was confirmed to exist; corrected audit-final.json reads that named path under the same metadata-only bounds. No broad store scan.
