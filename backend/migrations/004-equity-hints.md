# 04 组件初始表：待核权益材料

Ledger启动执行 `CREATE TABLE IF NOT EXISTS account_equity_hints(id TEXT PRIMARY KEY, material TEXT NOT NULL)`。这是04组件初始幂等建表，不是全局schema version4；全局user_version保持02的2。已有cash/position/history/receipt/draft表及数据不变；04已确认现金/权益事实仍存于原账户事件/不可变快照，不新建账户权威。

材料仅含来源、原宣告内容及时间、系统获知时间、未知实际发生时间与待核状态。新增/查询材料不写account_versions；正式事实仍只能由用户草稿/确认单事务入账。旧schema升级及重复启动回归包含在完整真实SQLite/进程套件中。
