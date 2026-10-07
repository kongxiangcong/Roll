# Roll

本机 React/FastAPI 应用。支持首次账户基线、权限确认、实际成交与费用追加、现金与权益、待结算/实际到账、版本历史和可靠回执；可登记资金授权并分别查看技术资格和运行健康。交易判断未启用。

## 启动（Windows PowerShell）

需要 Python 3.12+、uv、Node.js 22.12+。已验收环境见 `.scratch/roll-p0/evidence/01/acceptance.md`。

在 `backend` 目录：

```powershell
uv sync --frozen
# 可选：指定独立运行数据目录；不配置时 Windows 使用 %LOCALAPPDATA%\Roll。
$env:ROLL_DATA_DIR = Join-Path $env:LOCALAPPDATA 'Roll'
uv run --frozen uvicorn roll.app:create_app --factory --host 127.0.0.1 --port 8010
```

另一个终端，在 `frontend` 目录：

```powershell
npm ci
npm run dev -- --port 5173
```

打开 `http://127.0.0.1:5173`，在“同步账户”填写当前真实现金与持仓，先预览，再确认。两个服务默认只绑定本机。`npm run build` 生成已检查的前端构建；上述开发服务器是当前可重复的本地启动路径。

`ROLL_DATA_DIR` 控制唯一正式 SQLite 路径；默认位于操作系统用户数据目录，Unix 为 `$XDG_DATA_HOME/roll` 或 `~/.local/share/roll`。不要把真实账户数据、密钥或备份放入源码。当前首次切片只有 `roll.sqlite3`，没有无用途的市场/研究/后台骨架。

## 验证

在 `backend`：`uv run --frozen pytest -q`。应用测试使用临时真实 SQLite；恢复测试启动实际 Uvicorn 子进程，在事务前后和已收到回执后终止进程，通过重启后的 HTTP 查询验证持久性。

在 `frontend`：`npm run build`。浏览器验收自动启动两个真实服务与独立临时运行目录：

```powershell
# 使用机器上已经安装的 Chrome；未安装时可 npx playwright install chromium。
$env:ROLL_BROWSER_CHANNEL = 'chrome'
# 并行工作树可分别设置测试端口，避免复用别的账户服务。
$env:ROLL_TEST_API_PORT = '8010'
$env:ROLL_TEST_WEB_PORT = '5173'
npm run test:e2e
```

手动改变 API 端口时，前端启动终端设置 `ROLL_API_PORT` 到同一个端口。浏览器验收仅使用合成账户，不能证明真实券商同步或投资资格。

接口和精度说明见 [账户接口](docs/account-contract.md)、[实际成交与费用](docs/fill-contract.md)、[现金与权益](docs/cash-equity-contract.md)、[资金与损失口径](docs/funding-contract.md)。
