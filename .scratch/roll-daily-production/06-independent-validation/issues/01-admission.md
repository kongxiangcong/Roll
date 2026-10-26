# 阶段 6 / 01-admission

Type: task
Status: ready-for-agent
Execution: resolved
Acceptance: core-verified; real-forward-evidence-pending

## Requirements

实现独立验证元数据预检、期限/有效块上限、家族尝试与曝光审计、不可变预登记及竞态检查。验收：拒绝错误冻结指纹、事后登记、客户端独立性字段、METHOD 在生产环境使用；预检不读取价格或标签原件；保留旧预算。

详见 [spec](../spec.md)。依赖阶段 5 完成；02 依赖 01。

## Comments

已实现并验证。54 项联合回归和生产构建通过，见 [验收记录](../acceptance.md)。真实前向成熟证据不能由合成测试替代。
