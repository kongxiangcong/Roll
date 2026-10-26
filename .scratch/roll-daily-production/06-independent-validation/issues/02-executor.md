# 成熟结果、同窗基线、门级结论与离线重放

Type: task
Status: ready-for-agent
Execution: open
Acceptance: pending

## Requirements

复用 ForwardArchive 的实时归档预测与成熟结果，新增预测开始前不可变预登记与一次终点评估；拒绝 CAL 改名、事后登记、未知代码、历史污染和重复检验。按相同日期、资金、费用、执行政策生成 CASH/START_HOLD/MA5_MA20 对照；记录概率质量、成熟/未成熟/不可评分以及独立性限制。输出 PASS/FAIL/INCONCLUSIVE 的门级判断和总体结论，不能自动授予正式资格。样本不足或统计假设未验证必须 INCONCLUSIVE。冻结资源/阈值、审计家族既往曝光，支持幂等、重启、离线重放；不得读取 SEALED 来补足样本。

## 验收

实现经公共接口可达；相关边界测试通过；保留离线证据与运行限制；完成后在 Comments 记录测试与结果。

## Comments
