# 概率数值参照

保存研究报告中展开「概率计算独立库核验」，可运行、保存、查看和校验旧CAL归档的校准前后数值。scikit-learn1.9.1（BSD-3-Clause）在独立Python进程中仅调用Brier、log-loss和calibration_curve，不调用拟合、随机CV、新预测或验证，也不访问SEALED。配置 `ROLL_SKLEARN_PYTHON` 指向独立环境；依赖固定于 `backend/requirements-sklearn-reference.lock`。已验证Windows/Python3.13.12。

预登记方法见 `backend/src/roll/research/reference/probability-reference-v1.json`：绝对容差1e-12、无相对容差、自然对数、等权按逻辑事件去重、冲突拒绝。样本来自原模型before/after预测原件，逐执行输入hash匹配原标签，使用原CAL窗口及标签可知截止。模型、校准器、输入、校准前后预测指针都绑定原冻结manifest；窗口、事件、期限及证券范围也须一致。当前路径要求完整冻结已有保存的日历输入，不从行情行数压缩出交易日。

旧模型逐类别将概率下限设为1e-15，scikit-learn默认采用机器epsilon；参照分别保留对齐和默认结果。旧方法左闭分箱与库默认边界可能不同，上表按原分箱对齐，默认组另列。单类别仍有Brier/log-loss，未知/未成熟排除且留明细；缺失不是0。重复事件权重变化标记「口径不同」，明确数值偏差标记「实现差异」，不足与输入错误分别显示。

20秒进程上限、最多10000个CAL事件、8MiB结果；网络入口关闭。首次依赖冷启动超时已保留，正常缓存初始化后仍使用原上限，不调整容差。工件保存源样本、方法、原指纹和库源码版本；后续校验只读原工件，不使用当前库重新评分。

「数值一致」不说明样本独立、历史PIT、校准有效或策略获利。原CAL拟合窗口被复用，FITTED_UNVALIDATED、统计假设、G1—G7、原拟合预算和真实账户均不变。METHOD样本及真实库工程执行分别标注。
