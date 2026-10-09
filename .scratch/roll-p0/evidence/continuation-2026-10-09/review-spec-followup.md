# Spec review follow-up

Reviewed `d267b84364f024af703c8b2afb93b5ae2c11abdb` and calendar UI correction `c46a22eaafce9e5183f0361c796dafb1c278c17a` against the original Spec finding.

**Resolved:** SOHU now adds `ZERO_VOLUME_POSITIVE_AMOUNT_CONFLICT` when the supplier reports zero volume and positive turnover. The new FastAPI/real SQLite regression verifies preserved reported fields, `quality=INVALID`, `model_daily_input_allowed=false` and a persisted `DATA_QUALITY_ALERT`. The fix record reports precise red/green and 11 passing SOHU tests; this reviewer independently reproduced the parser result on the final implementation checkout. Zero volume/zero amount remains a zero report with no invented suspension inference.

**Resolved:** Market UI accurately distinguishes SSE 2013–2026 calendar coverage from SZSE 2026 and explicitly keeps historical stages/unadapted rules unknown. It does not claim historical execution or point-in-time qualification.

The acceptance record and ticket 19 tracker still state `partial / needs-info`, preserve the first five unchecked real research criteria, and keep ticket 20 blocked. No residual actionable Spec defect found in these corrections. This closes the review finding; it does not complete ticket 19's real training/calibration/model-freeze requirements.
