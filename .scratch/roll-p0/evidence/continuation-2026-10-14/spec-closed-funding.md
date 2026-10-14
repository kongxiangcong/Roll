# Spec review — factual tariff registration with closed funding

Fixed delta: `555ab7a..7311e68508a9f7d54043210f40f98da92f696d87`. Reviewed the one-line production change, two parameterized public API cases and `t25-production-inputs/closed-funding.md`. No tests or actual databases/provider/training/SEALED/external calls were performed.

**No actionable spec finding in this narrow delta.** Removing the `funding.state == CONFIRMED` precondition allows confirmed tariff facts to be saved while funding is REVOKED or PAUSED. This follows the spec boundary that, without sufficient judgment authority, users can “继续使用账户与观察功能”. It does not change the separate requirement that formal suggestions require “确定性资格检查及用户资金启用均满足条件”.

Exact current tariff/account/funding versions remain checked inside the same SQLite writer transaction; positive account/funding versions remain required by the command schema. Idempotent receipt retrieval, source archiving, decimal constraints, scope and effective interval validation remain unchanged. The confirmation writes only the tariff record/archive, retaining `system_usable=false` and `USER_CONFIRMED_COST_FACT_NOT_CAPABILITY_GRANT`.

The new tests exercise both revoked and paused funding, assert successful factual registration, unchanged funding JSON, empty allowed actions and no grants. The owner records two red cases followed by four passing cases, preserving the distinction between factual registration and funding resumption. Those results were inspected, not rerun by this reviewer.

Three attempted read commands initially failed at the MXC launcher with HRESULT `0x80070020`; a scoped elevated read then succeeded. These are tool-launch failures, not product/test evidence. This review establishes neither whole-ticket completion nor formal eligibility.
