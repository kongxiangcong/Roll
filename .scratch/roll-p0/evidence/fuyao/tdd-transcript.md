# TDD接缝记录

此摘录来自本次工具输出，非原stdout逐字节副本；全部新测试只用已确认FastAPI/真实SQLite/raw。

- daily_source=FUYAO：422红；RAW/qfq、量额、档案与0联网回放绿。
- adjustment_source=FUYAO：422红；DATE公司行为/未知披露/不写账绿。
- quote_source=FUYAO：422红；逐证券时间null与UNKNOWN状态绿。
- 当前监控消费null交易日：COMPLETED期望而FAILED红；明确MONITORING_UNAVAILABLE、估值net_assets未知绿。
- 指数点位/总成交额：错误UNIT_AMOUNT_OHLC_MISMATCH红；INDEX_POINTS_NOT_SHARE_PRICE、背景不可个股模型绿。
- 实际视觉检查：待核观察除权日None而已知2026-06-26红；原始除权事项/DATE绿。
- 权限2003/限流4001/反射密钥/缺凭据/错对象固定响应回归；反射密钥在归档前拒绝，固定样本只记METHOD_CASE。
- 最终专项及旧市场合计24passed，先前相关66有2既有clock红，原root同2重现；不改变生产时点门禁。

早期pytest临时目录sandboxACL拒绝是环境，授权隔离目录执行后得到产品断言红。早期测试误读run.archives/账户account_version，纠正为公共snapshot.archives/账户schema；产品源码不为断言假设做兼容。
