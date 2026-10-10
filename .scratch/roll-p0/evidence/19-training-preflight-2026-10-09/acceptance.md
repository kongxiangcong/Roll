# Ticket 19：只读训练预检与实际家族预算

日期：2026-10-09。此切片补齐不消耗拟合额度的数据缺口检查；不是实际模型、校准器或 ticket 19 的完整验收。真实来源准入、历史版本、状态/权益处理、窗口登记、真实训练和必要基线仍由实施代理继续处理。

## 实际已核验事项

[初始主机回执](actual-family-before.json)通过既有 `http://127.0.0.1:8010` 的公开 `attempt-manifest` 查询旧江西铜业家族，覆盖两个协议及两次不同的失败 PRIMARY_FIT。当前主机登记：PRIMARY_FIT/G5_NEIGHBOR 已用 2/5，剩余 3；CALIBRATION 已用 0/1，剩余 1。失败次数保留，没有更改归类、重置预算或新开根。这个快照不是额度预约，也不能证明不存在未登记的外部尝试；真正开始尝试仍由现有 SQLite 事务重新检查。

[初次实际元数据诊断](actual-preflight-initial.json)使用当时工作树的新函数和仅允许协议、所引用数据登记、attempt-manifest 三种 GET 的适配器。来源登记为 REAL_ACQUISITION，DEV/CAL 都为 NOT_PREREGISTERED。重复诊断相同，家族 manifest 不变；无新来源采集、标签读取或计算、模型/校准拟合、封存读取。这不是“当前 8010 已部署新预检路由”的证明，也不更新、重启现有用户主机。

## 实现及边界

- 新 `GET /api/research/protocols/{id}/training-preflight` 仅读取登记元数据，列出来源/历史 PIT/窗口/代码缺口及全 family 尝试预算。
- PRIMARY_FIT/G5_NEIGHBOR 五次及 CALIBRATION 一次的失败、中止、中断、兄弟和后继均计入；未知协议 404，未知 purpose 422。
- 不读取分片原件、DEV/CAL 标签或 SEALED，不保存新 attempt/event/model/forecast，不调用取数、拟合或校准。不产生来源资格或预算预约。
- 原件完整性、实际标签及支持明确 NOT_CHECKED；真实训练代码未接通仍明确报告。METHOD 不提升真实研究资格。
- SEALED 独立性属于后续确认性检验，不作为 ticket 19 模型冻结的前提；预检报告不解除后续门禁。
- 代码放独立 `training_preflight.py`，保留 `models.py`、`registry.py`、`execution.py` 原字节和旧算法指纹。旧 POST `/models` 的失败计数、冻结拒绝及资格边界保持。

## 最终集成与实际元数据检查

实现提交 `1baba13dfc0f9b3871833722ccc3a2a07d489e5c` 已合入集成 `f953d71c5d74c740a14fdeb389b52ad110a21709`。四模块 21 passed/0 failed，117.73 秒，含四个新预检应用用例及原透明模型、协议、来源登记回归；[实施验收](../19-completion-2026-10-09/training-preflight-acceptance.md)保留红/绿阶段与中间失败。没有重复完整 412 套件或新增前端/浏览器结果声明。

[最终实际元数据诊断](actual-preflight-final.json)显式使用集成代码及同一只读 HTTP 元数据适配器。代码规范 LF SHA 为 `7dfc584cff45ce54f85ca9b0f1f92d1610a3ca6401037b915ebef0d473c1dbb6`；来源是真实旧采集登记，重复报告一致、manifest 不变，实际家族仍两次 FAILED / 三次主拟合剩余 / 一次校准剩余。它报告七个具体缺口：历史版本、完整权益处理、完整执行状态、历史规则验证、窗口未预登记、真实训练路径未实现、实际标签/支持未检查。未将封存独立性添加为本票模型冻结前提，也未解除后续确认性控制。

与本轮开始的原字节核对，`models.py`、`registry.py`、`execution.py` 均未改变。仅查询旧采集的登记及尝试元数据，没有依赖 Fuyao/BaoStock 取新数据，没有打开实际分片、原始样本、模型/执行结果或账户材料。既有 8010 用户服务未重启、未宣称新路由已部署到该进程。

[工作树保全](worktree-preservation.json)复制并核对 11 个隔离工程目录的 1,228 文件 / 84,947,992 字节，原件与目标 SHA/长度差异 0；逐目录 metadata 摘要与实施者的冻结清单一致。初次普通沙箱在明确的合成凭据 fixture 上 PermissionError；查测试源码确认 `METHOD_CASE_ONLY`，正确身份继续同一范围完成，未访问真实凭据。这些文件仅是可重建工程测试资料，不能代替真实市场数据。

独立 Standards/Spec 审查及合并后关键应用验证见[合并验收](merge-acceptance.md)。本文件不得作为已经训练、校准、冻结或完成 19 的证据；19 保持 partial/needs-info，20 尚未解锁。资料取证、真实训练、校准和模型冻结的开发及实验继续由代理负责，不要求用户承担技术验收。

合并后关键用例 5 passed/0 failed，38.97 秒；与实施者21项是两个检查记录，不合计为26个独立用例。Standards/Spec各0发现，源码合并f953d71，独立合并验收提交36ef3b0。没有源码在上述检查之后改变。

[托管归档确认](worktree-cleanup.json)及源路径不存在均核验。归档后[最终核对](final-verification.json)为目标副本单独复核：1,228文件SHA/长度差异0，模型/协议/执行原代码字节不变，实际家族尝试元数据与本轮开始一致。它不再宣称归档后能重新比对已移除源。校验器首轮漏列同一家族前序协议的合法只读manifest路径，原[失败](final-verification-first-failure.txt)保留；白名单补入已知family ID的同一GET后通过，没有改变实际回执、来源、预算或生产代码。仅本地提交，未推送。
