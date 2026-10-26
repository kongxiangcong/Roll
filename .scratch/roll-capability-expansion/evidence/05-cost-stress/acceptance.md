# 05 增量：保存前缀费用压力消费者

05仍partial。本切片落实已冻结三档commission_scenario_rate及三档slippage_each_side_rate，逐项改变，未让用户输入新网格/找赢家。使用原successor_shadow.simulate，在同一保存METHOD帧、政策、现金/持仓迁移与各lot期限下运行六个场景；基准逐帧等于原保存结果。保存成交/费用/净值/缺口、原冻结与代码依赖、输入/结果指纹；费用率变化产生实际费用差异。

原successor_protocol.py、successor_shadow.py、policy_successors.py、statistics.py和旧模型依赖字节不改，兼容旧工件。新增诊断不覆盖参数冻结或旧验证结果。所有前缀验证/场景模拟在可终止子进程内，200帧/30秒/输入及输出各8MiB、网络0。只查询目标revision及之前，不读取后来帧。输入/方法先归档，结果不可变/幂等；显式重放使用原归档、同一方法及继承代码，不改原帧。

不能PASS。按原冻结回撤边界保留METHOD硬FAIL，否则G5 INCONCLUSIVE；未知NAV不提供完整期收益/回撤。已观察净值能证明的回撤下界与完整期指标分列，后来未知不抹掉先前失败。实际费用/独立资格/真实输入均未授予。

方法：method-before-evaluation.json保留首次正向算例前的原文；method-risk-handling.json记录“已知硬FAIL/否则INCONCLUSIVE/无PASS”的语义澄清及输入上限。风险阈值一直取原已冻结design.primary_objective.risk_constraints，未引入或按结果调整统计/风险阈值。

验收：

- api-red.log：404，1 failed/17.26s。
- api-green.log：1 PASS/24.08s，原模拟器实际运行六场景、原前缀一致、幂等/保存/重启/重放/账户及attempt不变。
- api-adverse.log：1 PASS/26.38s，费用差异及原风险硬FAIL。
- api-final.log：1 PASS/30.16s，继承代码绑定、未知NAV不补值、既有硬FAIL保留、后续帧损坏不影响旧前缀重放。
- api-final02.log：最终API通过，含201帧超限拒绝、8MiB输入上限下正向路径。
- browser-final.log：Chrome1 PASS/29.3s，页面六场景/费用及百分比/保存版本/重放/重载/390px；mobile.png。
- build.log：TypeScript/Vite通过。双轴审查开放发现0；P3方法文案已修正并复核。
- preservation.json：15份原现场文件无差异；model-preservation.json：12旧依赖无差异。四个旧冻结模块git diff为空。

剩余：真实v2输入准入、独立成熟概率、共同窗口风险匹配基准、时间分段、执行延迟、冻结邻域及迁移支持；不能将本费用消费者称为完整G5或完整实验冻结。不拟合、不读SEALED、不增加确认性查看、不变更实际账户、资金、资格或前向起点。
