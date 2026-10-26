# 已登记入场执行压力

保存费用诊断下可运行六个固定场景：四种原登记延迟按全成交，再加 NEXT_OPEN 的0%和50%成交。只改变 BUY/ADD 入场，早退 SELL、到期 CLOSE 和原迁移期限保留；未完成基准联合压力，不授G5通过。该消费者只处理 METHOD 保存帧，不读取行情、拟合模型或变更真实账本。

新版本引擎保留旧源文件，每个保存前缀先检查默认 NEXT_OPEN/全成交的完整返回状态与旧引擎和原工件完全相同。NEXT_CLOSE 入场在原到期退出后、收盘估值和政策观察前执行，持仓暴露用实际执行点价格。延迟一会话要求中间及目标连续声明，仅在观察+2精确位置尝试，不借用下一个可用行情。

部分数量向下取登记 buy_increment，再校验原 minimum/offset 规则；不足整手明确不成交。原预留持有到单次尝试，同证券待办入场不重复提交，之后释放全部剩余预留；原政策后续新 ADD 仍可能发生。实际成交新 lot 保留入场+20会话期限。没有成交不被标成预测亏损。

保留最多200声明位置，缺口为null，不压窗口。已观察回撤/暴露硬失败保留，其余G5 INCONCLUSIVE。归档源manifest/input、固定方法与新代码指纹；禁网子进程30秒及输入/输出8MiB上限，保存后可查询、刷新恢复和显式重放，后来帧不影响旧前缀。

API：`POST/GET /api/research/successor-cost-stresses/{id}/entry-stress`、`GET /api/research/successor-entry-stresses/{id}`、`POST /api/research/successor-entry-stresses/{id}/replay`。
