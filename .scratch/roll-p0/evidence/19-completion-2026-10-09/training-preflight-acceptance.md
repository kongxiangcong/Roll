# Ticket 19：只读训练准备检查实施验收

本切片完成公开元数据预检，相关后端四模块 **21 passed / 0 failed，117.73 秒**。它不完成真实来源准入、实际训练/校准、基线或模型冻结，票19实际研究判据仍不足；本切片不更新票状态、总tracker或后续票依赖。

## 范围与实现

- 基于集成 `81abcb961dd2b628b7466b8ecb08eb249c992a26`，工作树 `C:\Users\72449\.codex\worktrees\ticket19-training-preflight\Roll`，分支 `codex/ticket19-training-preflight`。
- 新增 `GET /api/research/protocols/{id}/training-preflight`，purpose默认RESEARCH，同一Literal值域允许METHOD_VALIDATION；未知协议404、未知用途422。
- 只读取协议/数据登记与全family attempt manifest。返回DEV/CAL窗口元数据、具体来源/PIT/状态/权益/历史规则/窗口/真实训练代码缺口，及PRIMARY_FIT+G5_NEIGHBOR五次、CALIBRATION一次的已用/剩余数量。失败、中止、中断、成功与运行中都计数，后继和兄弟共享。
- `assessment=METADATA_ONLY`、`ready_to_fit=false`，原件完整性、训练输入、实际标签与支持均NOT_CHECKED。METHOD不提升实际研究资格；SEALED独立性/G3/G7不列作19模型冻结前提。数量不是预约，不能证明宿主外无未登记尝试。
- 预检只含既存时刻/身份，重复GET不生成now/nonce、不写事件、attempt、模型或工件。未调用来源或网络、未读取原件/Parquet/DEV或CAL标签/SEALED、未拟合或校准；账户、能力、前向起点保持原值。
- 实现独立于模型算法，`models.py` 未改变。实施前后Gitblob均为 `672aee8ab755d092627f9c7c3a08ff2116ffeda4`，新只读功能不会因修改模型文件SHA而使旧方法模型/预测失去算法重放资格。旧POST模型的先计PRIMARY_FIT、失败计费、事务重查家族预算行为保留。

## 应用与持久化验收

测试seam为已经确认的FastAPI应用与持久化，未向用户重复索要统计设置；tdd的tests.md/mocking.md、仓库领域/ADR和本地任务约束均已阅读。

| 切片 | 红阶段 | 最终绿阶段 | 已证行为 |
| --- | --- | --- | --- |
| 两旧失败与家族 | red-01：缺路由404 | green-01：1 passed | 旧失败保留，后继/兄弟相同2用/3剩余，重复GET及已结束家族重启公开状态完全相同 |
| 五次/一次预算边界 | red-02：缺明确预算用尽阻塞 | green-02：1 passed | PRIMARY/G5均计数，FAILED/ABORTED/SUCCEEDED/INTERRUPTED保留，五次与一次用尽；404/422不写状态 |
| 宿主覆盖BLOCKED | red-03：缺来源元数据 | green-03-final：1 passed | 固定外部响应登记仍METHOD_CASE/BLOCKED、DEV/CAL未预登记；损坏该测试原件/Parquet不影响元数据GET，来源调用数不变、零新模型/attempt |
| 旧无宿主身份尝试 | red-04：KeyError host_owner | green-04：1 passed | 隔离旧持久化fixture可以预检，中断仍占一次，未补写或改写旧记录 |

第三片两次中间失败均保留：`green-03.txt` 原测试误期待固定响应为非METHOD，已改为诚实的METHOD_CASE断言；`green-03-corrected.txt` 在构造采集fixture时遭Windows过长临时路径FileNotFoundError，改用工作树内更短且已验证路径后通过。它们不是最终绿阶段，也未覆盖原输出。

最终四模块为 `test_training_preflight`（4）、`test_transparent_models`（4）、`test_research_protocol`（10）、`test_research_acquisition_import`（3）。原模型工件、预测/离线重放、失败预算、协议/来源登记相关用例通过。没有扩展跑完整412套件，也没有前端/浏览器或实际数据研究结果的新增验收声明。

所有临时路径在运行前用绝对路径核验属于本工作树，使用根 `D:\dsh-proj\Roll\backend\.venv\Scripts\python.exe`，显式PYTHONPATH指向工作树backend/src。pytest仅使用隔离测试数据库及明确工程输入；没有启动服务、读取实际运行DB、改账户、调用Fuyao/BaoStock或推送。

## 原始输出、指纹及清理保全

- 原始红/绿/相关输出共11文件均保留在本证据目录，相关终态见 [training-preflight-related-backend.txt](training-preflight-related-backend.txt)。本目录已有`.gitattributes`规则保留JSON/stdout原字节。
- [training-preflight-implementation-verification.json](training-preflight-implementation-verification.json) 保存算法Gitblob、四个实施文件规范LF SHA、各stdout长度/SHA及隔离fixture的目录清单、数量/长度和规范文件清单指纹。来源资格/实际标签评估与实际研究拟合均false。
- 工作树 `.scratch/t19-final*` 隔离工程fixture共 **1,228文件 / 84,947,992字节**，目录清单见同一JSON的`ignored_fixture_preservation`。它们包含可重建工程原件、Parquet、SQLite及方法运行记录，不含实际研究原件，不能用作实际市场研究证据，也不是托管归档前必须额外保全的材料。必要源码、应用测试、11份raw stdout、验收和指纹证据均提交；本工作树内fixture尚未清理，主进程可自行选择是否另保留。
- 未删除任何原件、fixture或工作树；未修改实际数据库、旧失败、正式版本、资格、账户或前向起点。后续由主进程完成只读实际元数据核验、集成审查和必要证据保全后托管归档。

真实来源仍需可验证历史版本、完整状态/权益与历史规则处理和预登记窗口；真实训练路径仍未实现。本切片只避免未来查看缺口误占拟合额度，不解除这些门禁，也不使ticket20解锁。
