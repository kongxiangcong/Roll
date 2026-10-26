# 05 增量：同截止概率证据绑定

05仍partial。新消费者将20/21的已保存概率/区块参照绑定到同一后继参数协议。前驱完整冻结ID/FP、模型各工件FP、概率报告ID/manifest与区块所引父ID/manifest/截止全部相符才保存；阈值固定继承0.60。不同报告即使模型相同也不得混用。

公开链读取同一193文件固定METHOD donor已保存CAL，实际scikit-learn1.9.1和arch8.0.0分别生成参照；绑定阶段只读归档、线性计数，无新数值库调用/拟合/bootstrap/SEALED。两阶段各20成熟唯一、完整40日历且20缺失或未知日历；选中数按各阶段真实概率计算。保留原数值状态、源区间、类别/分箱/选中/区块等冻结支持缺口；只消费SOURCE区间，不计METHOD解析例证。

CAL拟合窗口复用，独立校准/假设未证，G3 INCONCLUSIVE、完整冻结false、NOT_GRANTED。新表保存不可变关联，不改旧协议、模型、冻结、attempt、账户或预算。读/重放复用两父报告的原只读校验器，包括嵌套source/method，不重新评分。

验收：

- api-red.log：404，1 failed/19.05s。
- api-green.log：主绑定路径通过，末尾错误假定继承账户版本0，实际原donor版本1，失败保留；改为完整账户前后相同。
- api-final.log：1 PASS/22.75s，正向绑定、同模型不同父报告拒绝、幂等/查询、原协议/完整冻结/attempt/账户不变、无数值环境重启读取及重放。
- 审查P2：只验父manifest不能发现嵌套source损坏。integrity-red.log复现GET200vs预期409，1 failed/18.70s。复用概率/区块原读者后integrity-green.log：1 PASS/22.33s；逐项损坏本轮隔离副本内新生成概率source和区块source，GET/POST replay均409，finally恢复原字节。
- browser-green.log：错误断言选中成熟固定0，失败保留；测试改为来源支持显示，不虚构选中数。browser-final.log：Chrome1 PASS/28.5s，读取两个参照/关联保存/两阶段支持与缺口/G3未验证/原件校验/重载/390px。
- build.log：TypeScript/Vite通过；双轴审查P2修复复审后开放发现0。
- preservation.json：15份原现场文件无差异；model-preservation.json：12旧依赖无差异；旧四个冻结方法模块字节不改。

该切片实现保存CAL证据消费者，不能替代独立成熟前向标签/概率资格。05仍需真实输入、共同风险基准及其余G5组件/完整实验冻结。09有界生产整链计划已单独准备但等待用户答复，未执行或重开已封口预算。
