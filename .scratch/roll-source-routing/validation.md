# 来源路由验证

日期：2026-10-29（Asia/Shanghai）。本轮没有提交、推送或修改真实账户事实。

## 实际来源

独立目录 `live-20261029/`，账户版本仍为0，只有为有界查询建立的单证券关注记录。

- `receipt.json`：扶摇日线/新浪报价成功；妙想财务参考成功；东财财务结构数据2条成功，公告原件详情请求断连，所以财务取证仍为PARTIAL。妙想参考未被当作披露原件或自动财务事实。
- `receipt-market.json`：扶摇RAW与当前前复权各8条（2026-10-19至2026-10-28），新浪报价1条。东财公开日线请求断连后，比较路径继续取得BaoStock RAW；不是把接口失败藏成缺数据。
- `recomparison.json`：对上述实际归档做离线字段比较，8日的开/高/低/收、股数和成交额均在记录容差内一致；新浪/腾讯时点不同，1组NOT_COMPARABLE。独立生产依据仍为UNPROVEN，不宣称严格历史PIT。
- 三次实际取证的原件/Parquet回放网络调用均为0。实际额度耗尽没有人为触发；相应错误由模拟供应商测试验证，不宣称账号额度已测完。

## 工程验证

- 前端两次构建通过，保留既有大bundle提示；`git diff --check`通过。
- 路由/配置/共享材料组合回归曾23 passed；新闻结构及配置组合12 passed；增加按capability冷却及畸形MCP信封后路由13 passed。最终组合结果见 `final-routing-tests.xml`。
- 最终路由与配置组合：17 passed，95.10秒；JUnit为 `final-routing-tests.xml`。覆盖额度、业务限流、显式源、网络/字节/取消预算、凭据缺失、字段比较、按capability权限冷却、畸形信封、研究参考隔离与共享材料。
- 原有来源/worker/报告回归：87 passed，648.72秒。范围：`test_market_evidence.py`、`test_source_resolution.py`、`test_fuyao_evidence.py`、`test_assistance.py`、`test_observation_updates.py`、`test_report_pipeline.py`。共享材料另有23项组合回归通过（其中12项共享材料用例）。没有用这些结果宣称全库验收。
- 本机真实API已读取OFFICIAL_FIRST，API/worker/网页确认RUNNING；无凭据健康收据为 `runtime-status.json`。

环境测试已迁移到配置加载、进程优先级和数据供应商凭据隔离，不再调用退出当前验收范围的DeepSeek入口。该迁移中发现并修复测试自身的环境恢复泄漏，后续共享材料回归已通过。Windows沙箱的临时目录ACL/socketpair阻塞由独立仓库临时目录和授权测试进程解决，不记作数据源回归。

## 仍有边界

这证明有限证券、日期及工程切换，不是全部股票、capability、新闻原文、财务科目或历史版本资格。既有前向CNEquity/AKShare策略、发行人原件、官方日历/状态保留；宏观/港美股未迁为默认公司采集。没有做整套浏览器验收或全库测试。正式能力未因换源而放开。
