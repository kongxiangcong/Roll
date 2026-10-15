# 05 增量：同一轨迹时间三段

05仍partial。读取不可变费用诊断及其原始METHOD帧，按完整声明会话跨度的floor(N×i/3)分三段；最多200声明位置，不把漏日压成已观察帧。每段带前一边界净值、当时现金/各lot/预留，边界无原状态则未知，不LOCF、不重置资金、不重新模拟交易或把分段成绩拼起来。

纯线性只读派生，保存源manifest/input、原方法/统计源码指纹、分段结果和原件。full-window含未知则收益/回撤None，原已知硬失败仍保留；分段输入缺口、未知NAV、原成交费用分别保存。METHOD整数不冒充真实日历或新增独立样本，永不PASS/不授资格。

验收：

- api-red.log：公开新入口404，1 failed/19.90s。
- api-green.log：1 PASS/22.68s，六帧三段1—2/3—4/5—6，逐字核对第二段承接的现金、各lot及原NAV锚；第五帧未知NAV不补值；保存/幂等/列表/重启重放，原状态/参数不变。
- api-final.log：1 PASS/25.47s，追加稀疏帧10/12，完整跨度保留12个位置；第三段9/10/11/12，缺9/11，边界8无状态，现金和持仓均None；原六帧分段仍重放；新隔离源归档损坏GET409、finally恢复字节。
- api-final02.log：1 PASS/28.08s，进一步保留分段输入缺口；声明跨度1000拒绝422 SPAN_LIMIT_NO_COMPRESSION，未压缩。
- browser-green.log：Chrome1 PASS/30.2s，从费用诊断保存三段、承接/指标/未知展示、原件重放、重载版本和390px无横向溢出。
- build.log：TypeScript/Vite通过；双轴审查开放发现0。
- preservation.json：15原现场文件无差异；model-preservation.json：12旧模型依赖不变；旧successor_protocol/successor_shadow/policy_successors/statistics源码git diff为空。

没有新依赖、拟合、SEALED、网络、真实账户/资金/资格/计时动作。实际窗口与独立分段支持、真实输入、共同风险基准、执行延迟、冻结邻域与迁移仍需本票剩余消费者和证据；未关闭05或06/08的依赖。
