# 原冻结主模型中心绑定

工程检查下可保存独立中心绑定，不改旧检查。API：POST/GET `/api/research/successor-completion-checks/{id}/primary-center-binding`，GET/POST replay `/api/research/successor-primary-center-bindings/{id}`。

绑定 penalty=1、lookback_sessions=20 与同一冻结模型、输入、校准器及 CAL 校准前后原件。核对模型/协议/数据/代码哈希、惩罚目标和 DEVELOPMENT 标准化、特征定义，以及 DEV/CAL 每条快照的21个日期与原输入重算结果（20个收益区间）。只读校准前后预测身份，不调用拟合或预测，不读取 SEALED。

新记录保留旧检查和已知 FAIL；其余 penalty0.5/2、lookback15/25 四个槽位仍 NOT_SUPPLIED。中心身份不表示执行窗口预测对齐、邻域压力成功、独立验证或完整冻结；NOT_GRANTED，真实前向起点为空。方法与输入分别归档，8MiB/2000条快照上限；幂等冲突及嵌套原件损坏拒绝，重启可离线重放。
