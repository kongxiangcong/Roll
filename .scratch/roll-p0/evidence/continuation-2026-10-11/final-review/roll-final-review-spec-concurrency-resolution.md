# Spec 并发残差复查

仅核对 `bbb84a57f624dec9351b32373fd9d10e1447eed3...4a975c629379cba4cbee34178bf5d2ac4452d87c` 的 prepare 最小并发 hunk。原报告及 bbb84a57 的 held 记录保留，不覆盖。

**结论：原 prepare 幂等并发残差静态 closed；无新增可操作残差。**

spec:349 要求“同幂等键同内容返回原业务结果”，26 AC:17 要求“幂等重试返回原结果”。`intents.py:78–81`现在先显式 `BEGIN`，`prepare_receipt`的:65回执查询与:69 legacy查询处于同一读事务。另一 caller 在两次查询间提交的新意向与回执，不会被第二查询单独看见，原误报 `LEGACY_PREPARE_RECEIPT_UNAVAILABLE` 的时序已消除。未找到回执时显式 rollback，释放读快照，再刷新宿主当前状态。

`intents.py:85–88`仍在 `BEGIN IMMEDIATE` writer事务内再次查询，覆盖初次读快照结束后同键提交的情形，随后才执行新请求的当前资格与动作检查。不同内容继续409，真正 legacy 无原回执继续明确不可用；已有不可变回执不重新创建或恢复执行资格，不覆盖当前 pending/partial 意向事实。

初次查到回执的 return、内容冲突或 legacy异常均离开 `Ledger.connection` 的 contextmanager，`finally: db.close()`结束连接及未提交的只读事务。writer返回前显式 commit；异常同样关闭连接。没有遗留读事务跨入权限刷新或新 writer步骤。

局限：本结论仅为固定源码的静态合同复核，未执行 SQL、测试、HTTP 或 Provider；owner 红绿记录不作为本次独立运行验收。未重审其他三项或全 diff。第5政策与生产 producer要求仍partial，实际资格和 actual ReviewRecord 均未升级。
