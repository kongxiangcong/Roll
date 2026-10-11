# Ticket31 最终独立合并验收

2026-10-11；只接受本轮有限工程交付证据，不将全部239项、研究资格或整个规格升级为PASS。31 Completion保持partial，政策／来源先决缺口仍归20/25，真实前向与32—34、G7及用户配置后外发分别保留。

root before `6bbc3f94c05fd62e0afb9d0c4be2f1f502fffbf2`，稳定owner `792389c8c3e6d211199e6d73ed45b5940cb6ece7`，行为版本 `d4864a4e29ddcb80462e44250569d652e8cc03cf`，own docs merge `6cad5e121d8de4b34847195a4ef2a52d5902d0c9`。确认含accepted `076e67d53e4e550d4027b4f76909fb693c952957`。root no-ff为 `543fb66697b9c189d7017c0554a91a291893709d`。107个实际Git差异路径只含31证据／脚本／截图、一个调用方test_reviews通知契约更新及专用报告Playwright配置；没有backend/src或frontend/src产品改动。197个产品源raw Git tree/blob在root/owner一致，75个数值应用源与实际数值运行摘要一致。

## 独立结果与证据界限

| 项目 | 核对结果 |
| --- | --- |
| 安装／build | own物理venv/node_modules均非reparse；4个锁／manifest原字节与清洁安装记录一致，Python3.13.12/SQLite3.50.4/Node25.8.1/npm11.11.0，Roll导入own源码、system-site-packages=false；uv/npm/build exit0历史安装记录与当前66module/2.22s build日志分别保留；未重装或audit fix，npm1low/1high诊断不推断可利用性 |
| 组件／Agent | 固定CNE410源/382installed公开包记录、Apache2 NOTICE/TDX MIT及DSA design-only MIT分别保留；仅核验已注册公开记录绑定。七个Agent源当前摘要已核，其中五个未变，saved-material枚举和资格展示变化已读；只读3项取证工具/2项审阅工具未扩权，资格展示只投射既有宿主结果，不签新grant；历史11/23真实调用不冒称本轮实际调用，DS按当前范围排除 |
| 五入口 | 最终真实Chrome记录6个checks、0pageerrors/HTTP500：初始30持仓未知可卖与5背景指数、实际300无建议成交/未知费用暂估后补5元、25.01 CSV整批回执、无未记录变化声明、持仓/历史及按原因暂停恢复。未把拟议500或实际账户GRANTED虚构为本轮事实 |
| 隔离报告 | 最终单case1PASS4.9s（runner7.3s）；固定193文件METHOD donor复制receipt、SHA/length/source前后0差异、original_sqlite_connections0；仅新copy连接，固定MockTransport非真实新源。四namespace、已存实际估值103600.10/NOT_COMPARABLE、只读导出、旧链接、原shadow不变/formal403有行为证据 |
| 两项15 | 完整日线/旧quote时点在保留失败段中1PASS（总体1pass/1fail24.83s）；retry最终单case1PASS11.44s，3attempt/6retrievalruns、每attempt两purpose工具合计≤8及幂等/partial/ConnectTimeout/无forecast保留。独立核对新caller断言CHECKED/value0/merged0、RUN_SUMMARY1、snapshot_id/task_id分别绑定、transmission0/deliveryUNKNOWN；未重跑已PASS日线 |
| 进程／恢复 | 真API/worker/Vite、API不抢lease、重复workerALREADY_RUNNING非零、关浏览器服务存活和同workerowner；正常worker退出0/coverage NORMAL_CLOSE；备份后API+worker恢复RECOVERY_LOCK/formal403，不补旧动作通知。API CTRL_BREAK退出3、Vite3221225786、worker0明确保留，不能称全exit0；未授fixture不证明真实资格或positive LOSS恢复 |

代表性保存截图已实际查看：Today `today-ungranted.png`、Settings `settings-closed-maintenance-control.png`、History `reports-history.png`及四namespace `reports-open.png`。未授标题、未知值、四曲线／独立结果与不可比说明清晰，未发现阻碍阅读的裁切。Settings截图在展开后的控件状态，不能由文件名推断默认折叠；默认关闭/展开由实际脚本断言与完整PASS记录证明。视觉查看与纯静态检查分别记录，不补跑整套Chrome。

## 三项P95原始样本独立复算

| 测量 | 样本／warmup | nearest-rank零基index | 独立复算 | 阈值 |
| --- | --- | --- | --- | --- |
| 缓存首页HTTP+decode | 100/10 | 94 | 221.62250010296702ms | 2000ms |
| 单笔确认HTTP+decode | 100/10，30持仓 | 94 | 1079.4349999632686ms | 2000ms |
| 本地30股+5指数完整数值/应用层 | 21/无warmup | 19 | 0.5617275000549853s | 30s |

复算与已落盘值精确一致；每样本有限非负，数值层+应用层之和等于full层。21次重新计算既有features/scaler/weights/intercept校准，三个注册既有JSON只checksum/parse，1scope/29拒绝/5背景；相同输入distinct evaluation1，非21个独立研究或新动作。源码75绑定当前、模型工件/政策/交易日历及设备与时间有记录；缓存展示、数值、应用/full、外部取得分别命名，external0不当实时取得性能。成功由原始样本审计接受，没有重跑三项基准或选择最快样本；旧25 P95不计当前。

## 保护与保全

独立逐项检查15保护源、3许可JSON及原19数据库checksum。原19仅读取指定文件字节，不连接SQLite：165814272B/SHA `ec46257c4420f69c245791778c49079355700615cc3ed7b94d8027bd4dcf66c4`。owner guard-before与guard-final结构完全一致，root及own当前产品源与冻结摘要一致。

own完整runtime union的645文件/291181324B在source与root保全端全部SHA/length相同，0差异；manifest178259B/SHA `ca3331799dbf8ffcf298e45d0c2fe076ac94a939361a000cf378dfe91252ba7d`，两端manifest相同。保全位置 `.roll-data/implementation-evidence/31-final-r01`，含失败profiles、4个短pytest目录及公开browseroutputs；它们仍在own树，未删除。无private/reparse exclusions；未读hash/copy凭据或依赖cache。owner39停止记录已审，独立再对同39明确PID查询CIM均不存在（`cim-stopped.json`），无进程启动或停止。

首次独立审计harness的Windows长路径FileNotFoundError(exit1)及sandbox CIM不可访问但命令exit0的无效null结果均保留于`harness-lineage.json`和`cim-sandbox-unavailable.json`。仅修自己审计器extended-length路径，并以ErrorAction Stop/精确PID范围执行CIM成功检查；不计初次结果为CIM0。Git首次无法写ORIG_HEAD.lock的沙箱拒绝后，在root已授权窗口内范围提升成功no-ff；无产品修复、无新业务测试或HTTP。

详细机器结果见[audit.json](audit.json)，复核脚本[audit.py](audit.py)，进程结果[cim-stopped.json](cim-stopped.json)，合并后字节核对[postmerge.json](postmerge.json)。本独立动作tests0/HTTP0/SQLconnections0/provider0/sourcecollection0/fit0/forecast0/SEALED0/notice0/actualgrant0/actualReviewRecord0；既定owner METHOD_ENGINEERING grant fixture已获授权且system_usable=false，不能写成METHOD注册0，也不同于最终修复纯GRANTED投射。

所有owner失败/harness/oldNone/business0/sourceID误差与非零退出码都仍保留。没有具体证据缺口要求新增测试，故按计划不重复owner全suite/Chrome/三个benchmark。只stage独立receipt目录和issue31末尾评论；没有root status/trace/README/Completion/manual239写入，没有cleanup或push。
