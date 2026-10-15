# 05 入场阈值邻域验收

基线63200a2。结果前保存method-before-derivation.json，entry-only三档，support固定。未改registry.py/research_attempts或旧冻结模型源码；独立METHOD事件partition=null、data_scope=METHOD_DECLARED_SLOTS，与真实训练分区严格分开。

公开API红灯404失败1项/20.08s；首绿1 PASS/28.06s，增加风险/源完整性后1 PASS/34.16s。审查发现两个P2：START后mkdir在保护外、两个恢复者关闭同一行可能启动报错。全部postSTART准备/worker/success finish移入try；恢复在写事务内幂等处理已终态。最终 **1 PASS/33.38s**（api-final02.log）。

正向证明：0.60完整状态等原前缀；0.55实际2买入、5卖出（support仍0.60），0.65无入场；三档全报无赢家。原影子/账户/拟合家族清单不变，显式重放不新增METHOD尝试。漏9、10未知、11已观察暴露硬FAIL时，完整收益未知但G5 FAIL不丢；嵌套input损坏GET409并还原。

生命周期回归：仅在隔离profile内改名自己的输出目录，并建立同名文件造成真实目录冲突，三档均FAILED留证，重复key返回同一记录无新尝试，finally恢复原目录。另用明确的持久START/死owner夹具及Barrier同步两个实际服务初始化器，二者均完成且只三条INTERRUPTED终态。该项是数据库/初始化并发METHOD恢复证据，不冒充真实进程kill实验。家族共12 METHOD，含3FAILED/3INTERRUPTED；原训练清单仍不变。未知协议查询404。

修复后Chrome **1 PASS/63.94s**（体42.8s，browser-final.log/browser-results.json）：运行三档、原训练/METHOD清单分列、保存重放、刷新恢复及390px无溢出截图mobile.png。隔离profile `.scratch/r05nb2`、8164/5264，未启动主服务；TypeScript/Vite构建通过。双审查P2均已关闭，见对应报告。15原脏文件0差异、12旧模型依赖不变，见preservation.json/model-preservation.json。

只证明固定METHOD阈值敏感性及审计工程；无新预测、拟合、SEALED或行情请求。Penalty/lookback需原冻结邻域工件，真实输入、独立支持和完整冻结仍缺；NOT_GRANTED，真实前向未启动，05保持partial。下一离线前沿为迁移lot/scope审计和版本化工程完成检查。
