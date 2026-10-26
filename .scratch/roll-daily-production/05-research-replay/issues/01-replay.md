# 现金事件证券隔离与手算回归

Type: task
Status: ready-for-agent
Execution: resolved
Acceptance: core-verified; real-profile-report-pending

## Requirements

修复跨证券现金分红污染订单和退出价格边界；现金事件必须属于确定证券。保存手算、多证券差分、原版本拒绝回放测试。新增可重复的研究交付入口，复用冻结模型、连续影子账户与 QuantStats，不重新拟合。只消费获准 CAL 资料，报告明确为描述性研究；保留所有旧工件与指纹。缺少真实归档或 QuantStats 运行环境时给出明确阻塞，不伪造真实验收。

## 验收

实现经公共接口可达；相关边界测试通过；保留离线证据与运行限制；完成后在 Comments 记录测试与结果。

## Comments

实现与测试见 [验收记录](../acceptance.md)。真实原件缺失，不能以 METHOD 验收冒充真实报告。
