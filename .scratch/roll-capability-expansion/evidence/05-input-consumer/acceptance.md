# 05 来源输入与冻结模型消费者验收

基线b3e4eca。方法先于结果固定。API红404：1 failed/42.84s；初始化顺序失败6.18s已修（api-green.log）；初绿1 PASS/74.43s。审查P2：CAS版本<=200可写201却无法续写、执行准入晚于predict，两项均已修。api-final.log保留测试过程中源码升级使旧保存方法指纹失配的重放失败，不作为当前结果；固定源码/新profile最终 **1 PASS/93.32s**（api-final02.log）。

公开API证明原CAL输入重新计算features/predict与原保存概率相等，独立连续两步实际BUY_FILL2；原人工3帧、训练清单、账户及真实起点不变。幂等/冲突/旧revision拒绝、生产环境METHOD403、METHOD模型不能REAL、输入原件损坏409及还原、重启移除库配置离线重放通过。明确的持久METHOD CAS夹具模拟revision200（不伪称198次历史预测），API可续写201/202；漏日期为空bar/空signals并保留未知。另两种隔离worker METHOD故障输入UNKNOWN_STATE/INVALID_BAR来自保存输入的内存副本，只证明先拒绝后零predict，不冒充真实原件/权威来源。

最终Chrome **1 PASS/90.32s**（browser-final.log），运行/保存/重放/刷新/390px无横向溢出；最终profile .scratch/r05ufb、8171/5271，mobile.png。TypeScript/Vite通过（478.35KB/140.42KB gzip）。双审查修复后开放0；15受保护文件0差异、12旧模型依赖不变。

生产入口接通旧PostClose原包重放、宿主当天盘后截止/范围/规则/原gaps检查，当前producer仍强制状态/行动UNKNOWN，未获得真实正向准入。此切片仅MODEL/METHOD正向工程验收；非空初始持仓不假清仓，真实完整冻结未授予，独立支持/四非中心工件未供。新崩溃点未做实进程kill测试；只主张正常重启/事务CAS与不可变原件验收。后续来源契约与真实原件具备后再补REAL和26完整故障恢复验收。05保持partial。
