# 16：本机备份与恢复验收

2026-10-08（上海）。本轮实际开始05:29:01（2026-10-07T21:29:01Z），最后Chrome重启记录06:07，原生文件保全完成06:07:06，最终构建/清单记录06:11。源从c6cd196开始，先提交1b79c66、b33ea90，实际合入14/19及父记录7260c8c，合并点53dfd81；本文件随本票最终提交保存。不修改父执行状态，不推送。

16本票范围 COMPLETE。AT-45完整备份/一致恢复/升级前回滚、AT-86实际运行日变化/离线无新覆盖/重启补做/观察可用已验。27真实技术ACTIVE、可能遗漏撤权、旧通知出队与当前资格解除锁联验仍 PARTIAL / NOT_CONNECTED；没有开放解除锁开关。资金CONFIRMED不等同技术ACTIVE，不用原本总403的端点独自证明恢复锁。

## 输入、预期与实际

| 公开输入或原生故障 | 预期 | 实际证据 |
| --- | --- | --- |
| 确认账户/原事件、07 METHOD raw/Parquet、原CSV（包括待核原稿）→备份→导出→停止→恢复 | 原字节SHA、版本、事件、发布投影一致；重放零联网；观察可用 | API通过，每附件SHA一致；原CSV内容未脱敏破坏；tasks/auth.json合成陷阱未导出 |
| 缺附件/改附件/仅DB/改事件数；修复SHA后篡改账户投影 | 409不排队、不改活账户；event replay独立拒绝篡改 | 四种坏包及ACCOUNT_EVENT_REPLAY_MISMATCH通过 |
| 原附件丢失、新备份失败、已有包后损坏 | 不记录新成功；此前完整副本独立导出；坏包拒绝并明确CORRUPT | 最近成功与当前损坏状态分列，API通过 |
| 同时CASH_IN20元确认与SQLite backup；同包/不同包重传 | 完整恢复点为版本1或2；同包幂等，异包409，现金/事件不重计 | 合法凭证补全后1passed，现金100000.10或100020.10及事件数匹配 |
| 25小时可控时钟无变化→新材料→停止→重启 | 无变化不造包，有变化覆盖，重启补做，停机无承诺 | 真SQLite/后台生命周期通过，RESTART_CATCHUP、offline_backup_promised=false；时钟METHOD，非实际等25小时 |
| 资金enabled/CONFIRMED→备份→REVOKED→恢复旧包 | 原历史保留；当前可能遗漏撤回未知，RECOVERY_LOCK，旧通知/正式动作关闭 | public capability/恢复状态/旧资金版本/今天一致，27 NOT_CONNECTED |
| 外部client/Origin；Windows真实ACL | API拒绝外部，仅本机用户/SYSTEM | 403与真实Win32 protected DACL通过，pywin32==312锁定 |
| 19 METHOD feature/model/calibrator/forecast及登记原source目录 | 原archive/raw/Parquet/engineering exposure全保留，恢复后真实导入/重放可用 | 联验通过，forecast replay network_calls=0，METHOD_ARTIFACT_ONLY/NOT_GRANTED不变 |
| 14 frozen request实际消费 +15网络worker关闭/peer | 原核验关联不丢，真实线程停后释放lease | 两个现有公共调用方定向通过，未重跑SDK或全225 |
| 17ca07d实际旧服务写schema1/回执/待确认权限；DDL前/后死亡87、迁移异常1 | PRE_UPGRADE在所有新DDL之前，schema1；真实旧服务读包原样；新服务先回滚再幂等确认 | 三个OS通过，ROLLED_BACK，旧account/events/receipt/draft一致；schema1公开ledger replay验证且不构造迁移 |
| MANUAL包发布前死亡88 | staging不冒称成功，重启原回执不重复 | 实际OS通过 |
| 两个真实宿主共用目录，恢复排队 | 不在线覆库，任一host活着均拒绝新启动，全停后应用 | 两次RESTORE_PENDING_STOP_ALL_LOCAL_HOSTS、peer事实未变；后续锁通过 |
| 物理损坏SQLite主文件，停止后CLI restore | 不先构造Ledger；保留坏DB/WAL未校验材料；完整包恢复原账户/回执且上锁 | 真CLI进程通过，RESTORED_RECOVERY_LOCK；坏原件不冒称成功包 |
| 已确认CSV CASH_IN10元；恢复after_lock/after_attachments/after_database死亡89 | 锁可靠保留，同恢复点，原CSV/回执/事件/现金不重计 | 三个OS通过，重传confirm返回原receipt，原CSV字节一致 |
| Chrome设置创建/下载/坏上传/合法上传→停止→同目录新服务 | 损坏明确，待重启时活账户不改；重启今天/设置锁、版本1/10000.10 | 两次真实Chrome分别通过，截图核对五入口、复制完成时点及观察/核对提示 |

早期19真实本机再导入揭露原source目录raw/Parquet漏件，补齐实际登记原件后通过。实际Windows长路径和SQLite连接未关闭导致的rename错误已具体修复。金额/市场材料均为合成METHOD，不能当真实交易、来源独立性或预测资格。

## 最终证据分层

- [api-first-final.txt](api-first-final.txt)：13passed/1failed，66.05s。并发CASH_IN夹具漏必需凭证字段，产品正确422；补合法输入后只重跑该case，[concurrency-final.txt](concurrency-final.txt) 1passed/6.43s。合计14个不同公共API场景通过（本票12、14/15交点2），没有宣称单次14全绿。
- [process-first-final.txt](process-first-final.txt)：6passed/3failed，三个CSV夹具漏basis，产品正确隔离；补原凭证后 [process-final.txt](process-final.txt) **9passed/91.66s**。未弱化确认约束。
- Chrome创建 [文本](browser-create-final.txt)/[JSON](browser-create-final.json) **1passed/11.2s**；同目录新服务重启 [文本](browser-restore-final.txt)/[JSON](browser-restore-final.json) **1passed/9.6s**。测试主体完成后仅加独立phase选择，默认集合不执行未准备恢复点的案例；未修复或冒称既有05默认共享夹具已绿。
- [build-source-final.txt](build-source-final.txt)：最后UI复制完成时点字段及14/19合并后tsc/Vite通过，52modules/1.93s；此前构建 [build-final.txt](build-final.txt) 原日志另保留。
- 实际截图：[创建设置](browser-settings.png)、[恢复后今天](browser-restored-today.png)、[恢复后设置](browser-restored-settings.png)。人工查看设置图无溢出，最近成功/复制完成/恢复锁分列。

## 复现入口

backend实际锁定venv：

```powershell
.venv/Scripts/python.exe -m pytest -q tests/application/test_backups.py tests/application/test_independent_verification.py::test_frozen_review_request_consumes_once_and_links_original_audit_without_routine_upgrade tests/application/test_reviews.py::test_shutdown_keeps_lease_until_actual_network_worker_stops_before_peer_takes_over
.venv/Scripts/python.exe -m pytest -q tests/recovery/test_backup_process.py
```

Chrome必须先全新隔离目录，两个独立服务生命周期使用同一目录；第一次结束后不删目录、不另造基线。frontend：

```powershell
$env:ROLL_TEST_API_PORT='8036'
$env:ROLL_TEST_WEB_PORT='5196'
$env:ROLL_BROWSER_CHANNEL='chrome'
$env:ROLL_TEST_DATA_DIR='D:/your-isolated-runtime/backup-acceptance'
$env:ROLL_BACKUP_BROWSER_PHASE='create'
npx playwright test tests/e2e/backups.spec.ts
$env:ROLL_BACKUP_BROWSER_PHASE='restore'
npx playwright test tests/e2e/backups-restored.spec.ts
```

env仅选择两阶段验收，不弱化空账户确认、不替换app。恢复/CLI/访问边界见 [实际契约](../../../../docs/backup-recovery-contract.md)。

## 原件保全与停止边界

最终9个OS临时原件已只读复制到本树ignored目录，未删临时源。首次传统Windows路径限失败后只补缺失文件，已有字节必须相等。[native-file-preservation.json](native-file-preservation.json)：294件/23,666,039字节，SHA差异0，逐文件原源/目标映射。

全部验收服务/浏览器进程已结束；未移动/清理源。父永久保全入口 [runtime-retention.json](runtime-retention.json)：348件/29,840,615字节，每件SHA：

| 本树backend/.roll-data目录 | 件数/字节 | 范围 |
| --- | --- | --- |
| acceptance-16-browser | 27 / 3,013,347 | 较早真实Chrome，optional；prototype未有字段仍unknown |
| acceptance-16-browser-final | 27 / 3,161,229 | 最终真实Chrome两阶段，required |
| acceptance-16-process-files | 294 / 23,666,039 | 最终9原生进程/文件，required |

old-source/roll Python是迁移可复现源；源码/SDK只有部署指纹，不冒称runtime附件。未复制模型Temp认证/key。父永久复制并逐SHA校对前保留这三个源；本票不执行清理。[清单脚本](retention_inventory.py) 只盘点这些明确目录、不改原件。

## 最后22实际集成

结项源f109842后，按协调要求合入根真实22 tip c127930。唯一冲突为.gitattributes尾部证据声明，完整保留16与22两组原字节规则；app/risk-policy路由、页面、追踪表自动合并。未重复14API/9OS/Chrome/SDK套件。必要轻量 [merge22-build.txt](merge22-build.txt) tsc/Vite通过53modules/2.00s；[merge22-routes.txt](merge22-routes.txt) 真FastAPI/新SQLite构造、完整backup/export、恢复202排队、停止/重启后pending清除、RECOVERY_LOCK、formal拒绝与22观察read资源404均通过。此404明确证明读路由仍可达，不冒称该空账户已有22政策材料或验证过其实体恢复。348件已停止的原证据目录未改变；临时合并smoke目录生命周期结束后自动清理，不属该保全清单。
