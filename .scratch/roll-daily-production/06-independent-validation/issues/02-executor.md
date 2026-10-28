# 阶段 6 / 02-executor

Type: task
Status: ready-for-agent
Execution: resolved
Acceptance: core-verified; real-forward-evidence-pending

## Requirements

实现终点关闭门禁、原件绑定/预测/成熟结果/账本重放、同窗三基线与概率描述，生成门级及总体三态结论。新增界面入口、下载及离线重放。验收：空样本 INCONCLUSIVE、篡改 FAIL、未成熟不评分、单终点幂等、重启可读、版本变更拒绝冒充重放；原账户与模型不改。

详见 [spec](../spec.md)。依赖阶段 5 完成；02 依赖 01。

## Comments

已实现并验证。54 项联合回归和生产构建通过，见 [验收记录](../acceptance.md)。真实前向成熟证据不能由合成测试替代。
