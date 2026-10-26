# 同一后继轨迹的时间三段

保存费用诊断后，展开其“同一轨迹的时间三段”，保存或查看三个时间视图。只读取该不可变费用诊断的原轨迹和帧，不重新拟合、模拟交易或重置资金。

完整声明的METHOD会话跨度按floor(N×i/3)划分三段，缺失整数位置保留为未知；跨度超过200拒绝，不缩成已观测帧。每段包含其开始前的一个净值锚，并承接那个精确边界保存的现金、各lot和预留。边界缺失时现金/持仓未知，不采用上一条观察前向填充。

净值未知则完整分段收益/回撤不算。成交费用只计该段发生的原成交，输入缺口保留。原轨迹或分段内已观察到的硬回撤失败继续保留；其他情况INCONCLUSIVE，不授PASS。三个相关时间视图不是新增独立样本，不将分段收益拼成新实验成绩。METHOD会话不冒充实际交易日证据。

保存源manifest/input、方法、原统计方法指纹和结果。读取检查嵌套原件；显式重放只从原归档重新派生，后来帧不影响。旧模拟器、参数协议与原统计模块不改。

API：`POST/GET /api/research/successor-cost-stresses/{id}/time-segments`；`GET /api/research/successor-time-segments/{id}`；`POST /api/research/successor-time-segments/{id}/replay`。
