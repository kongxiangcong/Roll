# Roll 本机三进程启动契约（31 工程切片）

当前交付版本的物理安装、三角色及备份恢复已独立有限接受，见[最终31](../.scratch/roll-p0/evidence/31-final/acceptance.md)和[独立核对](../.scratch/roll-p0/evidence/continuation-2026-10-11/ticket31-final-independent/acceptance.md)。worker正常关闭exit0；API信号关闭exit3、Vite3221225786原样记录，不概括为全exit0。恢复保持RECOVERY_LOCK，实际资格和正向LOSS另需有效证据。29工程隔离已接受，30九个有限来源切片已接受且尝试关闭；完整来源仍不足。以下早期切片说明保留其原时点。

本说明交付独立 worker 的安装与运行接口。31 尚为 partial；29 跨出口联验、30 实际来源 producer 与前向证据、28 用户配置后的真实外发、32—34 仍按各票实际状态收口。当前后端范围为 CODEX；历史 DeepSeek 材料保留，不能启动新 DeepSeek 验收或替代当前 Codex 技术审阅。技术审阅完成不等于 G1—G7 PASS 或资金启用。

## 干净 Windows 安装

使用独立源码路径，不复制旧 `.venv` 或 `node_modules`，不以 junction 共享安装目录。需要 Python 3.13、uv、Node.js/npm；具体已验环境见本票 receipt。源码含 `backend/uv.lock` 和 `frontend/package-lock.json`。

```powershell
Set-Location <独立源码路径>\backend
uv sync --frozen --python 3.13
Set-Location ..\frontend
npm ci
npm run build
```

安装失败保留错误；不能删锁文件重新解析来声称锁定安装成功。开发测试替身、实际研究数据、`.env`、密钥文件和日志均不加入源码交付。运行目录建议使用较短的本机路径，避免未开启 Win32 长路径支持的环境超过 260 字符。

## 三个独立进程

三进程使用同一版本源码。API 与 worker 使用同一 `ROLL_DATA_DIR`，不同本机账户/目录属于不同实例。首次安装或升级先等 API `/api/health` 返回成功，再启动 worker，避免并行初始化；升级必须先停止该目录的全部宿主。

在两个 PowerShell 窗口分别设置相同私有配置（下面示例不配置 provider，不执行真实外发）：

```powershell
$env:ROLL_ENV='local'
$env:ROLL_DATA_DIR="$env:LOCALAPPDATA\Roll"
# 可选：显式私有文件，内容按字面量读取；进程变量优先。
# $env:ROLL_ENV_FILE='<源码外>\roll-runtime.env'
Set-Location <源码路径>\backend
```

API 窗口：

```powershell
$env:ROLL_RUNTIME_ROLE='API'
.\.venv\Scripts\python.exe -m uvicorn roll.app:create_app --factory --host 127.0.0.1 --port 8010
```

worker 窗口：

```powershell
$env:ROLL_RUNTIME_ROLE='WORKER'
.\.venv\Scripts\python.exe -m roll.worker
```

第三个窗口：

```powershell
Set-Location <源码路径>\frontend
$env:ROLL_API_PORT='8010'
node .\node_modules\vite\bin\vite.js --host 127.0.0.1 --port 5173 --strictPort
```

浏览器访问 `http://127.0.0.1:5173`。三个进程由本机窗口/宿主持有；关闭网页不停止它们。后台启动可用 `Start-Process -WindowStyle Hidden -PassThru` 并将标准输出/错误分别重定向到源码外日志；保存本次启动 PID。Windows venv 启动 PID 可能是 launcher，实际 worker owner 以 `/api/reviews/health` 的 `worker.host_owner`（PID、创建时刻、nonce）为准。

API 的 `/api/health` 返回 `runtime_role=API`；它只提交持久化任务，不因健康、任务查询、summary 或恢复入口启动 worker。worker 没有 HTTP listener；它复用当前 Reviews 工作循环、SQLite 单租约、有限重试和后台维护/备份，不建立第二队列。已有前向入口沿原冻结规则运行；独立进程本身不能赋予研究或正式权限。worker 打印 `ROLL_BACKGROUND_WORKER_RUNNING`，重复 worker 非零退出并报告 `BACKGROUND_WORKER_ALREADY_RUNNING`。已知启动/恢复阻塞使用明确错误码，其他异常只输出脱敏失败码。

显式 `runtime_role` 参数优先于 `ROLL_RUNTIME_ROLE`；无参数的生产 factory 默认 API。显式隔离目录或 `ROLL_ENV=test` 的旧应用测试默认 `IN_PROCESS`，保留既有 TestClient/崩溃验收语义；生产三进程命令须明确角色。未知角色在 bootstrap 前失败，不创建运行目录。

## 停止、故障和恢复

正常停止在各控制台使用 Ctrl+C，worker 也处理 Windows Ctrl+Break；等待进程退出。API 停止只移除自己的 host marker，不能释放另一 worker 的租约；worker 正常停止记录实际结束与正常离线状态。隐藏进程需要保留的 PID 与日志核对后停止；如果使用 `taskkill /PID <本次启动PID> /T /F`，这是强制终止，随后应看到实际未观察缺口。不要把 launcher 的停止误报为实际 worker 已停止。

worker 死亡时 API 仍可确认账户/提交任务，但不会取得租约；任务保持排队。重启 worker 沿原任务标识、已用尝试次数和限额恢复。停机、睡眠或故障期间不补造前向预测、不发送过期机会，不承诺离线监控。健康 RUNNING 指实际活的 owner，不能用客户端 complete 标记替代归档/资格检查。

计划备份只由 worker（兼容测试则由 IN_PROCESS）运行。API 仍提供本机手工备份、导出和暂存恢复接口。备份包含数据库与被登记原件的一致清单，排除任务凭据。`/api/runtime/backups/status` 分别显示最新成功点、未覆盖变化、损坏、待恢复与恢复锁；暂停宿主期间没有新备份保证。

升级：停止该目录全部 API/worker 宿主后切换同一版本并按锁文件安装；启动时原有 bootstrap 根据部署指纹建立 PRE_UPGRADE 恢复点。迁移失败仍走已有回滚材料，不从其他未核实目录复制数据库。

恢复：API 暂存合格备份只返回 `PENDING_RESTART`，存活服务继续用原状态；只要 API 或 worker owner 存活，另一个启动就拒绝应用恢复，错误 `RESTORE_PENDING_STOP_ALL_LOCAL_HOSTS`。停止全部宿主后重新启动 API，恢复后必须保持 `RECOVERY_LOCK`；再启动 worker不能解除它。离线工具为：

```powershell
.\.venv\Scripts\python.exe -m roll.runtime.backups restore --data-dir '<运行目录>' --bundle '<合格导出ZIP>'
```

恢复锁的账户核对、当前授权和可能遗漏撤回沿现有受控入口核实；旧备份不恢复正式动作/通知权限。先查看实际恢复点和缺口，再决定下一步，不以安装成功替代账户与资格核验。

## 本切片的可复验边界

```powershell
# 只使用新的隔离 runtime；不能指向真实账户或研究目录。
$env:ROLL_ENV='test'
.\backend\.venv\Scripts\python.exe -m pytest backend/tests/application/test_runtime_roles.py backend/tests/recovery/test_worker_process.py -q
node frontend/scripts/worker-delivery-acceptance.mjs
```

浏览器验收脚本自动创建全新隔离目录、三本机进程和独立浏览器；清除外部/METHOD凭据定位变量，不取数、不调用模型、不外发、不 fit、不启动前向实验。其结果仅证明安装、账户回执、浏览器关闭不终止服务及无预测的离线观察。实际来源、统计、资金、容量和完整五入口/90 AT/125 P0/14 BR/10不变量按主责任票另留结果。
