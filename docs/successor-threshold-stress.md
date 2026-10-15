# 入场阈值邻域与METHOD审计

同一保存费用前缀上，固定报告0.55、0.60、0.65三档入场阈值。支持阈值、期限、反向冷却、数量、费用及原概率均保持不变；默认0.60逐前缀完整状态必须与原保存状态一致。私有诊断执行契约不带旧冻结身份或指纹，不修改原政策/模型，不拟合或选择赢家。

METHOD整数会话不属于DEVELOPMENT/CALIBRATION/SEALED训练分区。每档在worker前原子登记独立METHOD THRESHOLD START事件，完成/失败/取消及死宿主恢复均追加终态。家族及兄弟METHOD清单与原训练attempt_manifest分列，partition=null；原拟合、校准、SEALED与确认性查看额度不变。相同key不重复登记失败或运行中的尝试。

漏会话/未知全区间保留null，已观察回撤/暴露硬FAIL保留，其余G5 INCONCLUSIVE，无PASS。最多200帧/声明跨度、禁网worker30秒、输入输出8MiB。保存方法、源manifest/input及代码指纹；显式重放不新增METHOD尝试。目录准备失败进入FAILED，两个恢复者不会重复终结或使启动失败。

API：`POST/GET /api/research/successor-cost-stresses/{id}/threshold-stress`、`GET /api/research/successor-threshold-stresses/{id}`、`POST /api/research/successor-threshold-stresses/{id}/replay`；实时家族METHOD清单 `GET /api/research/protocols/{id}/successor-method-attempts`。保存结果含原训练与METHOD两个快照清单，后续尝试不改历史快照。
