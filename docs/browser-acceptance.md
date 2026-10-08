# 本地Chrome验收的账户隔离

Playwright启动真实FastAPI、SQLite与Vite；ROLL_ENV=test和临时ROLL_DATA_DIR只包含合成账户，不暴露产品reset接口。`frontend`目录先设置：

```powershell
$env:ROLL_BROWSER_CHANNEL='chrome'
$env:ROLL_TEST_API_PORT='8028'
$env:ROLL_TEST_WEB_PORT='5188'
```

默认 `npm run test:e2e` 逐文件启动真实服务和空 SQLite；文件之间隔离，同一个文件内顺序用例保留事实链（包括 reconcile 的两例）。有限默认集合是 baseline/cash-equity/codex-evidence/csv/deepseek-evidence/fills/funding/market/market-overflow/reconcile/valuation。默认缺凭据路径不发真实模型请求或取新公网数据。每个文件的输出、报告和退出码见 `frontend/test-results/default/`，任一失败使最终命令失败。

历史08默认11通过/2失败/1跳过原报告保留；修复后的默认结果单列在[审阅修复验收](../.scratch/roll-p0/evidence/review/fixes.md)，不覆盖旧红。运行默认命令前移除 `ROLL_ENV_FILE`、外部来源、METHOD工厂、已有数据目录和两阶段恢复变量；runner遇这些profile会明确拒绝混用，清除 DeepSeek/Fuyao/OpenAI/Codex 凭据环境。11/12真实SDK、07/08实际来源、14/15方法与已有真实原件、17/18/19/22研究保全、16备份两阶段必须显式单独运行。

以下实际公开来源profile会联网，不能算默认离线集合：

```powershell
$env:ROLL_LIVE_MARKET='1'
$env:ROLL_LIVE_FALLBACK='1'
npx playwright test tests/e2e/evidence-live.spec.ts tests/e2e/resolution-live.spec.ts
```

16备份需要两个完整服务生命周期共享同一个全新目录，create结束后再启动restore，禁止换目录或重置生产状态：

```powershell
$env:ROLL_TEST_DATA_DIR='D:/your-isolated-runtime/backup-acceptance'
$env:ROLL_BACKUP_BROWSER_PHASE='create'
npx playwright test tests/e2e/backups.spec.ts
$env:ROLL_BACKUP_BROWSER_PHASE='restore'
npx playwright test tests/e2e/backups-restored.spec.ts
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

17研究先用宿主真实07归档目录（非来源账户）运行`backend/.venv/Scripts/python.exe -X utf8 scripts/research_protocol_acceptance.py --data-root backend/.roll-data/implementation-evidence/17/acceptance-17-final --port 8037`。需要已有`research-inputs/07-browser`及原字节包，不能用方法fixture代替。

从frontend目录使用独立已归档真实研究目录，原报告与旧协议会保留，每次Chrome生成关联后继记录：

```powershell
$env:ROLL_RESEARCH_LIVE='1'
$env:ROLL_RESEARCH_DATA='D:/dsh-proj/Roll/backend/.roll-data/implementation-evidence/17/acceptance-17-final'
$env:ROLL_TEST_API_PORT='8037'
$env:ROLL_TEST_WEB_PORT='5197'
npx playwright test --config playwright.research.config.ts
```

研究在历史子视图、五个主入口保持；不启动真实资金前向。17独立1passed/构建与公开HTTP原件保全见[票级验收](../.scratch/roll-p0/evidence/17/acceptance.md)。历史共享夹具红保留，新的默认结果独立留证。

18先运行 `backend/.venv/Scripts/python.exe -X utf8 scripts/daily_execution_acceptance.py --source D:/dsh-proj/Roll/backend/.roll-data/implementation-evidence/17/acceptance-17-final --data-root backend/.roll-data/acceptance-18-final --port 8038`。目标须全新，原目录只读；仅宿主DEV/CAL，真实120未知/0训练与METHOD另列。固定夹具不替真实来源。

从frontend设置 `ROLL_EXECUTION_LIVE=1`、`ROLL_BROWSER_CHANNEL=chrome`、`ROLL_EXECUTION_DATA` 为真实该保全目录，运行 `npx playwright test --config playwright.executions.config.ts`（API8038/web5198）；重跑追加METHOD记录/复评，原结果不改。独立2passed和实际HTTP/55pass1共享SDK轮询红+单例复验、原件保全均见[18验收](../.scratch/roll-p0/evidence/18/acceptance.md)，不称默认共享全Chrome绿。


15方法Chrome单独调用 `ROLL_PLAYWRIGHT_FACTORY=review_method_app:factory`、`ROLL_BROWSER_METHOD=1`，8035/5195与空隔离ROLL_TEST_DATA_DIR；运行 `npx playwright test reviews.spec.ts`。只该测试工厂提供固定方法源/盘后时钟，无生产覆盖端点。真实原件缓存先在backend运行 `python -X utf8 ../scripts/acceptance_15.py`（只读复制根07保全，创建新自身runtime），按输出设置ROLL_TEST_DATA_DIR，移除方法factory/flag，设置ROLL_REVIEW_REAL_CACHE=1，运行 `npx playwright test reviews-real-cache.spec.ts`。方法与真实原件/本地缓存性能分列，均未证明10/8新行情或未来正式动作/通知；[15票级证据](../.scratch/roll-p0/evidence/15/acceptance.md)。

14分开使用隔离目录，统一 `ROLL_BROWSER_CHANNEL=chrome`、`ROLL_TEST_API_PORT=8034`、`ROLL_TEST_WEB_PORT=5194`。METHOD设 `ROLL_BROWSER_METHOD=1`、`ROLL_PLAYWRIGHT_FACTORY=verification_method_app:factory`，各自全新 `ROLL_TEST_DATA_DIR` 后运行 `npx playwright test verification-method.spec.ts` 或 `verification-joint.spec.ts`，不可两文件共用同一列表/原件夹具。真实使用14保全的real目录副本作为 `ROLL_TEST_DATA_DIR`，移除METHOD/factory，设 `ROLL_REAL_VERIFICATION=1`，运行 `npx playwright test verification-real.spec.ts`；Git real-run.json指向既有实际snapshot ID，须保留对应原件/SQLite/Parquet。重跑追加真实观察/核验历史，不刷新旧原值/可得时点，不再取外部数据或发模型请求；独立METHOD1、联合METHOD1、最终真实2及原报告纠错见[14验收](../.scratch/roll-p0/evidence/14/acceptance.md)。
19 独立研究模型验收：先在backend设置 PYTHONPATH=tests/application，运行 .venv/Scripts/python.exe -X utf8 ../scripts/transparent_model_acceptance.py --source D:/dsh-proj/Roll/backend/.roll-data/implementation-evidence/18/acceptance-18-final --data-root .roll-data/acceptance-19-final --port 8039（全新目标、源只读）。从frontend设置 ROLL_MODEL_LIVE=1、ROLL_BROWSER_CHANNEL=chrome、ROLL_MODEL_DATA 指向此目录，运行 npx playwright test --config playwright.models.config.ts，API8039/web5199。实际120不可评分→失败与METHOD40DEV/20CAL工件分列，Chrome2passed/build通过，真实模型/校准未冻，20受阻；[19票级证据](../.scratch/roll-p0/evidence/19/acceptance.md)。默认共享05fixture红及18记录的SDK20秒轮询红不由此转绿。

22独立风险政策分实际无授权与隔离METHOD目录。先从根运行`backend/.venv/Scripts/python.exe -X utf8 scripts/risk_policy_acceptance.py --source D:/dsh-proj/Roll/backend/.roll-data/implementation-evidence/19/acceptance-19-final --data-root <全新目录> --port 8042`；METHOD加`--method`，父进程PYTHONPATH指backend/tests/application。frontend设置`ROLL_RISK_LIVE=1`、`ROLL_BROWSER_CHANNEL=chrome`、`ROLL_RISK_DATA`后运行`npx playwright test -c playwright.risk-policies.config.ts`；METHOD加`ROLL_RISK_METHOD=1`。API8042/web5202，各自1passed，原检查历史/压力/未知/重放/403/账户不变保持；实际无授权INCONCLUSIVE、METHOD不升级实际资格。相关17项与52module构建通过，[22验收](../.scratch/roll-p0/evidence/22/acceptance.md)。默认05共享fixture红与18 SDK方法轮询红仍按旧证据保留，不宣称全仓全绿。

审阅修复把DeepSeek方法测试等待改为公开运行记录中冻结的 timeout_seconds 加10秒收尾窗口（进程等待最多5秒、目录清理最多1秒及查询调度）；生产120秒/工具/字节预算未放宽。18旧20秒轮询红保留，新完整后端结果见审阅修复验收。
