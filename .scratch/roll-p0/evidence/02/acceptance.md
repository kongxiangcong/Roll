# 02 实际成交与费用 · 验收

日期2026-10-07；实现0e26d30，资金授权10合并88a94d5（integration e981380）。01/02/10联合结果：真实 SQLite / FastAPI 与真实进程测试 **77 passed, 1 warning**，54.13s；真实 Chrome **3 passed**，13.1s；TypeScript/Vite构建通过。[后端原输出](backend-test.txt)、[浏览器输出](browser-test.txt)、[浏览器结构结果](browser-result.json)、[构建](frontend-build.txt)。本票新增17项（成交12、进程故障3、真实旧版升级1、性能1），继承01的22项及10的38项。

| 主验收 | 已通过证据与实际预期 |
|---|---|
| AT-03 | test_fills.py 第一个买入预览/确认/回执查询；真实浏览器 fills.spec.ts 实际输入→暂估预览→确认→持久回执→今天→补费→历史，截图 [暂估](fill-provisional.png)、[历史](fill-history.png)。实际份额/价格8位原精度保留；事件取得系统实际记录时点。 |
| AT-08 | 可靠分笔去重返回原回执；同价同量两笔同委托均保留；缺失ID歧义保留；矛盾原材料QUARANTINED、公开查询且无正式入账。CONTRARY/EXCESS_QUANTITY/OFFLINE/NO_RECOMMENDATION为用户事实标记；建议关联UNKNOWN，不冒充26实际动作匹配。 |
| AT-09 | 已知/未知费与保守占用、原费用不可变、追加 FEE_ADJUSTMENT；读取事件重放后现金/持仓/批次/收益一致。100000买300×10费5→96995现金/3005取得成本；卖100×12费5→98190/余成本2003.33/收益193.33；末笔→100585/收益585。先保守费10后部分卖出再实际5，得到相同结果；历史原暂估仍存在。 |
| AT-40 | 四并发同键一次成交，继承旧版本/同键异内容拒绝；真实子进程 before_commit/after_commit/收到回执后OS kill 三边界重启，均无丢失/重复/部分写入；旧17ca07d真实服务建库再新服务升级，旧回执/不可变历史/未确认草稿保留。确认P95见下。 |

应用证据通过公开HTTP用例及真实SQLite；测试不直接操作数据库构造/断言账户事实。恢复启动真实Uvicorn、HTTP确认与查询，终止真实进程。浏览器为已安装Chrome154.0.8037.95，headless，API8022/页面5182、独立临时数据目录；基线/成交/资金用合成数据，不能证明真实券商获取或投资资格。

实施按纵向TDD：首次买入、部分卖出、费用追加、矛盾隔离、身份与逆行为、原精度/权限时点、实际进程/升级/性能各先写公共行为测试、观察缺失行为失败，再接入同一确认服务。首个浏览器失败缺少“同步实际成交”入口，接入后上述关键路径通过。精度使用 Decimal 80 位与分舍入，固定独立预期不由实现复制生成。

性能在真实HTTP→Uvicorn→SQLite FULL/WAL→回执JSON解析链测量；10次预热后100次 BUY_FILL，最近秩 ceil(.95n)：**P95 54.5614ms**、中位40.6255ms、最大218.4970ms（门槛2000ms）。结束账户111版、30证券持仓、142事件、SQLite36,659,200字节；独立临时档案，无附件/行情引用。设备Windows11 10.0.26200-SP0、AMD64 Family25 Model116 Stepping1 AuthenticAMD、Python3.13.12、SQLite3.50.4。全部样本、规模与环境：[performance.json](confirmation-performance.json)。该规模下通过，不外推更大档案。

可复现：backend执行 `$env:ROLL_EVIDENCE_DIR=(Resolve-Path '../.scratch/roll-p0/evidence/02').Path; ./.venv/Scripts/python.exe -m pytest -q`；frontend执行 `npm run build`，并以 `ROLL_BROWSER_CHANNEL=chrome,ROLL_TEST_API_PORT=8022,ROLL_TEST_WEB_PORT=5182` 执行 `npm run test:e2e`。锁版本由 uv.lock/package-lock.json记录。警告为 Starlette TestClient 的 httpx弃用提示，测试没有失败。

08/13的真实外部获取/模型任务尚未存在，组合验收 **pending actual 08/13 execution**；`scripts/account_confirmation_performance.py::measure_confirmations` 是具体隔离测试集成入口，要求在实际等待/超时期间保存同一采样与任务生命周期。09费用前损益与02费用后成本区分见 [成交契约](../../../../docs/fill-contract.md)，当前资金 PENDING_FACTS、技术 UNGRANTED。03/05继续核对/更正隔离事实，26执行实际动作关联；这些后续责任不冒充02已经完成。
