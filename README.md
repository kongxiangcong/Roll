# Roll

本机 React/FastAPI 应用。支持账户与 CSV 全批确认、成交和费用、现金与权益、更正与一致性检查、估值、资金授权、备份与恢复。市场事实、来源选择、独立核验和重点复盘保留原件、取得时点与版本；研究登记、日线事件、透明模型和独立风险政策保留尝试及失败记录。交易判断与真实资金前向未启用。

当前新取证和技术审阅仅支持 CODEX；历史 DeepSeek 记录保留，后续不测试其能力。真实历史量价重建研究已完成训练、校准拟合及模型工件冻结；校准器仍为 FITTED_UNVALIDATED，重建用途不等于严格历史 PIT。已批准冻结材料的真实 CODEX 技术审阅完成，G4/G5 为 FAIL、其他门槛为 INCONCLUSIVE，真实能力仍为 NOT_GRANTED。工程完成、完整实验冻结、验证交付和正式资格分别记录，见 [任务状态](.scratch/roll-p0/execution-status.md)。

前向数据积累和独立 METHOD 工程案例继续分开；历史重建训练不能补成真实前向预测。每日采集与虚拟构建命令、数据库目录、时点契约和可用门禁见 [前向数据契约](docs/prospective-data-contract.md)。当前完整盘后状态与权益来源仍有缺口，尚未建立真实前向起点。

## 启动（Windows PowerShell）

需要 Python 3.12+、uv、Node.js 22.12+。已验收环境见 `.scratch/roll-p0/evidence/01/acceptance.md`。

在 `backend` 目录：

```powershell
uv sync --frozen
# 可选：指定独立运行数据目录；不配置时 Windows 使用 %LOCALAPPDATA%\Roll。
$env:ROLL_DATA_DIR = Join-Path $env:LOCALAPPDATA 'Roll'
uv run --frozen uvicorn roll.app:create_app --factory --host 127.0.0.1 --port 8010
```

运行工厂启动时读取仓库根目录 `.env`；可使用 `ROLL_ENV_FILE` 明确指定其他文件。支持 `KEY=value`、可选 `export`、单/双引号字面值和行尾注释，不执行变量插值或 shell。进程环境变量优先，文件中的 `DEEPSEEK_API_KEY`、`FUYAO_API_KEY` 只进入宿主环境；不要提交凭据。显式数据目录的测试工厂不读取此文件，`ROLL_ENV=test` 也不自动读取仓库凭据；默认浏览器命令拒绝 `ROLL_ENV_FILE` 与真实验收 profile，并移除凭据环境变量。

使用 Codex 后端时，在启动后端的终端显式指定已有的 ChatGPT 登录文件，例如 `$env:ROLL_CODEX_AUTH_FILE = Join-Path $env:USERPROFILE '.codex\auth.json'`。应用不会自动搜索登录文件；文件只供工作进程认证，不会进入取证归档或备份。

另一个终端，在 `frontend` 目录：

```powershell
npm ci
npm run dev -- --port 5173
```

打开 `http://127.0.0.1:5173`，在“同步账户”填写当前真实现金与持仓，先预览，再确认。两个服务默认只绑定本机。`npm run build` 生成已检查的前端构建；上述开发服务器是当前可重复的本地启动路径。

`ROLL_DATA_DIR` 控制应用数据目录；默认位于操作系统用户数据目录，Unix 为 `$XDG_DATA_HOME/roll` 或 `~/.local/share/roll`。其中 `roll.sqlite3` 保存账户、证据和任务元数据，运行时可能有 SQLite WAL/SHM；`raw/` 保存账户 CSV 和来源原字节，`parquet/` 保存规范化事实，`research-inputs/` 保存导入的研究依据，`backups/` 保存完整恢复包与校验记录。原件按 SHA256 引用，复制单个数据库不能替代完整备份。不要把真实账户数据、凭据或备份提交到源码。模型工作进程使用独立临时目录并在结束后清理；凭据不属于取证原件或恢复包。

## 验证

在 `backend`：`uv run --frozen pytest -q`。应用测试使用临时真实 SQLite 和明确 METHOD 来源；恢复测试启动实际 Uvicorn 子进程并检查进程退出、持久性与恢复。SDK 方法使用本地固定提供方，不发送真实计费模型请求。历史真实来源与真实模型验收单列，不由默认测试代替。

在 `frontend`：`npm run build`。默认浏览器验收逐文件启动真实服务，每个文件有独立空 SQLite，同文件内的顺序用例共享事实链；不会复用用户账户、发真实模型请求或取新公网数据：

```powershell
# 使用机器上已经安装的 Chrome；未安装时可 npx playwright install chromium。
$env:ROLL_BROWSER_CHANNEL = 'chrome'
# 并行工作树可分别设置测试端口，避免复用别的账户服务。
$env:ROLL_TEST_API_PORT = '8010'
$env:ROLL_TEST_WEB_PORT = '5173'
npm run test:e2e
```

默认集合及逐文件退出码保存在 `frontend/test-results/default/manifest.json`；任一文件失败都会让命令失败。外部来源、SDK 方法、已有研究原件和备份两阶段使用 [独立验收命令](docs/browser-acceptance.md)，先移除相应 profile 环境变量再运行默认命令。手动改变 API 端口时，前端启动终端设置 `ROLL_API_PORT` 到同一个端口。浏览器默认集合使用合成账户，不能证明真实券商同步或投资资格。

接口说明见 [账户](docs/account-contract.md)、[成交与费用](docs/fill-contract.md)、[现金与权益](docs/cash-equity-contract.md)、[资金](docs/funding-contract.md)、[证据取得](docs/data-evidence-contract.md)、[来源选择](docs/source-resolution-contract.md) 和 [研究登记](docs/research-protocol-contract.md)。

## CNEquity 补充数据层

先运行 `backend\.venv\Scripts\python.exe -B -X utf8 scripts\setup_cnequity.py` 安装固定版本的隔离适配器环境，再使用现有 `scripts\collect_prospective.py` 持续追加。来源开关、失败退避、异常隔离、修订及源值差异均保存到前向库；完整性通过后生成数据库与原件一致备份。详情见 [数据层维护契约](docs/cnequity-data-contract.md)。系统继续积累中，不因接入或虚拟模型成功而启用。
