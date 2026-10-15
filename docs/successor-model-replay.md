# 原CAL模型预测的独立执行回放

中心绑定下 POST/GET `/api/research/successor-primary-center-bindings/{id}/model-execution-replay`；GET 和 POST replay `/api/research/successor-model-execution-replays/{id}`。

仅接受已核对中心绑定的 METHOD 模型及显式空初始持仓。使用原 v1 已保存完整 CAL 输入日历和同冻结模型的校准后预测，不生成新预测/拟合、不读 SEALED。缺少完整日历或非空原持仓时拒绝，不假定清仓或平移原迁移期限。

全部原日期逐一映射到 starting_session 后的连续 METHOD 会话；上下文仅用于首日 reference close，不进入回放窗口。RAW/SHARE/原状态与行动 METHOD 证据通过适配，缺失或无效输入保持 UNKNOWN。原小数价格及概率表示保留，不为了旧公开命令的两位金额/十二位概率约束静默舍入。这里是私有、已归档的执行输入契约，不伪造旧公开 shadow 帧。每条概率以原日期、模型哈希及预测阶段匹配；无预测日期保持空，不延用或拼接标签机会。

冻结现金、政策、费用、规则及新lot入场加20期限由原引擎消费。回放逐日得到曲线、成交、未成交、保留仓位/挂单和缺口。观察到的绝对硬风险FAIL保留，其余INCONCLUSIVE；校准拟合窗口重用不构成独立验证或G5通过。原人工前缀、冻结及真实账户保持不变。

方法/来源分别归档，200会话、8MiB输入输出、30秒隔离worker，禁网络；取消/超时终止worker。重启后用保存输入离线重放，不依赖当前可变shadow最新版本。完整冻结、真实输入准入及真实起点均未授予。
