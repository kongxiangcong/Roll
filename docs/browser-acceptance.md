# 本地Chrome验收的账户隔离

Playwright启动真实FastAPI、SQLite与Vite；ROLL_ENV=test和临时ROLL_DATA_DIR只包含合成账户，不暴露产品reset接口。`frontend`目录先设置：

```powershell
$env:ROLL_BROWSER_CHANNEL='chrome'
$env:ROLL_TEST_API_PORT='8028'
$env:ROLL_TEST_WEB_PORT='5188'
```

当前默认 `npm run test:e2e` 全文件同一账户运行存在05夹具冲突：reconcile.spec首例要求version0，但前序文件已确认基线/交易，首例未检查draft/confirm的409/422，第二例又依赖首例生成的利息事实。08保留默认失败原报告，没有改产品校验或称默认全绿；31收口通用runner。在此之前，明确分列以下两组，每次Playwright调用启动自己的临时空数据库：

```powershell
# 05空账户两例，第二例保留第一例的事实链
npx playwright test tests/e2e/reconcile.spec.ts
# 其余共享组合，含07/08真实公开取数（会联网，0 paid API）
$env:ROLL_LIVE_MARKET='1'
$env:ROLL_LIVE_FALLBACK='1'
npx playwright test --grep-invert 'scoped declaration, append correction|CSV v3 confirms replacement'
```

08固定源修订/局部状态缺口页面单独运行；只此工厂提供明确METHOD_CASE控制端点，生产app没有该端点：

```powershell
Remove-Item Env:ROLL_LIVE_MARKET -ErrorAction SilentlyContinue
Remove-Item Env:ROLL_LIVE_FALLBACK -ErrorAction SilentlyContinue
$env:ROLL_BROWSER_METHOD='1'
$env:ROLL_PLAYWRIGHT_FACTORY='resolution_method_app:factory'
npx playwright test tests/e2e/resolution-method.spec.ts
Remove-Item Env:ROLL_BROWSER_METHOD -ErrorAction SilentlyContinue
Remove-Item Env:ROLL_PLAYWRIGHT_FACTORY -ErrorAction SilentlyContinue
```

方法源不证明真实异常/真实修订，实际源运行保留原字节/SHA、供应商时间、取得时点和有限覆盖。08票级日志/页面/档案保全清单见 [验收](../.scratch/roll-p0/evidence/08/acceptance.md)。不合并不同账户的测试结果冒充一次默认suite全绿。

17研究先用宿主真实07归档目录（非来源账户）运行`backend/.venv/Scripts/python.exe -X utf8 scripts/research_protocol_acceptance.py --data-root backend/.roll-data/acceptance-17-final --port 8037`。需要已有`research-inputs/07-browser`及原字节包，不能用方法fixture代替。

从frontend目录使用独立已归档真实研究目录，原报告与旧协议会保留，每次Chrome生成关联后继记录：

```powershell
$env:ROLL_RESEARCH_LIVE='1'
$env:ROLL_RESEARCH_DATA='D:/dsh-proj/Roll/.scratch/worktrees/17-research-protocol/backend/.roll-data/acceptance-17-final'
$env:ROLL_TEST_API_PORT='8037'
$env:ROLL_TEST_WEB_PORT='5197'
npx playwright test --config playwright.research.config.ts
```

研究在历史子视图、五个主入口保持；不启动真实资金前向。17独立1passed/构建与公开HTTP原件保全见[票级验收](../.scratch/roll-p0/evidence/17/acceptance.md)。默认全文件05共享fixture红仍保留，不用17结果替代默认suite全绿。

18先运行 `backend/.venv/Scripts/python.exe -X utf8 scripts/daily_execution_acceptance.py --source D:/dsh-proj/Roll/backend/.roll-data/implementation-evidence/17/acceptance-17-final --data-root backend/.roll-data/acceptance-18-final --port 8038`。目标须全新，原目录只读；仅宿主DEV/CAL，真实120未知/0训练与METHOD另列。固定夹具不替真实来源。

从frontend设置 `ROLL_EXECUTION_LIVE=1`、`ROLL_BROWSER_CHANNEL=chrome`、`ROLL_EXECUTION_DATA` 为真实该保全目录，运行 `npx playwright test --config playwright.executions.config.ts`（API8038/web5198）；重跑追加METHOD记录/复评，原结果不改。独立2passed和实际HTTP/55pass1共享SDK轮询红+单例复验、原件保全均见[18验收](../.scratch/roll-p0/evidence/18/acceptance.md)，不称默认共享全Chrome绿。
