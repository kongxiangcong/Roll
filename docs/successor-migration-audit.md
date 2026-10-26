# 原迁移lot与登记范围审计

从同一保存费用前缀读取原初始持仓、冻结迁移绑定、BUY事件及各帧lot状态。核对位置/证券/数量/原期限和迁移身份，新lot首帧位置身份绑定BUY订单，后续位置和lot身份不改、剩余数量不回涨，新lot期限保持实际入场加原登记期限。

原lot到期但不可卖时保留原截止与逐次阻塞依据，不把期限延长或挪给新lot；迁移生效位置与原到期安排分开显示。原初始持仓为空时迁移不适用，仍核对新lot和范围。范围登记及已观察证券不证明其他证券、市场、时期或真实迁移能力，scope_transfer_evidence始终NOT_PROVEN。

一致/不一致仅为METHOD工程审计；G5 INCONCLUSIVE，不产生统计FAIL/PASS或资格。最多200帧/声明跨度、8MiB输入，只读原件，不重跑模拟器或改变账本。来源/方法/代码指纹保存，嵌套原件损坏拒绝，后来帧不改变旧重放。

API：`POST/GET /api/research/successor-cost-stresses/{id}/migration-audit`、`GET /api/research/successor-migration-audits/{id}`、`POST /api/research/successor-migration-audits/{id}/replay`。
