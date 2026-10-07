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
