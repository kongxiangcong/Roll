# 09 production integration Spec review

结论：本次独立整链验收已补齐 [ticket 09](../../issues/09-income-statement.md) 原剩余运行路径，可在同步更新 ticket、acceptance 与 handoff 后标记 complete；未发现新的实质缺陷，开放项 0。这里只读检查代码、保存响应、封口回执与浏览器日志，未执行测试、联网或取数。

- `integration-plan.json` 明确一次独立授权及隔离 `.scratch/r09real`，未重开旧 SDK/JS/PDF 预算。执行脚本断言生产 `financial.worker is None`，配置真实隔离 SDK 子进程，以公开 collect API 完成持久化及查询，没有固定响应注入。
- `integration-attempt.json` 已 `CLOSED_NO_RETRY`：COMPLETE、3 HTTP、5 facts、3 原响应逐一下载校验 SHA、账户前后相同。保存响应为 REAL_ACQUISITION；出版日期、更新日期、首次收到和 available_at 分离，合并/CNY 元/年初累计有原口径 PDF 依据，仍不授予历史 PIT 或系统使用资格。
- `integration-browser-final.log` 记录 1 PASS / 21.0s；用同一生产归档验证五期展示、金额、原响应/PDF、刷新和 390px 宽度。浏览器 collect 路由拦截计数为 0，未重新取得来源。失败、取消、重复、版本变更及损坏仍由既有 METHOD 回归证明，不冒称此次真实来源均逐一触发。

当前 `acceptance.md`、旧 `spec-review.md` 的“生产整链未运行”属历史状态，交付时应指向本回执替换该剩余项。完成范围仍是单股利润表观察链，不外推为历史 PIT、财务三表、正式模型输入或交易资格；封口预算继续保持关闭。
