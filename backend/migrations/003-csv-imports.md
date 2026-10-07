# 03 CSV草稿与文件身份

启动创建 `account_csv_imports(draft_id PRIMARY KEY, sha256, metadata)` 及sha256索引，仅保存本票实际文件/行/编码/修订元数据。正式账户继续用已有Ledger表和确认事务；不写全局user_version、不更改旧事件/回执。旧1/2迁移仍由Ledger负责。原附件在当前ROLL_DATA_DIR/raw/account-csv按内容身份保存，不另建权威账户投影。
