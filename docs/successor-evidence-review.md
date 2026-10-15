# 同前缀保存证据汇总

在保存费用诊断下读取可绑定证据，显式选择时间分段、CASH、原登记基准、入场压力和CAL概率。执行类结果必须指向同一个费用记录、manifest/input和后继协议；CAL要求同后继与协议，但窗口单列，不与METHOD执行日历拼接。未选择的项为UNBOUND，不补成零或通过。

汇总显示已保存描述性结果、G1—G7状态、原目标和支持要求。保留全部已知硬风险失败，其余INCONCLUSIVE，不产生PASS或确认性查看额度。完整冻结的工程/输入缺口与启运后资格缺口分列：成熟G6/G7不是开始真实前向的循环前置。

本消费者不运行底层模拟器、拟合、获取行情或改变模型/原协议/账户。完整输入最多8MiB，保存源工件和方法/代码指纹，读取验证嵌套原件，显式重放只重算汇总。后续推进不改变旧记录。

API：`POST/GET /api/research/successor-cost-stresses/{id}/evidence-review`、`GET /api/research/successor-evidence-reviews/{id}`、`POST /api/research/successor-evidence-reviews/{id}/replay`。
