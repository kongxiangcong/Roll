# Ticket 21：自动验证与门槛证据验收

日期：2026-10-11。分支 `codex/roll-p0-ticket21`；FastAPI、真实 SQLite/归档与 Chrome 为工程边界。当前交付的是冻结候选的验证能力及具体缺口，所有自动结果均为初步结论、待独立技术审阅、`NOT_GRANTED`。

## 实现与逐项结果

| 验收范围 | 输入、预期与实际 |
|---|---|
| AT-38 / 确认性入口 | 仅完整冻结指纹匹配后才能诊断；模型/CAL/归档损坏拒绝。CONFIRMATORY 从宿主登记、用途、暴露、统计假设、家族尝试、真实前向与独立最终材料推导准入，当前材料在任何 SEALED 内容消费前返回409，保存拒绝审计。客户端不能提交 PASS。修改方法后旧验证重放409；旧结果保留 |
| AT-52 / 清单、状态与追溯 | 输入归档、输出清单、协议/候选/方法/结果指纹、目标及25bp改善、基线、窗口、尝试、依赖、停止、费用/执行、范围、截止与未决事项保存。实验、验证、审阅、能力分别呈现。G2只把冻结轨迹重放子检查记PASS，整项因未绑定完整部署工程证据仍INCONCLUSIVE |
| G4连续策略 | 使用20同一连续执行引擎及CASH、START_HOLD、MA5_MA20约束基线；NAV改善、尾部/回撤、资金占用、持有期、盈亏、覆盖与20/40交易日相关区间分别计算。重复逻辑机会按“任一BUY”计一次入选，保留所有原始拒绝；已观察全拒绝覆盖硬FAIL，无机会输入不足INCONCLUSIVE。分段成交仅计本段事件，已实现收益扣除段前累积基准 |
| 概率有效性 | 成熟归档机会：Brier/对数损失与DEV基准、固定可靠性分箱、AUC、入选子集、有效支持及相关区间。缺失日期保留日历空槽，同日联合重采样，不压缩日历；CAL复用只能描述，不能取得独立校准PASS |
| G5必需分项 | 三时间段、冻结费用压力、NEXT_OPEN/NEXT_CLOSE/ONE_MORE_SESSION_OPEN/OUTSIDE_ALLOWED_PRICE_NO_FILL及0/50/100%成交、概率阈值邻域逐项执行并绑定输入、阈值、方法、结果。真实缺少冻结penalty/lookback邻域拟合工件，分别INCOMPLETE，不补拟合、不消费原预算、不缩域改判PASS；迁移条件按冻结名称与现有范围缺口报告 |
| AT-56 / 正式监测方法 | 固定输入执行费用/价格/延迟/部分成交、DEV冻结分位漂移、覆盖、相对上次登记的30交易日检查点、到期、成熟/缺失/未成熟处理。0.5与0.60等有限十进制部分成交按范围比较；未知/NaN不算合格。29/30/31边界明确；27负责持久化检查点身份和后续真实监测。方法输出不增加统计PASS点、不改历史结论，不代表实际漂移、用户行为或G7 |
| 门槛组合 / 持久化 | 硬FAIL优先，跨界区间和支持不足INCONCLUSIVE，未执行工件另列INCOMPLETE；SQLite重启、归档一致性、离线验证重放及账户/前向不变通过。RUNNING/FAILED/拒绝与独立诊断尝试保留，不占原拟合/确认性PASS额度 |
| 页面 | 七项门槛、每项依据/分项、清单和输入下载、独立状态、未决事项、监测方法与0联网重放可见；缺口长标识可换行，无正式操作按钮 |

`backend/tests/application/test_validation.py`通过公开API同时验证非空、重复机会、半成交100/200、分段一笔平仓、区间不足、全拒绝硬FAIL、空策略不足、损坏CAL、宿主准入拒绝、重启与重放。纯数值方法算例均随归档清单输出，不能替代真实统计证据。

## 最终工程证据

- [API](api-tests.txt)：3 passed，47.80秒。20同引擎边界7项API及1统计方法回归此前通过，保存在[专项原日志](focused-tests-before-test-fix.txt)；此专项合计9 passed/1 failed，其中首次21测试断言放置错误产生NameError，已修正后本票3项全部通过，不把该中间失败作最终通过记录。
- [构建](build.txt)、[实际Chrome](browser-tests.txt)、[截图](validation-gates.png)：最终前端换行修正后重新执行：Chrome1 passed/53.1秒，build57模块通过；宿主初始/account代理ETIMEDOUT仍保留在日志，最终账户公开API版本0断言及完整流程通过。此前5秒异步断言超时保留在[browser-async-wait](browser-async-wait.txt)，相同版本断言以30秒限时通过，未改变生产推进逻辑。
- 红记录：[覆盖缺陷](coverage-red.txt)、[分段事件缺陷](segment-red.txt)；最初404、执行场景、监测、损坏CAL和部分成交红绿记录在上级21专用日志中保留。
- [运行前源码](source-before-final.json)与[最终源码](source-after-final.json)：三个后端文件原字节一致；最终前端表格换行单独标识。19模型指纹依赖源未改变；20默认执行与场景变体共用单引擎，原20版本/工件作为历史保留。
- 上游完整460项基线由主代理执行通过，本票未重复整仓长跑。19工程来源见[实际19验收](../19-reconstruction-2026-10-10/acceptance.md)，20工程来源见[20验收](../20/acceptance.md)与[独立合并验收](../continuation-2026-10-11/merge20.md)；这些参考不把G2整项或G7改为PASS。

## 真实当前候选的隔离复验

根目录原件未启动。主代理使用只读SQLite在线备份及3811个已登记原件（659,165,829字节）创建一致副本，逐件SHA/长度一致、原数据库复制前后SHA一致。复制方式与清单见[copy-research19.py](../continuation-2026-10-11/copy-research19.py)、[复制清单](../continuation-2026-10-11/research19-copy-manifest.json)。本票[脚本](actual-current-gaps.py)仅消费该一致副本，拒绝受保护原路径。

真实重建模型 `8be461f3-af8b-4f0f-a707-13e41cf48249`，完整冻结 `42ccd899-ef10-4706-842d-ce71ce62e6d9`，最终验证 `baf981b6-b2bf-4f6f-b46f-1726f261de8e`。截止2022-02-10，当前三项CAL历史机会尚无成熟验证支持；初步 **FAIL**（G4/G5），G1/G2/G3/G6/G7 **INCONCLUSIVE**。这是REAL_ACQUISITION / RECONSTRUCTED_RESEARCH / FITTED_UNVALIDATED诊断，非真实独立确认或前向证明。

[完整实际结果](actual-current-results.json)与[清洁退出日志](actual-current-tests.txt)：重放一致、联网0；账户与原家族拟合尝试一致、无新拟合、无SEALED消费、无前向起点。前版验证 `1e18df81…` 重放409 `VALIDATION_CODE_CHANGED_SUCCESSOR_REQUIRED`，历史结果分别保存在before-coverage-fix/before-segment-fix文件。脚本复跑复用同一不可变冻结/影子，不重复推进或增加实际机会。

当前缺口明确保留：严格历史PIT与独立封存、独立概率有效性、冻结模型参数邻域工件、依赖统计假设、真实G6/G7、人工技术审阅。确认性当前准入拒绝是本票交付行为；真实统计及生产资格仍按33/34责任推进。本票完成不表示这些缺口消失。

最终METHOD浏览器运行件315文件/17,887,006字节保存到根`.roll-data/implementation-evidence/21/browser-final-method`，源/目标逐件SHA与长度零差异，见[保全清单](browser-runtime-preservation.json)。实际副本保留在同级`actual-current-copy`；旧METHOD测试目录不是最新源码复验凭据。
