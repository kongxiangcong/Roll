# 实施任务图

依据 [规格](spec.md) 执行 implement-spec。任务 01 和 02 可依据共同接口并行，03 在集成后完成验收。任务完成后在各票 Comments 记录关闭与测试证据。

- [01 冻结报告复查 API](issues/01-report-review-api.md)
- [02 工作台复查与判断记录](issues/02-workbench-review.md)
- [03 闭环验收](issues/03-acceptance.md)

共同接口为 GET /api/daily-reports/{report_id}/review，返回 report_id、day、revision、known_by、input_sha256、comparison（同类报告元数据或 null）、account（version、confirmed_at、cash_weight_pct、largest_weight_pct、constraints_status）、holdings。每项 holding 包含 instrument、weight_pct、status（REVIEW_REQUIRED / INSUFFICIENT / NO_NEW_REVIEW）、reasons（中文字符串数组）、changes（{kind, summary, references: string[]} 数组）、judgments（{note_id, thesis, invalidation, state, comparator, threshold, due_date} 数组）。百分比字段为数字或 null。GET 报告列表及原判断写入接口继续使用既有契约。报告列表供版本选择与可关联成交，客户端无需从列表重新推导复查结论。

实现补充：变化条目带覆盖状态。复查同时保留价格状态和日期触发，比较基准双方均有已确认账户时展示已退出持仓。判断写入新增可选 price_only，默认沿用既有的人工核对语义。资金摘要列出已核对的冻结暴露与账面现金保留约束，持续损失和其他交易约束仍须另行核验。

集成分支为 `codex/workbench-daily-review`。两个实现任务在共享工作树按文件分工，规格和编码标准分别独立审阅。浏览器验收使用本地 API、临时账户和 Chrome。
