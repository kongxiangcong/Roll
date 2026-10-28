# 公司研究使用与恢复

当前交付为研究功能与局部真实验收；[联合矩阵](../../.scratch/roll-research-valuation/evidence/12/coverage.md)仍有未通过项，不能把PARTIAL或CURRENT_PRICING blocked显示成完整可用估值。最终review的自动估值编排修复尚未并入本检查点。

## 日常与独立报告

日常使用先在「持仓与关注」添加有限证券，再选择研究对象。没有账户确认也可以研究关注公司。查看关注理由、经营证据、固定条件下的价格/估值变化、下一验证事件、反证、资料核查与年龄。成功无新增只表示完成的来源范围未得新证据；失败/不支持/缺原件不是经营未变。当前公开新闻/财务适配范围仍有限，查看实际source receipt和scope，不凭研究按钮推定全市场采集。

「公司研报」输入公司名称或代码，核对解析主体、上市地/股类/币种，再选择截至时点、来源策略与固定快照。复用已归档材料的新任务仍可能调用模型；仅查看历史报告不调用模型。无权限/配置/来源时会保留缺口，任务状态和章节尝试不是事实审核结论。

查看报告质量缺口、原件引用、文件交付历史后下载Markdown/PDF。报告状态PARTIAL与文件状态COMPLETE各有含义：文件渲染成功不证明研究完整。新PDF交付只追加文件版本；新研究任务/新快照不改旧报告。报告中的同快照跟踪链接保留原core，持续更新需加入关注范围；只读跟踪不会自动启用采集。

条件估值按用途显示：BASELINE_RESEARCH可有明确日期和假设的条件参照，CURRENT_PRICING若缺最新经营/桥接证据则blocked。不要将过去取得的旧年报、当前构建假设当作历史PIT，不把情景权重或模型语气当上涨概率。

## 启动与当前验收库

普通完整服务沿用现有入口，明确数据目录和空闲端口；先Status核验，保留原服务receipt，不与其它部署共享数据目录启动第二worker：

```powershell
./scripts/start-roll.ps1 -Status -DataDirectory <absolute-data-directory> -ApiPort <api-port> -WebPort <web-port>
./scripts/start-roll.ps1 -DataDirectory <absolute-data-directory> -ApiPort <api-port> -WebPort <web-port>
```

该入口沿既有配置加载模型/来源。不是在本票新授权模型请求的指令；待运行队列和实际payload范围需匹配现有授权。首轮复核优先API-only和只读历史，不为浏览器预览加载凭据。

本次实际验收为显式当前backend/src PYTHONPATH，避免原venv editable加载旧worktree：

|库/进程|用途|实际入口/证据|
|---|---|---|
|`.scratch/rv12-real01`，API8032/web5212|真实共享报告、官方新增材料、网页新PARTIAL任务|evidence12/serve_api.py、serve_report_worker.py、api03-receipt/process-receipt/web-receipt|
|`.scratch/rv12-daily01`，API8033/原worker|两真实关注证券自然盘后观察，原公开source配置；无模型auth|serve_daily.py、serve_daily_worker.py、daily-configuration/daily-worker-receipt|
|`.scratch/rv12-restored01`|公开Backups隔离正常启动恢复样例|verify_restore.py、restore-receipt|

验收worker显式清除ROLL_CODEX/ROLL_DEEPSEEK配置、不读取.env：新事实需要模型时正常记录UNAVAILABLE，绝不擅自外发。两关注research_postclose已开启且news_refresh=true；其它三盘后类别关闭。不把旧source disabled、scope unsupported或ARCHIVES_ONLY记为真实公源完成。

当前自然周期0/2；最早候选10月28和29日15:05 Asia/Shanghai，实际线上当前交易日才调度。主机休眠/离线不补造过去日期；轮询worker健康不增加周期。后续按GET observation-updates各证券检查实际scheduled_checkpoint、started/finished、receipt、scope、check/model状态及error；一日同证券相同key不重复。未启用新平台automation。

## 备份、恢复、重启与接管

通过 `POST /api/runtime/backups` 创建备份，`GET /api/runtime/backups/{id}/export`保存bundle。恢复到全新空目录，用既有Backups.stage_restore和restore_at_start走正常启动验证；不要覆盖原库、手拷正在写的SQLite或改原件/报告hash。恢复后核公司/快照/计算/报告/交付及原件SHA，恢复不重新调用模型。evidence12/verify_restore.py是实际复现入口，目标目录已存在时主动拒绝覆盖；另选新目录。

重启前保存明确源路径、数据目录、角色、PID、StartTime ticks、CLI与监听端口。仅停止自身已逐项核验的进程，不能按端口名/所有python进程批量stop。venv launcher与实际listener/worker可能是父子两个PID，核各自身份。API重启后重读稳定公共对象与原件SHA；只读页面重载不等进程恢复。

本票实际API重启前后7稳定公共对象一致，源资料新增后15原件/2报告/2快照/6文件隔离恢复相等，见restart/restore receipts。原生产8010/5173以及07–11服务未动。

未来从实施worktree迁到integration时，要先把同一固定commit/入口部署在明确目录、保留配置/队列/收据并精确接管，不能让不同代码同时消费同一库。只有确认所有owned服务不再依赖实施路径后才能清理worktree。前端node_modules为指向原项目依赖的junction，只移除junction入口，不递归删除目标。实际数据目录、备份与稳定证据继续保留。
