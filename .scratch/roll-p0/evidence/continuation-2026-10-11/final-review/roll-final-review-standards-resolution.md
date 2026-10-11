# Standards affected-hunk resolution review

固定范围：`80fbcc23c8440e7210221144c020d315b9784773...bbb84a57f624dec9351b32373fd9d10e1447eed3`。产品修改来自 `e75c14e`；保留原 `roll-final-review-standards.md`，本次只复查 10 个生产文件的新增/受影响 hunk，没有重新开展全范围审查。

**文档标准：0 项新增可操作违例。**

- `decisions/capabilities.py:25` 的 `current_presentation` 仅投影已由 Host 核验的范围、动作、期限与实际/METHOD状态；`app.py:1232`、`today.tsx:18`、`settings.tsx:32` 消费该结果，没有增加前端资格判定。符合 project-layout.md“HTTP 和 worker 调用同一应用用例；React 展示服务端结果”。
- `decisions/intents.py:64–125` 保持 PrepareIntent 命令，独立保存首次 prepare 回执；快速读取后在 BEGIN IMMEDIATE 内复核幂等键，新意向、原回执与事件一次提交。旧记录缺回执明确返回 `LEGACY_PREPARE_RECEIPT_UNAVAILABLE`，没有伪造或回填旧承诺。符合受控原子写入、幂等和回执可靠持久化约束。
- `research/reports.py:92` 将缺少的 proposal 费用保留为 null/UNKNOWN，没有补零、重算金融政策或覆盖旧决策；符合 project-layout.md“未知异常/缺失不折算为成功或零值”和 ADR 0004 原始来源/版本保留。
- `technical_review.py:215` 与 `app.py:674` 只查询并校验已有材料；`capability-panel.tsx:14–36` 从已保存材料/审阅中选择，Host 继续最终准入；`settings.tsx:32` 默认折叠维护面板。未新增通用框架、权限写工具或额外真实审阅。

**12 项启发式 smells：0 项新增可操作问题。** 一个具体纯投影和一个现有材料查询均有当前调用者；幂等双检查分别承担快速找回与事务内竞争保护。仓库的具体模块、必要门禁规则优先，无需泛化抽象。

局限：仅静态只读复查。未运行测试、HTTP、provider、数据库或 SEALED；没有将 owner 测试当独立验收，也不据此补全金融规则、真实资格或生产 partial 状态。
