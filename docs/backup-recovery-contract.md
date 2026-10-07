# 本机备份、升级与恢复（16）

唯一生产启动入口仍为 `roll.app:create_app`。`ROLL_DATA_DIR` 指向运行目录；默认 Windows LocalAppData/Roll。备份在该目录的 backups 中，源码、SDK、模型 Temp 工作区与凭据不作为附件复制。

## 用户入口与恢复边界

- `POST /api/runtime/backups` 创建完整备份；`GET /api/runtime/backups`、`/status` 查看实际成功时间、数据库复制完成时点、账户版本、事件数与未覆盖变化。
- `GET /api/runtime/backups/{id}/export` 重新校验后下载 ZIP；完整原值用于恢复，页面只显示时点、版本、数量和脱敏错误代码。导出发现损坏后状态明确记录 CORRUPT，先前的成功时间不能代表当前包仍完整。
- `POST /api/runtime/restores` 上传 ZIP，完整校验后返回202/PENDING_RESTART。不会在线替换 SQLite。相同包重复请求保留原恢复请求，不同包在已有请求未处理时409/RESTORE_ALREADY_PENDING。
- 停止所有使用该目录的本机服务，再启动，才应用已选恢复点。其他宿主还活着时启动拒绝 RESTORE_PENDING_STOP_ALL_LOCAL_HOSTS。PID、实际创建时点、nonce 区分宿主；同时检查15 worker 和 RUNNING取证任务的实际 owner。
- 包压缩大小最多256MiB、展开合计最多1GiB；不允许重名、未知附加文件、路径穿越、目录外引用或 reparse 附件。大小限制是当前本机恢复入口的实际工程限制。

恢复以 SQLite 一致性复制的实际内容为界。数据库复制完成时点与最终包完成时点分列，账户事实自己的确认/实际时点不改变。停机没有新备份或新的分析覆盖，不承诺未运行期间的24小时恢复点；恢复不补造预测或追发旧机会。

## 完整原件与持久发布

ROLL-RECOVERY-1 含数据库 SHA、schema、事件数、原发布账户投影 SHA、持久事实 fingerprint、来源部署及备份写入者指纹、附件相对路径/SHA/字节数。

SQLite backup 固定一致性数据库版本；该副本决定所有附件引用，账户确认可继续执行。清单包括 evidence_archives 中原始响应/PDF/Parquet/研究分区及特征、模型、校准、forecast 工件；account_csv_imports 全部原 CSV；研究登记的原 browser-live.json、对应来源目录 raw/Parquet 文件，以及实际登记的工程暴露原件。代码/锁文件/实际 Python 与 SDK 版本只用于部署指纹，不被误当作 runtime 附件。

附件按原字节保留，不脱敏重写。复制后校验全部 SHA、数据库 integrity_check、附件引用、事件数、发布投影和既有账本 replay。旧不可变版本缺少后来新增的派生字段时，核对每个已保存字段，不补写旧版本。文件 flush/fsync，数据库连接全部关闭，完整目录原子发布后才进入成功列表；.building/.restore/损坏原文件留存目录不显示成成功备份。

自动后台只在程序实际运行时检查，30秒一次；有持久化变化时最多按一分钟合并检查间隔备份，新运行日亦检查。建议连续运行备份不超过24小时，有变化的重启立即补做。无变化不制造新备份；worker/session 心跳本身不算新增账户或证据，真实运行日审计与覆盖缺口仍属于持久事实。失败保存脱敏状态，不能替代成功备份。

## 恢复锁与当前资格

在任何附件/数据库替换、Ledger构造或后台任务启动前，先可靠保存 RECOVERY_LOCK。完整包不能包含 backups 内锁文件，旧包无法覆盖当前锁。旧已确认事件、回执、资金授权历史、研究材料保留；恢复的 QUEUED/RUNNING观察与未完成取证变为历史取消/中断，原标识和原因可查，不自动重启旧任务。

`GET /api/capabilities` 明确当前 RECOVERY_LOCK；正式端点返回403/RECOVERY_LOCK，观察、账户同步、普通数据查询继续可用。今天和设置显示实际恢复点、当前账户核对及正常离线覆盖缺口。旧资金确认记录不证明目前仍允许使用；后续遗漏的撤回为 UNVERIFIED，当前授权未核实，正式动作与旧通知为 false。

本票没有解除锁的公开开关。27尚未提供真实技术 ACTIVE、撤权与通知消费者；`permission_consumer_27=NOT_CONNECTED`。27必须以当前账户、部署、资金用途、可能遗漏撤回及有效自动验证/技术审阅材料建立当前资格，并在真实发布/出队/开卡/意向节点联验。现有资金 enabled→REVOKED→旧包案例证明历史不倒改且恢复保持关闭，不能宣称已完成27真实 ACTIVE 或通知联验。

## 迁移前备份与离线方法

create_app 的 bootstrap 在 Ledger（包括真实 v1→v2 ALTER）及所有模块构造写DDL之前执行。已有库的部署/依赖指纹变化、v1或所需实际表缺少时，先生成 PRE_UPGRADE 完整恢复包并保存 upgrade-pending。新空目录不造迁移前备份。其他活宿主存在时不允许升级替换。

全部构造成功才确认部署指纹并清除升级中标记；异常恢复迁移前数据库，保留 ROLLED_BACK 记录。进程在DDL前后死亡，下次启动先读升级中标记、校验并恢复原库，再重试构造。恢复原有数据库前也保存 PRE_RESTORE；原库损坏/漏件时保留数据库/WAL/SHM为未校验损坏材料，不冒称成功备份，仍可由已完整校验的包恢复。

数据库损坏导致 HTTP 无法启动时，先停止所有本机宿主，在 backend 目录使用当前锁定 Python（下面 DATA 是自己的运行目录，包路径是实际导出文件）：

```powershell
.venv/Scripts/python.exe -m roll.runtime.backups restore --data-dir DATA --bundle RECOVERY.zip
.venv/Scripts/python.exe -m roll.runtime.backups rollback-upgrade --data-dir DATA
```

两者都校验完整包并保持 RECOVERY_LOCK；rollback-upgrade 选择实际最近成功 PRE_UPGRADE。不要只复制数据库冒称完整恢复。恢复旧软件时使用对应可复现旧源及锁文件，当前软件自身不能证明任意未来 schema 的兼容性；当前接受真实1/2，其它版本拒绝。

Windows目录DACL仅当前用户与SYSTEM，子文件继承；非Windows目录0700。Windows扩展文件路径支持隔离研究源目录的深层原件。备份API仅本机地址访问，外部Origin拒绝；生产启动脚本仍绑定127.0.0.1，不在本票引入远程服务。模型认证/key文件和交易凭据不在恢复包或日志中。下载文件离开服务管理范围后，由用户保存在受限目录。

实际验收分列 API/SQLite/文件、原生进程和 Chrome；见 [16证据](../.scratch/roll-p0/evidence/16/acceptance.md)。
