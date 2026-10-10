# 双轴审查

范围：`1bf2260bc99f41916fdfdd772af8f64fbbf1be8e..7eae269a74d5fe87a62cda3b38ed28c99933be65`，及本轮待提交合同、取证笔记和字节保全属性。两名独立只读审查代理分别检查 Standards 与 Spec；没有访问实际运行分片或 SEALED。

## Standards

发现一项 P2：`training_preflight.py` 的 CAL 额度检查与 `registry.start_attempt()` 登记 PRIMARY_FIT 不在同一事务。竞争请求可在预检后耗尽 CAL，随后主拟合仍被登记，消耗主预算。要求将必要检查放到主拟合登记事务，保留 `models.py` 数值工件身份，并用应用入口复现竞争写入，断言不新增主尝试。

未发现其他增量规范问题。公开原件时钟、未知状态、METHOD 与实际研究边界均已说明；不因内部真实路径缺失而虚报验收通过。

## Spec

本轮切片未发现另一个可操作实现缺陷。仍未满足 ticket 19 前五项：真实源准入、预登记 DEV/CAL、非 METHOD 特征与标签、真实训练、独立校准和模型冻结。`REAL_TRAINING_PATH_NOT_IMPLEMENTED` 是真实限制，不能全部归因于外部资料。

43 个业务日最长连续序列 2 日，不满足 21 行固定特征上下文；捕获、业务日期和实际取得时间保持分开。权益端点始终 `coverage=INCOMPLETE, scorable=false`，不证明账户实际到账或完整公司行为。税制按登记日、自然月／年边界处理；出场当天到账的日级证据不推断 NEXT_OPEN 前已到账。旧 `models.py` 字节一致，预检仅读登记元数据。要求任务摘要以 43 日／连续 2 日替代旧 40 日／连续 1 日。

P2 在 `02a554d` 修复，经同一 Standards 审查代理只读复核确认解决且无新发现：在 `BEGIN IMMEDIATE` 内、PRIMARY INSERT 前检查家族 CAL；竞争 CAL 后拒绝不耗主额度。确定性应用测试覆盖交错，通用手工配置语义保留，`models.py` 字节不变。复核没有运行测试、查看实际运行数据或 SEALED。测试结果由实施／集成回执提供。本记录保留首次发现，不把修复后的结果冒充首次无问题审查。
