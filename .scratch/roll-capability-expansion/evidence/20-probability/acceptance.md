# 20 概率计算核验验收

## 交付

**Completion complete（工程数值参照）**。保存研究报告可运行scikit-learn1.9.1，对旧CAL校准前/后向量、同一成熟标签和截止核对Brier、基率Brier、自然对数损失与分箱。公开命令→保存→查询→研究页面→原工件重放均已通过；不是独立校准或真实研究资格，不改变FITTED_UNVALIDATED、假设状态或G1—G7。

归档原件逐项绑定原model-freeze manifest的模型、校准器、输入、before/after SHA；相同模型ID/指纹字典不允许替换预测指针。原CAL窗口、事件、20期限和证券范围也绑定。仅读取已经使用的DEVELOPMENT/CALIBRATION归档，不调用新fit、forecast、advance、validation或SEALED，旧模型与尝试列表原样。

## 预登记与依赖

method-before-evaluation.json在首次计算前写入，生产静态方法及其归档与之相同：绝对容差1e-12/相对0、逐类别1e-15下限、等权唯一事件、冲突拒绝、5组原左闭分箱。库默认机器epsilon及分箱边界另列，未将默认口径不同误判成实现错误。Brier显式binary scale_by_half=true，log_loss显式labels[0,1]，calibration_curve原组对齐n_bins1及默认5组分别调用。

独立scikit-learn1.9.1 / BSD-3-Clause / Windows Python3.13.12；7依赖锁定见requirements.lock。Windows cp313 wheel SHA 2070f271e5375dc42c6bb93b461ab1c0aa5841d4009267e0cfd95a39dca94a43；实际分类/calibration源码SHA、许可见source-manifest.json、SKLEARN-LICENSE.txt。业务、模型、QuantStats环境均未改变。进程-I -B、20秒/10000事件/结果8MiB、socket网络入口拒绝。

## 证据

- api-red.log：公开命令404。
- api-green.log：初次依赖冷启动超时20秒，原失败保留；runtime-smoke.json：正常独立导入约12.1秒并初始化字节码缓存，无数据、评分或网络。
- api-green02.log：1 PASS/15.09s，真实独立库读取193文件METHOD副本，校准前后各20个成熟唯一事件数值一致，旧模型及尝试列表不变，幂等/保存/重启无库重放。
- edges.log：1 PASS/2.94s，固定METHOD向量覆盖0/1、精确分箱边界、单类别、未知与未成熟、同事件重复/冲突、不同日期、无效概率及人为偏差；口径不同、实现差异、不足和输入错误均分开。无新拟合或网络。
- binding-red.log：故障注入将after原件指针换成before时原路径错误201；修复后binding-green.log：1 PASS/15.18s，409拒绝，恢复模型后重启原工件仍可重放。只在隔离副本注入，未改原profile。
- browser-red.log：缺少报告内核验入口。browser-green.log：Chrome1 PASS/23.7s，校准前/后数值表、原工件校验、保存版本重载及390px无横向溢出。
- build.log：TypeScript/Vite PASS。standards-review.md/spec-review.md：源绑定P2已解决并定向复审，开放发现0；评审未额外联网/运行测试。

所有正向源来自固定193文件METHOD副本，真实库执行不代表真实数据独立有效。源cutoff=2026-10-10T17:16:39.073414+00:00，复用当时CAL标签；不把今天核验倒写为当时模型可用性。图文明确FIT_IN_SAMPLE与NOT_GRANTED。

preservation.json：15原现场保护文件无差异（剔除本feature插入）；model-preservation.json：12旧模型依赖相对fe5d01c7未变。app.py专用暂存补丁不包含原SSE改动。
