# 阶段 6 验收

工程实现完成；阶段 5 提交 d0c6238 之后实施本阶段。真实独立验证结果尚未生成，没有增加正式资格。

## 已交付

- 元数据预检：家族 DEV/CAL/保护窗口排除、曝光事件与全尝试清单；三个自然月与 30 个有效块的不可能支持上限。无重新拟合/CAL预算消耗。
- 不可变预登记：完整冻结/执行器依赖/原期限/资源绑定；第一条预测前登记；命令幂等与事务竞态检查。
- 一次终点：只消费 CLOSED 前向原件；重新核算冻结模型预测、逐机会成熟盈亏标签与连续账本；同一资金/费用/规则/日期生成三基线，保留暴露差异，不宣称已风险匹配。
- 结果与输入持久化；篡改拒绝或 FAIL、空样本 INCONCLUSIVE、同终点重复请求不增加检验；新进程离线重放。
- 影子页面的盘后归档区域新增独立验证预检/预登记/最终结论/下载/重放入口。

## 实际验证

后端 54 passed / 0 failed，完整输出见 [backend-tests.txt](backend-tests.txt)。覆盖 independent_validation、forward、validation、shadow、shadow_record_close、shadow_security_cash、reconstructed_research、research_report_delivery、daily_reports、daily_report_updates。方法测试明确设置 ROLL_ENV=test，不伪造真实时间或真实独立性。

前端 `npm run build`（TypeScript + Vite + release manifest）通过，106 modules；有既存大 bundle 提示，不影响构建。没有执行浏览器交互或 Windows 目标主机验收。QuantStats 使用独立 Python 环境和 0.0.86，实际离线渲染、导出、持久化/重启测试通过。

## 操作顺序

1. 在持有完整原件的运行库创建关联后继协议/完整冻结，保留旧代码和旧结果。前向使用 revision=0 的新基线；阶段 5 已演化的历史冻结不能重置用于前向。
2. 影子页面登记盘后归档，再在第一条预测之前点击“预登记独立验证”。也可依次调用 `/api/research/complete-freezes/{id}/forward` 与 `/independent-validation/plan`；后者要求 `expected_complete_protocol_fingerprint` 和 `basis`。
3. 已有 worker 只在实际运行时归档当前预测；保留漏日，20交易日期限到达才评分。用户停止或原三自然月终点关闭后，POST `/independent-validation` 一次生成结果。
4. GET 同地址读取；POST `/independent-validation/replay` 离线核验原输入；GET `/independent-validation/admission` 查看元数据与可行性。

## 交付边界

目前没有具备独立统计支持、抽样假设证明、风险匹配和完整 G5 准入的真实包，因此本版本对当前协议只可能形成总体 FAIL 或 INCONCLUSIVE。部分算术/工程门 PASS 不构成统计 PASS。没有通过请求体输入概率/标签/已独立标志或放宽旧门槛的入口。完整确认性 PASS 需未来另立可行后继协议及证据适配，不能宣称本次已完成。

真实研究报告还缺阶段 5 验收记录列出的原模型输入归档；真实前向采样尚未在目标运行库开始。不得用此处 METHOD 结果替代真实报告或宣称投资优势。旧正式验证、真实账户与资金授权未改；模型技术审阅仍待真实材料，不自动启动收费审阅。
