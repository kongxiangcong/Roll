# GS Quant：设计借鉴与 Roll 下一步

调研日期：2026-10-28。范围：官方文档与源码阅读，未安装、未运行 GS Quant，未调用其数据或定价 API。以下链接指向上游可变的 `master`，未锁定或宣称验证某个固定 commit。

## 结论

值得借鉴设计，目前不安装整包、不替换 Roll 回测引擎。Roll 面向 A 股单账户辅助决策，优先完成单标的真实数据 → 归档 → 回测 → 辅助判断 → 重启读回／次日更新的可靠闭环。机构品牌与开源代码都不能证明预测可信性；主数据适用性与真实端到端运行仍待验收。

## 可借鉴的边界

| 官方来源 | 阅读结论 | Roll 应吸收什么 |
| --- | --- | --- |
| [backtests/data_handler.py](https://github.com/goldmansachs/gs-quant/blob/master/gs_quant/backtests/data_handler.py) | `Clock` 防止模拟时间倒退；`DataHandler` / `time_check` 防止读取模拟时点之后的数据。 | 分开事件时间、数据可用时间和模拟时间；仍须明确 A 股日线何时可用，不能仅凭日期相等判断无未来信息。 |
| [backtests/data_sources.py](https://github.com/goldmansachs/gs-quant/blob/master/gs_quant/backtests/data_sources.py) | `GenericDataSource` 可包装本地 `pd.Series`，`GsDataSource` 通过 `Dataset.get_data` 取数。 | 数据、策略和模拟执行分层测试；缺失、停牌、暖启动不足应有明确规则，不随意插值制造可交易数据。 |
| [timeseries/econometrics.py](https://github.com/goldmansachs/gs-quant/blob/master/gs_quant/timeseries/econometrics.py) 与 [入门示例](https://developer.gs.com/docs/gsquant/getting-started/) | 窗口、ramp-up、价格到收益的口径需显式选择。部分 Series 运算可本地执行，但 `excess_returns` 的 Asset/Currency 分支及 Sharpe 相关路径可能取远端数据。 | 固定窗口、暖启动、复权／RAW、收益和基准定义；不能把整库称为离线工具。 |
| [risk/scenarios.py](https://github.com/goldmansachs/gs-quant/blob/master/gs_quant/risk/scenarios.py) | 情景对象表达显式 shock 假设。 | 压力情景回答“如果发生会怎样”，不能当作该情景发生概率。 |
| [backtests/generic_engine.py](https://github.com/goldmansachs/gs-quant/blob/master/gs_quant/backtests/generic_engine.py) | 引擎依赖 `PricingContext`、`HistoricalPricingContext` 与 `calc` 等定价机制。 | 不是简单离线 SMA 回测的直接替换；先验证现有最小链路，再决定是否有具体能力缺口值得引入依赖。 |

[官方仓库](https://github.com/goldmansachs/gs-quant)提供开源实现；[官方入门与认证文档](https://developer.gs.com/docs/gsquant/getting-started/)区分独立分析与 GS API 服务。服务路径需要相应凭证、权限及数据授权，开源不等于免费获得数据或模型服务。

## 下一项可验收工作

在另行确认真实来源、模型调用预算与标的后，以一个适用普通主板证券完成只读闭环：

1. 核对证券主数据、交易日、数据更新时间、RAW／复权口径、缺失与公司行为处理；保存可复现输入及版本。
2. 固定策略、暖启动、成交费用和基准，确认回测与辅助判断引用同一标的及资料时点。
3. 注入缺失、部分失败与取消；重启后读回任务、归档及部分结果，次日更新不得复用过期判断冒充当前结论。
4. 记录实际耗时、费用、失败原因和可重复结果；账户保持只读，不触发交易。

此验收证明工程链路能可靠运行，不自动赋予统计有效性。历史 CAL、固定均线历史表现与当前上涨概率必须继续区分；独立前瞻验证是另一项工作。当前工作台行情刷新是手动或页面可见时勾选五分钟轮询，不等于无人值守次日更新。参见[工作台运行边界](../workbench.md)。

本记录不改变现有账户、数据、研究与正式资格契约，也不授权新服务调用或功能实现。
