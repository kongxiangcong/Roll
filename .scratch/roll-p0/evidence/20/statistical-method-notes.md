# 20 可执行验证方法绑定

完整冻结保存 `statistics.py` 代码指纹及实际运行的固定算例结果，21消费相同版本；算法检查不会签发资格，也不会确认CAL拟合后的独立有效性。

日期块重采样保留同日证券组，固定20日块、40日敏感性、seed1701及2000次重复；不把同日证券或重复预测算为独立日期。缺失日期分数组返回不足，不压缩已声明的日期序列。`lower_95`和`upper_95`各是单侧95%端点，合起来为中心90%区间；主要门槛消费预登记的单侧下界。

方法来源为[Kunsch(1989)原论文](https://doi.org/10.1214/aos/1176347265)，书目信息见[作者出版目录](https://people.math.ethz.ch/~hkuensch/papers/)。真实序列的平稳性、弱依赖与有限样本覆盖不由恒定或合成算例证明；冻结记录保持`real_sampling_assumptions_verified=false`。

固定算例包括恒定0.005配对改善、跨0边界、40条成熟概率的Brier0.04和AUC1、重复事件不增加支持、净值100→90→110的收益0.10/最大回撤0.10以及缺估值保持null。预测损失和可靠性箱仅作描述，有效时间块显示上界；CAL自身指标不是独立确认。

在已批准的FastAPI/真实SQLite/隔离归档边界执行冻结及重查。红记录`statistics-red.txt`：1 failed，缺`statistical_methods`；绿记录`statistics-green.txt`另存，完整验收见本票acceptance.md。没有修改19指纹来源、读取真实SEALED或消耗既有真实拟合预算。
