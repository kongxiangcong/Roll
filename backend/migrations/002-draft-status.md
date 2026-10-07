# SQLite user_version 2

Ledger 初始化在现存 version 1 上执行一个 BEGIN IMMEDIATE 事务：

```sql
ALTER TABLE account_drafts ADD COLUMN status TEXT NOT NULL DEFAULT 'READY';
ALTER TABLE account_drafts ADD COLUMN issues TEXT NOT NULL DEFAULT '[]';
PRAGMA user_version=2;
COMMIT;
```

01 已有草稿默认 READY，无丢弃/改写事件、回执或账户快照。空库先按 01 bootstrap 到 1，再升级 2。version 2 重启不重复 ALTER，不降低更高 schema 版本。执行语句位于实际调用的 Ledger 初始化中；不建通用迁移框架。版本化 JSON 账户字段随下一次已确认事件增长，旧快照字段缺失保持既有意义。
