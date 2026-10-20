# 02 来源原件不可读修复；整票仍 partial

基线0f57695489453f7b53747dbc62d825a4a71ebafa，代码提交28da15d。持久Goal已建立，尚未完成。用户确认没有现成交易所/数据商交付文件。来源限定检索、现场26票与来源完整性核验分别见discovery.md、audit.json。

## 修复及直接证据

源码原来直接read_bytes；原件/清单缺失会抛出FileNotFoundError而不是公开拒绝诊断。现在仅将OSError转换成409 `AUTHORITY_MANIFEST_UNAVAILABLE` 或 `AUTHORITY_ORIGINAL_UNAVAILABLE:<role>`，读取及摘要校验仍在保存前。没有添加来源资格、重写已存记录或修改旧模型。

pytest-red03.log实际复现FileNotFoundError，1 failed/10.54秒。前两次沙箱运行未进入断言：首次无输出中止，第二次faulthandler明确定位asyncio socketpair.accept，随后中止；这两个结果不是产品失败证据。允许本地回环的运行环境中完成红绿验证。

pytest-green.log：9 passed/55.48秒，覆盖authority supplements与daily sessions。新增缺失测试在隔离目录隐藏清单/原件，明确409、无新增评估、账户0不变、先前归档读取和幂等重放不变；这是METHOD故障注入。正向归档材料来自已有真实原件，不是新增真实行情采集。

build.log：TypeScript/Vite通过，3.49秒，保留既有大包警告。chrome.log：Chrome channel，1 passed/18.3秒，端口18261/15261，API角色明确。完整复制r02-session-compare01到新的r-contract-browser01，包括backups/capability-journal/origin.json。浏览器零POST，验证原保存日线会话、未知/拒绝提示、16原件链接及390px布局；mobile.png已查看。浏览器没有注入缺失故障，缺失拒绝由公开API pytest直接证明。

运行命令：

```powershell
$env:PYTHONPATH='backend/src'
backend/.venv/Scripts/python.exe -m pytest backend/tests/application/test_authority_supplements.py backend/tests/application/test_daily_sessions.py -q -o faulthandler_timeout=60 --basetemp=.scratch/r-contract-green01
# frontend工作目录
npm run build
$env:ROLL_E2E_FILE_DATA_DIR='D:/dsh-proj/Roll/.scratch/r-contract-browser01'
$env:ROLL_TEST_API_PORT='18261'
$env:ROLL_TEST_WEB_PORT='15261'
$env:ROLL_BROWSER_CHANNEL='chrome'
npx playwright test --config=playwright.authority-reference-integrity.config.ts
```

## 未满足条件

02完整会话/适用交易类别、精确供应商口径、修订终态和正向用途仍缺；原两日诊断不改变。03完整状态及否定覆盖、04全行动修订取消/旧义务也未证。05/06/07/08/23—26原门槛均保留。状态仍15 complete、5 partial、6 pending，未声称全部开发完成。下一独立可调查范围为04已有公告窗口中尚未归档的旧年度实施原件，不重复02封口预算。
