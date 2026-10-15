# 19 保存基准遗漏修复与工程完成

原19-performance/acceptance.md记载的“没有保存连续基准”判断错误：同一固定193文件donor的影子revision2已有CASH、START_HOLD、MA5_MA20各33点。旧适配只读取curves.SHADOW，遗漏platform.state.comparators。此次直接消费这三条保存曲线，不运行simulate、advance、模型、校准、SEALED或任何新交易账本。

候选/基准共用saved_interval：要求日期完整、有序、唯一且与原日历精确相同，无dropna/填零/交集裁切。各基准有原点、缺失、未知及意外日期明细。完整基准计算同一首收盘锚定、区间收益/回撤/观察月度、描述性策略减基准；不足基准不输出相对收益，也不叠入三图。没有把同窗口比较升级为风险匹配资格，ACTUAL/HISTORICAL/SHADOW/ACCOUNT_CONDITIONAL仍分列。

三条曲线可能完全重合，保留原值和图例。CASH含原期初持仓处置，不能假定收益0；API验收逐条核对全部原点并独立用末NAV/首NAV-1核对到1e-12。报告表、三图/基准月度柱、离线HTML和覆盖限制均接入。仍为QuantStats0.0.86/Apache2，版本与依赖继承19锁定环境，无新增包或网络。

验收：

- api-red.log：实际公共API仍返回NO_SAVED_MATCHED_BASELINE_SERIES，1 failed/20.86s。
- api-green.log：边界1 PASS；API的错误测试假定CASH恒0失败，原失败保留。没有改原曲线。
- api-final.log：1 PASS/22.34s，三条原曲线、首末收益、归档/导出/幂等/重启。
- mismatch-api.log：1 PASS/32.63s，同一公开链额外在自有METHOD副本引入CASH漏日，明确SAVED_BASELINE_WINDOW_MISMATCH，完整策略曲线保留，基准收益/相对收益不计算，旧图表仍原样读取。测试后恢复副本行，未改193文件原donor。
- 原数值边界补入固定完整/错日/漏日/NULL基准：实际QuantStats已通过，见api-green.log的另一测试。原全零/短窗/首跌/大涨/现金流隔离检查保留。
- browser-green.log：Chrome1 PASS/31.6s，三基准表、三图、导出、实际本地HTML打开、刷新/390px。export.png已目视核验，表/图/图例及资格限制可读。
- build.log通过。standards-review.md/spec-review.md开放发现0。
- legacy-replay.json/log：修复前已生成报告1份，从本轮自有旧METHOD profile再复制到新目录；无库配置时GET/重放/导出全字节一致，旧报告没有benchmarks字段，未补新数据/重渲染；旧profile全文件SHA前后一致。
- preservation.json：15原现场文件无差异；model-preservation.json：12旧模型依赖无差异。

19工程完成；METHOD与真实收益/独立统计有效性/正式资格保持区别。先前partial原因被本修复解除，历史失败日志保留。05的真实输入/完整冻结消费者差量和09生产整链外部采集条件仍各自未完成。
