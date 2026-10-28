# 真实盘后采集、预测与启运核对

2026-10-14。本说明区分来源原件归档、预测归档、真实验证计时。

## 当前实际状态

持续真实采集使用 `.roll-data/pit`。试用 API8010 使用 `%LOCALAPPDATA%\Roll`。
两者是不同的状态库，不能把一个库中的采集行数当成另一个部署已具备冻结候选。
2026-10-14只读检查显示试用部署有两份研究协议，但无冻结模型、完整实验冻结或采集计划。
既有重建模型与其隔离验证材料仍按原登记保存，没有本轮重新拟合或移入试用账户。

真实 `forward_started_at` 只由冻结模型的首个合法预测与 SQLite 提交共同生成。
来源原件、采集计划、备份、METHOD 样例及部署时间都不能开始验证计时。
缺失日期不补预测；检查点之后才登记的计划不追认当天样本。

## 指定交易日日线来源

新增 `sse-dated-daily-statistic`，默认关闭；在来源配置中显式启用后使用。
只适配 SSE:600362，固定官方 commonQuery 日线统计及已保存的官方单位文档。
客户端不能指定过去日期、就绪状态或完成覆盖。Host 仅在已知交易日15:05以后取当天资料。
每个计划/Host交易日最多一次 HTTP，15秒总超时、1MiB解码上限，无重试、重定向或替代端点。

现有独立 worker 与 `scripts/collect_prospective.py` 共用同一 SQLite once job。
关闭页面不关闭 worker；关闭程序不会自动补预测或延长期限。
原件后、提交前进程中断保留 `INTERRUPTED_NO_RETRY`，重启不会再消费该日预算。
失败、空结果、错日期和前缀响应保留真实原件和缺口，不能推定无成交或普通交易状态。

成功回执提供精确日期、量价、单位文档和实际接收/可消费时间。
它仍是 `DAILY_STATISTIC_ASSESSMENT`；完整会话、状态、公司行动及旧义务责任分别保留。
`DATED_DAILY_SUCCESSOR` 显式绑定原盘后包和选定回执 IDs，离线重放不联网、不重选后来的版本。
原包、旧来源、模型冻结及已有预测不自动升级。该切片不产生真实预测或资格。

## 操作入口

- `POST /api/research/collections/{plan_id}/sse-daily/check`：已显式启用的来源，执行或复用当天有界任务。
- `GET /api/research/collections/{plan_id}/sse-daily-receipts`：检查原件、单位文档、请求计划及规范化绑定。
- `POST /api/research/collections/{plan_id}/sse-daily-packets`：指定 `predecessor_packet_id`、`receipt_ids` 与依据。
- `GET /api/research/collections/{plan_id}/sse-daily-packets/{packet_id}`：查询固定包并先核验重放。
- `POST /api/research/post-close-packets/{packet_id}/replay`：现有统一重放入口。

启运前从正在运行的部署只读核对：

```powershell
backend/.venv/Scripts/python.exe scripts/forward_readiness.py --output .scratch/forward-preflight.json
```

报告包含部署中真实存在的模型/完整冻结、采集输入、worker、备份与下一可能检查点。
该命令只有本机 GET，不创建计划、不读取 SEALED、不派发预测，也不改变资格。
未执行完整准入时报告不能充当启运授权；已有 FAIL 保留并要求按协议处理。

当前缺口关闭后，仍由原 `complete-freezes/{freeze_id}/forward` 登记及共同检查用例执行首次预测。
真实启运还需完整输入、冻结协议/政策/基线、部署与备份核对，并在检查点前预登记。
源的日线统计返回成功不会解除这些条件。

本轮没有重启试用服务；新 worker 源码随后续正常启动加载。PIT 持续采集脚本下次运行使用新入口。
真实取数、状态保全及测试证据见 `.scratch/real-forward-20261014/`；票级结果见
`.scratch/roll-p0/evidence/real-forward-2026-10-14/acceptance.md`。
