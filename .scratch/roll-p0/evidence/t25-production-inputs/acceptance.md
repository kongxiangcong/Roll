# Ticket 25 production cost input chain — 2026-10-14

Implemented from integration `f463dcb` in isolated `codex/t25-production-inputs`.

## Delivered boundary

Public FastAPI registration, version history and fee estimate use isolated real SQLite. Confirmed tariff records require explicit account/funding versions, SSE MAIN STOCK scope, a source-declared effective interval, commission including regulatory charges, minimum commission, separate transfer rate, source name and original UTF-8 basis. Values have no financial defaults. Original source text CRLF is retained and checksum checked. Registration never issues or edits capability grants.

ACTUAL action capture binds the last tariff snapshot and derives BUY reserve fees using the existing execution fee engine at the captured upper price and frozen quantity. Missing/stale/scope-mismatched/corrupt costs remain concrete gaps. Writer publication rechecks the tariff state; future cost-bound cards also check revision, interval and source restrictions. METHOD packet fees and qualification are unchanged and tariff settings do not enter METHOD capture authority.

No existing frozen production action lifetime or quote age rule was found: the production path still uses the existing expired cutoff; it now also reports `PRODUCTION_ACTION_VALIDITY_POLICY_NOT_FROZEN`. Cost intervals do not become action authorization. No TTL or future action expiry was invented. No production grant, real account data, original research SQLite, provider request, training/fit, SEALED access, notification delivery or frozen math/source was changed.

## Red and green evidence

Existing venv `D:/dsh-proj/Roll/backend/.venv/Scripts/python.exe`; PYTHONPATH `backend/src;backend/tests/application;backend/tests/support`. Every test used a separate `.scratch/t25-cost-*` basetemp in this worktree. First sandbox launch could not access the uv Python runtime; existing runtime worked with authorized escalation, no dependency installation.

- Registration red2: 1 failed, 7.83 seconds, public POST returned 404. Initial green1: 1 failed, 7.59 seconds, future source interval incorrectly used factual timestamp validation. Source interval ISO/timezone validator corrected; green2: 1 passed, 7.20 seconds.
- ACTUAL snapshot red3: 1 failed, 1 passed, 13.35 seconds; tariff revision did not change evaluation ID. After capture/publication integration green3: 2 passed, 12.60 seconds.
- Current status red4: 1 failed, 2 passed, 19.10 seconds; `current_status` absent. Green4: 3 passed, 18.18 seconds. Literal fee 6.20 = 6.00 commission plus 0.20 transfer at gross 20000, scope and effective interval reject unknown inputs; funding revision restricts current facts.
- Source corruption red5: 1 failed, 7.83 seconds; latest tariff still displayed confirmed after basis bytes were corrupted. Green5: all 4 new tariff cases passed, but a legacy `test_actions` METHOD case failed with no BUY. This old uncontrolled current-anchor test is not claimed as passing.
- Current clock-bound METHOD regression plus all tariff tests green6: **5 passed, 31.05 seconds**. Existing paired independent risk and BUY remain REDUCE100 → BUY200, 10005 reserve, unchanged immutable replay, no release of existing exposure. No simulated input was promoted to production qualification.

The public ACTUAL test covers snapshot receipt binding, refusal and replay without a grant or model fitting. The ACTUAL forecast/complete-freeze numeric capture consumer is implemented but not end-to-end exercised with a real production grant; such a grant does not currently exist. Writer/current checks on future ACTUAL cost-bound decisions are implemented without inventing one for acceptance.

Ticket 25's source-bound cost registration/consumption engineering is delivered; formal action validity still requires an explicit frozen policy and real qualification. Root owns UI, independent acceptance and task status.
