# 03: 发布第一份个股研究档案

Status: ready-for-agent

归属：研究流水线 · 个股研究、投资假设与发布。依据：[主方案 §4.1、§4.3–4.4、§6.1、§6.3–6.4、§9.4](../../../docs/design/architecture/roll_v3_trading_pipeline_spec.md)。

**What to build:** 研究者在没有账户的情况下对持仓股或关注股建档。以江西铜业实际公告为例，从产业或盈利问题形成可证伪的投资假设，通过研究 CLI 导入 Markdown 草稿并显式发布 ResearchDossier。

**Blocked by:** None (can start immediately)

## 验收

- [ ] 档案区分披露事实、外部预测、推断与待验证假设。列明证据的来源、定位与时间，以及反证、命题适用条件、验证目标、期限与证伪条件。
- [ ] 发布结果可按版本及生效时点查询，包含 fundamental_gate、thesis_status、strategy_whitelist、invalidation_triggers、evidence_refs、有效期及发布状态。每个约束可追溯到证据或研究者确认。
- [ ] 演示每周或重大公告后的按需刷新，记录新增证据与判断变化。草稿保留为草稿；显式发布后可查看新版的生效时间和旧版原文。外部助手只经公开研究入口交换资料与草稿。
