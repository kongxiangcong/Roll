# Ticket31 托管工作树归档

31 partial source已合入6c0f2d5，独立收据7390cce。原路径 `C:\Users\72449\.codex\worktrees\ticket31-delivery\Roll` 在调用归档前只读核对无自身运行宿主；首次查询命中的是核对PowerShell自身，排除本次PID后无匹配，不终止其他进程。

Codex `archive_worktree` 首次返回queued，随后 `list_artifacts` 确认同一identityKey成为archived_worktree，attachment `01a12941-672f-7cc2-9408-a02a72284275`。可恢复Git快照由工具保存；没有手工删除目录或分支。此安装使用独立物理venv/npm目录，没有指向根依赖的junction。

必要忽略运行件在归档前保全且独立双侧复核：旧4057件与组合237件共4294件。归档后再用逐字节读取复核目标清单，4294件SHA256/长度零差异，两份原清单未修改。源码工作树确认不再存在；本次为DESTINATION_ONLY_AFTER_MANAGED_ARCHIVE，不声称归档后仍能源/目标对比。见[ticket31-archive-postflight.json](ticket31-archive-postflight.json)和[核对脚本](verify31-archive.py)。

15保护源码零差异。原19数据库只作checksum，165814272 bytes、SHA `ec46257c4420f69c245791778c49079355700615cc3ed7b94d8027bd4dcf66c4`。没有连接任何保存SQLite，没有provider/拟合/SEALED/外发、资金或正式资格操作。31仍partial，后续跨票验收继续由责任票推进。
