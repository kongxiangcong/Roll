# Spec review — ticket 19 continuation

Fixed point: `01563d6`; reviewed the union of `codex/ticket19-public-history`, `codex/ticket19-historical-calendar`, root `5c64c65`, and the current `scripts/public_history_acceptance.py` change. Sources: ticket 19, Roll P0 spec ID-06/10/14/16/21, project-layout, PRD V1.3.

## Incorrect implementation

- **[P2] Reject a reported zero volume with positive turnover.** In `backend/src/roll/market/sohu.py:44`, the new quality gate only detects positive volume with zero amount; the subsequent VWAP check requires positive shares. A supplier row with zero hands and 10万元 therefore produces `volume_state=ZERO_REPORTED`, `amount_yuan=100000`, `errors=[]` and `model_daily_input_allowed=True`. Reproduced directly against the branch parser using METHOD_CASE data, without runtime or sealed access. PRD DAT-07: “缺失、零成交、休市、当前停牌和获取失败分别编码”; ticket 19 requires “修订、陈旧或缺失输入按协议处理，不使用未来事实.” Treat this contradictory zero as invalid and retain the original; add a FastAPI acquisition regression. The preserved historical-PIT gate currently blocks real training, but the invalid basic-input flag and absent quality warning still misstate the fact.

## Missing / partial requirements already acknowledged

Ticket 19 still lacks its first five real-research acceptance criteria. In particular, “训练、拟合与校准按时间隔离” and “冻结模型、校准器、特征与相关代码/数据指纹” have no qualified real dataset or resulting trained/calibrated artifact in this continuation. The 3,126 current RAW bars, official dividend/status subset, and archived historical annual calendars add evidence, but cannot establish historical versions, complete statuses/actions, independent preregistered windows, calibration support or mature execution rules. The records honestly retain BLOCKED/NOT_PREREGISTERED and unknowns; this is an incomplete intended goal, not an unsupported completion claim. Ticket 20 must remain locked.

## Scope / supported behavior

No scope-creep finding. Explicit SOHU RAW selection, fixed bounded public acquisition, official notices and calendar corrections address ticket 19's remaining data directly. The review found no silent Fuyao/BaoStock dependency in that path, account-fact writes, sealed-result consumption, lowered threshold, or fabricated probability. Historical calendar phases/rules remain UNKNOWN and reconstruction is explicitly not point-in-time proof; archived originals and restart/offline replay preserve the claimed engineering boundary.

Summary: one actionable Spec defect; real research remains partial.
