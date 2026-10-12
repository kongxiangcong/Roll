# Ticket 21 独立合并验收（2026-10-11）

结论：既定工程范围独立验收PASS，METHOD及真实一致副本两个公共API进程均正常退出0。当前真实研究诊断FAIL/INCONCLUSIVE与工程通过分开记录。

实现提交 `aef9b27bd32bb9983fcce77ab642a17c2dfcf3e0` 基于当前集成 `9b53aefd3bdba4e6f9779010cd32d2f4c1b47083`，经授权本地 no-ff 合入 `4f24dac6c18071309107a8a03b968395de44a710`。没有推送；既有未跟踪目录与历史失败、预算及暴露记录保留。

## 工程验收

最终实现者 API 3项通过（47.80秒）、实际 Chrome 1项通过（53.1秒）、TypeScript/Vite 57模块构建通过。最终截图已独立检查：G5长原因在表格内换行，七门槛、初步结论、待审阅与未授予状态清楚可读。来源见[21验收](../21/acceptance.md)及其原日志。20默认连续行为沿用同一模拟函数；21增加冻结执行场景参数，未指定时仍为 NEXT_OPEN/全额成交。早期专项记录及整仓460项基线各按自身时点保留，不跨运行加总或冒称本次整仓复测。

另一全新运行目录通过[独立公开API脚本](independent21.py)与[结构化结果](independent21-results.json)：

- 两个原始记录对应一个逻辑机会，一次BUY、一次重叠REFUSE；入选1、覆盖1，不因后一个拒绝覆盖前一个BUY。默认连续轨迹一买一卖，三时间段的平仓总数为1。
- 空机会、零收益为 INCONCLUSIVE；独立5000元基线出现已观察资金不足全拒绝，G4与总结果FAIL，原因 `MINIMUM_DECISION_COVERAGE_NOT_MET`。G7仍INCONCLUSIVE，硬失败没有被其他不足平均抵消。
- G2整体INCONCLUSIVE；冻结连续轨迹重放子检查PASS，完整部署证据不足单列。G5延迟分项保存输入、方法及结果指纹，监测固定输入方法检查通过。
- 三份不可变清单在真实SQLite重启后读取相同、重放一致、联网0。单独损坏自己的METHOD清单归档或输入归档，公开入口均返回409 `ARCHIVE_MISSING_OR_CORRUPT`；恢复原字节后原结果仍一致。
- CONFIRMATORY在SEALED内容消费前409；没有增加诊断结果或确认性PASS点。账户版本0、无前向起点；实验 `RUNNING_DIAGNOSTIC`、审阅 `PENDING_TECHNICAL_REVIEW`、能力 `NOT_GRANTED` 分开保存。

此前独立发现的重复机会覆盖和分段事件缺陷已由原实现者修正；公开红记录见21目录的coverage-red/segment-red。分段保留连续资金轨迹，事件仅属本段，累计已实现收益扣除段前基准。最终独立案例再核实修正行为。

## 当前真实一致副本

只消费根已授权一致副本 `.roll-data/implementation-evidence/21/actual-current-copy`；不启动原19、不读取实际SEALED，不增加拟合、预测、推进或诊断。通过[独立读取/重放脚本](independent21-actual-copy.py)核对既有最终清单 `baf981b6-b2bf-4f6f-b46f-1726f261de8e` 与实现者归档结果，读取旧方法清单并验证旧重放409 `VALIDATION_CODE_CHANGED_SUCCESSOR_REQUIRED`，最终清单重放一致、联网0。独立完成收据见[结构化结果](independent21-actual-copy-results.json)。

当前真实量价重建候选的诊断为FAIL（G4/G5），G1/G2/G3/G6/G7为INCONCLUSIVE；用途仍为 REAL_ACQUISITION / RECONSTRUCTED_RESEARCH，模型 FITTED_UNVALIDATED。这是当前历史CAL诊断，不是实际独立确认或真实前向证明。确认性入口的拒绝属于本票工程交付；真实协议统计结项、技术审阅、G6/G7及生产资格没有完成。缺失冻结参数邻域工件和独立统计条件逐项保留，禁止用工程测试结果补成PASS。

## 保全与来源边界

最终浏览器METHOD运行件由实现者停止后保存到根 `.roll-data/implementation-evidence/21/browser-final-method`，独立复核源和目标315文件/17,887,006字节全部SHA及长度相同，见[保全清单](../21/browser-runtime-preservation.json)。新的独立METHOD目录209文件另存[清单](independent21-profile-manifest.json)；实际一致副本留在根。最终源码与[source-after-final](../21/source-after-final.json)相符。

12个19模型指纹依赖源码SHA与长度保持相同，见[原基准](upstream19-before20.json)与[21之后](upstream19-after21.json)。新影子场景代码绑定新的完整冻结，旧20冻结及工件作为历史保留，不能跨源码版本重放或冒充新方法证据。历史失败浏览器日志两行保留原始尾空格；Windows CR-at-EOL以外的生产差异无空白问题。

21完成限于验证引擎、证据清单与当前缺口交付。当前01—22共22票工程完成，23依赖解除，按用户顺序继续23。30依赖20已解除但不跳过已确定顺序。真实G1—G7、自然月前向终点及正式能力仍按后续责任推进；当前19工程完成以eabc/19重建验收为准，旧历史partial记录不改写。
