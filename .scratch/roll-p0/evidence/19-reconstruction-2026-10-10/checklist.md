# Ticket 19 单票闭环

本轮依据 ADR 0004；旧框架与失败记录保留。只完成19，不拆票、不实施后续票。

| 原验收 | 实施入口 | 必需输入 | 本轮证据 |
|---|---|---|---|
| 一个透明候选/基线/全部尝试 | models / registry | REAL_ACQUISITION RAW、单机会标签 | [真实模型及比较](v4/real-model.json)；旧两失败+本轮单PRIMARY/CAL见[manifest](v4/restart-replay.json) |
| 时间隔离、跨窗和依赖 | datasets / models / execution | 连续日历、DEV/CAL、20日成熟时间 | [逐日质量/支持/排除](v4/quality-support-report.json)：DEV1148/CAL444；重叠依赖、跨窗保留未定 |
| 不读SEALED、模型/CAL冻结 | registry / models | 全家族预算、新特征协议、内容归档 | [真实模型freeze_manifest引用](v4/real-model.json)：FROZEN/FITTED_UNVALIDATED；SEALED未分配，审计未访问 |
| ForecastBundle | models API | 工件、获准CAL观察日 | [真实历史预测](v4/real-forecast.json)：实际消费时点与历史假设分列，非前向发布 |
| 支持/可靠性/必要基线 | research / models 页面 | DEV训练内与CAL拟合内描述、逐机会CASH/持有/MA | [实际Chrome最终1通过](browser-command-final.txt)、[页面](research-view.png)；独立有效性未确认 |
| 正式版本不变 | 隔离目录/保护摘要 | 原账户、旧研究、预算、权限 | [保全核验](protection-verification.json)：20源保护表、154原件/副本、旧记录、用户非本轮修改保持 |
| 持久化/重启/离线重放 | FastAPI / SQLite / archive | 原输入、原算法SHA | [禁止外网guard](v4/offline-network-guard.json)、[两个实际HTTP PID](v4/http-restart-replay.json)、[原输入一致重放](v4/restart-replay.json) |

盘点及已知拒绝不登记统计拟合。新用途/特征先登记，再计算；旧预算失败不改。窗口按覆盖和日历选取，不按候选收益挑选。

边界方法测试13通过；最终稳定后端460/52模块通过，源码/测试/引用JSON指纹不变；TypeScript/Vite与实际Chrome通过。详见[完整验收与本轮命令](acceptance.md)。只完成19，校准有效性未确认、完整实验未冻结、正式能力未授权；依赖已具备，后续可另行实施。
