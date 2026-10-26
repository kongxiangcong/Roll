# Spec review — fixed first integration snapshot

Baseline `f463dcb755c4785a6f07842aeb4231bb210f1010`; snapshot `7fc35604819edf821a81deae35a0606653c1cb79`. Reviewed `git diff baseline...snapshot` and the eight commits in `git log baseline..snapshot`, plus the pending broker-cost settings panel, settings integration, CSS and browser test. No production database, provider, training, SEALED or external calls were used.

## Finding

**[P2] Migrated positions cannot advance beyond the first ADD.** `backend/src/roll/research/policy_successors.py:126–128` compares the current quantity with the immutable migration receipt. A migrated 100-share position can receive ADD 100, but its next evaluation at 200 shares fails `POSITION_MIGRATION_FACTS_MISMATCH`; registering a replacement for the same position fails `POSITION_MIGRATION_IMMUTABLE`. It therefore cannot reach subsequent HOLD or horizon EXIT through the same binding. Ticket 20 requires “ShadowAccount 从冻结现金/持仓基线连续演化” and ticket 25 requires “政策变化保留持仓迁移安排”; the continuation plan calls for “确定性 ADD/HOLD/WAIT/退出/反向冷却/存量迁移计算与原输入重放”. Preserve immutable original migration facts, but distinguish the original migrated lot from subsequent ADD fills and their horizons. The independently forthcoming continuous-shadow slice must prove migrated 100 → ADD 100 → subsequent HOLD/EXIT and original-horizon preservation. This finding applies to the pinned first snapshot; it does not prejudge that slice.

## Other reviewed scope

No additional concrete spec violation or scope creep found in confirmed broker-cost capture/publication/current boundaries, receipt retry UI, or saved action-window binding/forward consumption. UNVALIDATED/NOT_GRANTED and production validity restrictions remain explicit. DATE precision, missing rows, unknown lifecycle and insufficient negative coverage are retained.

This review does not close tickets 20/25/30 or establish source completeness, actual qualification, forward commencement or economic validation. Policy-aware complete successor freeze and continuous execution remain separate required work.
