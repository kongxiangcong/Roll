# 原登记基准的 METHOD 诊断

在保存费用诊断中创建、查询或重放 CASH、START_HOLD、MA5_MA20 原登记基准。只接受空初始持仓，沿用原现金、范围、费用、数量与风险约束；原 `shadow.simulate` 保持不变。START_HOLD 不自动退出，MA 仍在观察后第20会话退出，候选新 lot 则按实际入场后20会话退出，页面分别显示这些时点。

纯引擎使用可逆 METHOD_SLOT 编号及旧接口状态别名。这些不是实际交易日、真实完整行情或公司行动否定覆盖证明。保留整个声明跨度，缺会话、未知当前/前收盘和不一致参考价均列明；不补行情或裁掉热身。MA 没有运行前上下文，其完整原窗口比较不可准入，即使后段已有实际模拟成交也不输出全窗口超额收益。

所有控制仍显示描述性轨迹、成交、缺口与原机会拒绝原因。相对结果要求双方整个窗口可计算且控制执行支持可准入。共同风险匹配尚未建立，回撤差异不触发风险匹配超额判定；已观察候选绝对风险硬失败继续保留，否则 G4 INCONCLUSIVE。不得 PASS 或授予资格。

保存源费用 manifest/input、原前驱冻结、方法和代码依赖；显式重放在30秒、8MiB输出上限的禁网子进程中执行。最多200声明会话。读取校验嵌套原件，后来帧不改变旧结果。账户、原冻结、模型与拟合/SEALED预算不变。

API：`POST/GET /api/research/successor-cost-stresses/{id}/registered-controls`、`GET /api/research/successor-registered-controls/{id}`、`POST /api/research/successor-registered-controls/{id}/replay`。
