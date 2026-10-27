# 11 命令与实际结果

所有Python命令均显式PYTHONPATH=rv-ticket11/backend/src，解释器D:/dsh-proj/Roll/backend/.venv/Scripts/python.exe，pytest basetemp为独立原repo .scratch/rv11-*。无模型/真实来源请求/拟合。测试公共边界已经用户确认，本票未重新请求确认。

1. red01：新公开features模块不存在，1failed15.56s。green01首次规范archive漏schema_version，1failed10.52s；只修档案body，green01b1passed9.24s。
2. red02：迟到修订/同季度独立支持的coverage方法缺失，1failed11.11s。green02：1passed10.16s；旧cutoff/严格历史用途都缺失，当前修订1，重复同季报2观察只1独立单位、0成熟样本。
3. red03：blocked审核误作unavailable，1failed14.11s。green03：1passed12.10s；原受控review/quote/version绑定，blocked gap null，概率和scenario_weight字段拒绝。
4. red04沙箱TestClient挂起。仅通过CIM核精确PID39704/18576和rv11-red04命令，停止这两个自身进程并留red04-owned-hang.json；未批量kill或改产品。相同公开HTTP测试正常权限red04b404，1failed9.62s；实现API/不可变补充协议后green04为1passed8.47s。
5. red05：重算档案与record SHA后错snapshot未被backup拒绝，1failed20.10s。增加原快照/core/ref/缺失/协议档案关系验证后green05为1passed15.17s，隔离恢复同对象。
6. red06：4并发相同key创建4个结果，1failed10.86s。交易锁内二次幂等核查后green06为1passed9.68s。
7. red07/green07初始夹具漏next_validation_event.date_fact_version_ids，candidate按原规范被拒，None不是时区产品红灯；记录保留。补真实原引用后red07b本地今日被UTC算作1天，1failed11.18s。仅按Shanghai日期修复，green07b1passed8.66s；未知披露年龄仍null。
8. 最终回归命令：

```powershell
python -m pytest backend/tests/company_research/test_research_features.py backend/tests/company_research/test_analysis_snapshots.py::test_frozen_input_publishes_one_immutable_snapshot_for_both_consumers backend/tests/company_research/test_changes.py::test_backup_refuses_rehashed_context_quote_that_differs_from_its_source_fact backend/tests/company_research/test_report_deliveries.py::test_backup_restores_delivery_bytes_and_rejects_rehashed_wrong_core backend/tests/application/test_feature_protocol.py::test_later_financial_revision_cannot_backfill_old_snapshot_or_cutoff -q --basetemp=D:/dsh-proj/Roll/.scratch/rv11-regression08
```

regression08：11passed92.22s。没有重跑宽suite或无关前端检查。首次命令搜索使用PowerShell不支持的brace语法报ParserError、两次猜测旧测试文件名不存在；改为rg发现正确文件，均为工具定位错误，不是产品失败。

## 真实复现入口

prepare_real.py通过Backups从rv10-real01创建全新rv11-real01；目标存在即拒绝，不覆盖旧目录。serve_api.py显式当前module和API-only8031，不加载.env，不启worker/model。初始api-receipt留launcher3060；仅时区/资料年龄修复后按CIM脚本与启动ticks精确停止自身wrapper/listener，保存api-stop01-receipt并改api02-receipt。最终launcher51196/listener23712，不涉及其他端口。

verify_real.py为第一真实版本，verify_real02.py为最终版：本地httpx trust_env=False，公开GET保护对象、POST三用途导出/协议/coverage、概率extra422、重复幂等、原snapshot/report/delivery不变；公开Backups导出后全新stage_restore并读原档案。real01/restore01与real02/restore02均保留。真实02结果见real02-receipt.json；纯本地恢复不调模型，不读取auth或SEALED。

应用源码与稳定证据均按票范围暂存；外部store日志持续增长，不追踪live日志；不可变源码/工件字节核对结果另存staged-byte-proof.json。所有原失败记录保留，未用METHOD冒充真实事件或概率效果。
