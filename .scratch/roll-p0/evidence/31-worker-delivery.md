# 31 独立 worker 与 Windows 交付切片

日期：2026-10-11。状态：**partial**。实施基线 `1c90c6edf2671b5095a649680ca04038dd0f26d0`；handoff 合入当前集成文档提交。只交付独立 worker/生产 API 角色、安装/进程/恢复契约及本票必要验收，不关闭 29/30、28 实际外发或 32—34。

## 改动与复用

- `roll.worker` 复用同一 app lifecycle、Reviews SQLite 单租约与原工作循环，没有第二队列；重复 worker 明确非零退出。工作循环和业务/统计算法未改。
- 生产 factory 默认 API，命令显式 `ROLL_RUNTIME_ROLE=API`；健康/任务/恢复入口不能启动该 API 的 worker。单独 worker 才启动计划备份。隔离目录/测试默认 IN_PROCESS 保留既有测试语义。
- 生命周期始终清理本次宿主；只释放自己的租约/marker。正常 API 退出不释放另一实际 worker，worker 停止不消除存活 API 的恢复屏障。
- 启动、停止、故障、备份/升级/恢复步骤见 [本机契约](../../../docs/local-worker-delivery.md)。README、全局 plan/status/trace 由集成维护者收口，本切片未改。

## 条款级实际结果

| 本票条款/切片 | 实际结果与边界 |
|---|---|
| 锁定干净 Windows 安装 | PASS：独立 managed 源码；uv sync --frozen --python 3.13 新建真实 `.venv`，安装 60 包；npm ci 新装 72 包；TypeScript/Vite build 成功。不是 junction 复用。依赖锁 SHA、目录属性、设备与版本有 receipt。 |
| API + 一个后台 worker + React 三进程 | PASS：真实 Chrome 与隔离 SQLite；界面基线/差异/确认/回执通过；浏览器关闭后 API/worker/页面仍存活；后台离线观察完成且无预测。此切片不替代五入口全联验。 |
| 单租约、死亡/重启与身份 | PASS：独立实际 owner，重复 worker 被拒；真实强制终止后 API 查询不接管租约，任务保持 QUEUED；重启沿同任务 ID 与限额处理，原发布观察不改。 |
| 正常关闭、存活宿主与恢复锁 | PASS：隐藏隔离控制台 Ctrl+Break 正常结束；额外 API 正常生命周期不释放另一 worker；待恢复时存活 API 阻止 worker 应用备份；全部宿主停止后恢复保持 RECOVERY_LOCK，再启 worker 不解除锁。 |
| 缺口与不补造 | PASS：PROCESS_OR_SLEEP_GAP_UNOBSERVED、正常离线状态、forward_predictions_reconstructed=false、expired_opportunities_sent=false；账户版本与已发布结果保留，无前向样本。 |
| 恢复接口兼容 | PASS：按已接受24接口修正两条旧断言：技术 state=UNGRANTED 与 runtime_state/recovery=RECOVERY_LOCK 分开；formal_judgment=DISABLED、allowed_actions=[]、grant_statuses=[]，METHOD forecast 仍 NOT_GRANTED，正式 evaluate 仍拒绝。两原件恢复例子及4受影响角色/worker例子共6通过（65.77s）。不把没有历史 grant 的 fixture 夸作已覆盖有 grant 的撤权恢复竞态。 |
| 定向兼容回归 | PASS：4 个新角色/实际进程用例（36.39s）；25 个已审代码且无拟合的复盘/备份/实际恢复用例（190.48s），1 个旧共享控制台 graceful 用例排除，其语义由本票隔离控制台 seam 覆盖。测试数只作运行记录，不作 90 AT 通过数。 |
| 源码保护 | PASS：父任务 source-final.json 前 15 个源码逐个 SHA-256/长度一致；没有原 19 数据库/实际研究、SEALED、provider 或外发操作。 |
| 完整 90 AT /125 P0 /14 BR /10 不变量与跨票出口 | pending：仍逐责任票/实际行为核对；本切片不填 blanket PASS。29/30 未关闭；28 外部实际送达需用户配置；32—34 保留真实时间状态。 |
| 容量/P95与完整五入口 | pending：本机仅合成小账户交付路径，未测 30 股+5 指数容量或以小样例声称其性能通过。 |
| 真实统计、前向、资格与资金 | 未执行/未启用：安装/进程稳定不能代替 G1—G7、技术审阅匹配、真实资金与最终部署检查。当前 CODEX-only；历史 DeepSeek 不替代当前 CODEX。 |

设备：Windows 11 家庭中文版 10.0.26200；AMD Ryzen 7 7840H，8 核/16 线程，约 27.7 GiB 可见内存。uv 0.11.17，Python 3.13.12，Node v25.8.1，npm 11.11.0。具体原始 JSON 与锁哈希位于保全目录。

## 中断扩测与受控兼容修复

第一次扩大到整个旧备份模块时，已有 METHOD 模型工件用例不属于本票无拟合范围，发现后停止隔离 runner；该用例在停止前已到合成恢复 target，故**已有合成 METHOD 模型工件生成，不宣称零合成拟合**。所有材料仍在隔离测试目录，未触碰实际研究、原19数据库或授权。该组是 interrupted，不能声称整组通过。

输出中的两处 F 对应：`test_restored_user_funding_remains_immutable_history_and_current_recovery_guard` 与 `test_registered_research_feature_model_forecast_and_source_files_restore_as_method_only`。旧断言期待无 grant 时 `/api/capabilities.state=RECOVERY_LOCK`；当前24的查询返回 `state=UNGRANTED`、`runtime_state=RECOVERY_LOCK` 及完整 recovery，主责任票随后明确接受分离语义，授权本31最小修复两旧断言，不修改产品将两状态混合。当前 root1c90的 Capabilities 代码与本切片同源，31 未修改它。失败详情因中断未完整打印，仅将 collection 顺序与实际代码/旧断言定位记录为风险，不能冒称已完成独立 baseline-red 运行。随后无拟合有限回归取得上表结果。为这一必要原件恢复例子，主责任票另明确授权只在全新隔离 profile 执行原 fixture 的 METHOD 训练，精确两例加4角色/恢复用例为6 PASS；未扩大整套回归，未取数/provider/SEALED/实际模型或预算。先前 interrupted 记录仍保留。

训练层次：METHOD 合成 fixture 工件训练存在（前次扩测已生成，本次必要例子经明确追加授权再执行）；**实际研究训练=0**。两用例没有创建历史能力 grant，grant_statuses=[] 与 METHOD forecast 的 NOT_GRANTED 只证明该样例不能通过恢复升级为正式资格；有旧 grant/撤权/通知竞态仍沿主责任票证据，不扩大本票声明。

## 原件保全

全部本票忽略 runtime、SQLite/原件/备份、失败与通过日志、浏览器 screenshot/receipt、host/lock/protected-source/source-snapshot 清单保全到：

`D:/dsh-proj/Roll/.roll-data/implementation-evidence/31/worker-delivery/`

其中 `archive-manifest.json` 逐文件记录原路径、目标相对路径、SHA-256、长度与复制核验；`scope.json` 记录测试/真实边界。managed tree 可在独立接受之后用 app archive_worktree 回收。锁定依赖安装环境可由锁文件重新生成；不将 `.venv`/node_modules 当运行证据迁入正式源码。安装结果有独立 receipt，源码版本/哈希与依赖锁保留。


## 最新30 producer 集成后的定向组合复验

交接前合入已独立接受的集成 `2db3bd1f6ea2fcb89d3c2b00020de7a4742ec881`（30 producer source `463658b`），无冲突；31 没有修改30 parser、binding 或 gate。既有 Reviews 循环仍调用 forward.work，真实 FORWARD 计划达到既有 admission 条件时才由 forward.check 调用 post_close.capture_once；本轮没有建立任何真实或 METHOD forward 计划来代替缺失资格。

最新组合定向 **6 PASS / 47.63s**：4个角色用例（含新增公开 API/source-job 与显式 WORKER 组合）、1个实际 OS worker死亡重启/正常关闭/restore，以及30已有有界重复触发用例。新增测试使用 MockTransport 精确 METHOD 原件与真实隔离 SQLite：API 盘后手动采集1次后仍无worker lease/session；另启 WORKER 消费同库普通任务；重复采集复用原job、只有1batch与1次受控请求，账户保持一致，forecast=null、forward_sample_created=false。该测试不证明真实源完整性、worker实际联网采集或前向起点。

新增 runtime/日志、最新 source 与15保护 receipt 追加保全在 `D:/dsh-proj/Roll/.roll-data/implementation-evidence/31/worker-delivery/composition30/`，独立 `archive-manifest.json`/`scope.json`；原4057文件/341456922bytes的根清单不覆盖。此次生产合并影响对应检查已复验，docs-only无需重复原干净安装/Chrome验收。31仍 partial，30 producer仍 partial，28实际外发及29/32—34原条款不因此关闭。
