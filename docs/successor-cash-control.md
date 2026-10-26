# 同窗口 CASH 控制

在保存费用诊断的“同窗口CASH控制”中显式保存或查看。只允许空初始持仓：同一原现金、零利息/成交/费用/暴露，不假设把原持仓清仓。非空初始持仓拒绝，沿用其真实保存轨迹仍可在原报告阅读。

保留开始会话到末次声明会话的每个位置，最多200跨度。候选缺口保留None，完整区间收益未知时不输出候选减CASH的相对收益。CASH本身在空初始持仓约束下为常数净值与0收益。比较只描述风险差异，不冒充共同风险匹配；其他已登记基准和独立支持仍需补齐。

按原冻结风险边界保留已观察候选回撤/暴露的硬失败，否则G4 INCONCLUSIVE，不能PASS。已观察最大暴露并非缺失区段的完整最大暴露；未知不补值，也不抹掉已被观察证明的失败。

只读取原不可变费用诊断、帧和方法，不另算交易账本、不改变原政策/持有期限/模型/账户/预算/资格。保存源manifest/input、方法及原统计代码指纹；原件读取与显式重放均验证嵌套来源，后续帧不影响。

API：`POST/GET /api/research/successor-cost-stresses/{id}/cash-control`；`GET /api/research/successor-cash-controls/{id}`；`POST /api/research/successor-cash-controls/{id}/replay`。
