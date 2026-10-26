# 2026-10-15 实施交接

用户 `$implement-spec D:/dsh-proj/Roll/.scratch/roll-capability-expansion` 是本轮启动授权。按任务计划单票顺序执行；保留原 P0 责任，不关闭或改写原 P0 票。

## 固定基线

- HEAD：`fe5d01c7d7af7da9a74354cbaf0ce8455450971c`；原分支 `codex/roll-p0-integration`，本轮集成分支 `codex/roll-capability-expansion`。
- 交接会话 `01a13aff-3428-7062-9c7d-7fb90bd7d79d` 最新 turn completed、状态 idle；同仓库其他最近实施会话 idle/notLoaded。未发送跨会话消息。
- 原有修改：9 个 tracked 文件及新增 SSE 日线模块、测试、运行脚本、研究资料与运行证据。完整 Git 状态见 [清单](evidence/handoff/preexisting-status.txt)，15 个受保护文件当前 SHA256 见 [保护清单](evidence/handoff/protected-files.json)。不把旧工作一并提交。
- Python 依赖以 `backend/pyproject.toml`/`uv.lock` 为准，实际 Python 3.13 环境；FastAPI、SQLite、内容寻址原件及既有 worker 保留。
- 最新产品合并 `a020be4225beb8d88f62feee7bad2a37862b4922`，随后文档接受 `fe5d01c7…`。未提交日线差量的固定验收：47 PASS/356.18s，含真实 OS 恢复；本轮不把这项旧结果称为新跑整套回归。
- 模型代码指纹 `9c9e8b701dd4db90486654b7d44781dc317cf52fa37574214d6d2b7989e9e3db`，实际校准状态 FITTED_UNVALIDATED，既有 G4/G5 FAIL 必须保留，正式能力 NOT_GRANTED。

## 运行及真实证据

只读运行预检在默认沙箱报 WinError10013；权限复核后 API8010 报 WinError10061，8010/5173 无监听。不能继承“服务当前运行”的旧结论。未停止、重启或迁移用户服务；未打开实际 SQLite。真实运行状态不能通过离线文档升级。

既有 PIT 数据目录与试用 API 数据目录分离。2026-10-14 SSE 日线唯一实际收据 `edebcb94-0467-418c-b7fa-5428a23a7072`、固定包 `0c169838-f82e-41f9-88d8-f5436d2c6d07`、1149B 原件 SHA256 `9537daa946f48cf46db0bac1ebd4db94a6d6e33e06e3e3b3877c6320fad1e3ff`、备份 `4679d60b-304b-4d1e-af15-6104b09e6898` COMPLETE。仅继承已归档证据，不复用已关闭的单日请求预算。

来源： [真实盘后验收](../roll-p0/evidence/real-forward-2026-10-14/acceptance.md)、[实际摘要](../real-forward-20261014/actual-summary.json)、[政策/费用/行动验收](../roll-p0/evidence/continuation-2026-10-14/acceptance.md)。原件、来源回执与 METHOD 工程样本分别记录。

## 唯一责任与差量

| 新票 | 旧责任 | 可继承的有限切片 | 剩余范围及本轮责任 |
| --- | --- | --- | --- |
| 02 | P0-30 | 日期日线 raw-first、Decimal/文档单位、API/worker once job、固定包离线重放 | 完整 session/RAW 用途及修订依据仍不足；补现有页面的日线与精确缺口查询，不重建采集器 |
| 03 | P0-30 | 指定日期停牌、commonSoa 区间、公司客户端契约；空名单不推出正常 | 全状态枚举/生效时刻/完整否定覆盖需官方依据；保存旧预算 CLOSED，任何新查证先登记固定计划 |
| 04 | P0-30 | 历史候选、14 份已知公告/旧义务、ACTION_WINDOW_SUCCESSOR 固定关联 | 当前完整公告区间、修订/取消/履行链尚缺，不把计划付款视为履行或到账 |
| 05 | P0-20/21 | v1 完整冻结及 G1—G7，v2 研究政策/连续 METHOD/批次迁移 | v2 当前明确 complete_experiment_frozen=false；完整经济/统计协议、验证消费者是本票差量；不借 v1 授权 |
| 06 | P0-25 | 当前动作五状态、联合预算、券商费用版本、执行意向 | v2 生产派发、冻结的有效期/报价时效尚缺；不代填真实资金/费率 |
| 07 | P0-27 | 暂停峰值/latch、原因拒绝、三范围、恢复锁与事实同步 | LOSS 正向恢复未登记规则/凭证；先登记后继规则，不从反弹推出恢复 |
| 08 | P0-32 | 唯一归档、重复起点/三自然月截止、只读部署预检 | 首次真实预测未保存；完整输入、冻结/准入及同部署一致性未满足，服务当前不可访问；不另起第二起点 |

## 启动前沿

01交接有限兼容核验后可解除本地依赖。02—05、07、09、19、20可分别启动；06待05工程消费者，08待02—05真实准入，10/12/14待09，21待20；其余依照原依赖图。真实阻塞不拦独立观察或数值参照工程。现有停止预算、失败及实际资格不变。

公开测试边界沿用已确认的 FastAPI 请求→隔离 SQLite/原件→查询/重启。浏览器与真实来源另验。后续每票只在必需条件全部成立时 complete。
