# 19 只读绩效图与导出验收

## 已交付 / 尚缺

现有研究报告内生成/保存/查看QuantStats累计收益、回撤及观察月度图，下载独立HTML；四namespace分列，完整源报告/原指纹/日历/输入/库源码/渲染代码/图表/导出均保留。重放只校验原工件，不用当前库重算。正向链使用既有193文件METHOD样本副本，原数据库连接0、新拟合/预测/推进/验证/SEALED调用0、外部数据下载0，不能归为真实研究资格。

**历史切片当时partial，现已由[最终基准修复验收](../19-baselines/acceptance.md)关闭工程差量**：当时适配输出NO_SAVED_MATCHED_BASELINE_SERIES，但“没有保存同窗口基准”的判断错误，原状态已有三条基准，后续只读接入并验证错位拒比；没有另算交易或下载制造基准。真实账户仅选定单快照，外部转入不从两次NAV简单相除构造收益。HISTORICAL和ACCOUNT_CONDITIONAL也不连成策略曲线。未改旧冻结模型、已存报告、真实账户、资格、前向时钟或研究预算。

## 锁定组件与方法

QuantStats0.0.86 / Apache-2.0 / Windows Python3.13.12；独立环境36个固定依赖见requirements.lock，业务依赖未改变。wheel SHA 4cfb157c8228cbb47681d6a81767d465fbc2bdf529643dd7e836479d2165efd6，实际stats/utils/reports源码SHA及预处理审计见source-manifest.json，许可证原件QUANTSTATS-LICENSE.txt。配置ROLL_QUANTSTATS_PYTHON；-I -B隔离子进程避免同名stdlib遮蔽。30秒/3650时点/结果与图各8MiB，socket/requests/curl_cffi/download_returns入口拒绝联网。

首个保存收盘是区间锚，不推算初始资金到该收盘的未知收益，首收益null；库收益只接收之后的真实相邻收盘比值。保存日历缺日或NAV未知时不压缩窗口、不填零、不提供完整指标。净值归一到首收盘100再输入库回撤函数，明确价格序列。月度接口prepare_returns=false，过滤库为未观察月份补的0；边界月份只代表观察到的部分区间。252期年化/无风险率0明确仅为报告诊断假设，观察收益不足252不年化，不改变冻结实验。

## 公开及数值证据

- api-red.log首先暴露Windows长路径复制失败；改短隔离目录后api-red02.log正确404。
- api-green.log暴露研究statistics.py遮蔽stdlib；隔离-I启动修复。api-green02.log暴露实际库将月份列转大写；按固定版本修正。两份原stderr另存，未覆盖失败。
- api-green03.log：1 PASS/22.00s，33点固定2026-06-08至2026-07-23、实际QuantStats、SVG/离线HTML、幂等、旧报告原样、重启无库重放。
- reference.log：1 PASS/9.39s，一次真实库进程覆盖全零、单点、漏日、空NAV、首段下跌、大于100%日收益，以及实际账户外部转入不变成连续收益。未观察月份不导出0；首段下跌最大回撤保留-10%；大涨不被库误判为价格。
- browser-red.log工厂导入前置错误；browser-red02.log记录真实缺入口红灯。
- browser-green.log：1 PASS/30.2s，报告内生成三图、分列/33点/年化不计算、下载、重载/390px无横向溢出。
- 离线文件首次使用Playwright无扩展名缓存导致文本预览，browser-final.log保留；保存为.html后browser-final02.log：1 PASS/30.4s。实际下载HTML离线打开、截图export.png已目视核验，metadata折叠，图和指标清晰，不调用网络。
- build.log：TypeScript/Vite构建PASS。双轴审查0开放发现，报告见standards-review.md/spec-review.md；审查不重跑、不联网。

preservation.json：15份原现场保护文件无差异（只剔除本feature新增hunk）；model-preservation.json：12项旧模型依赖相对fe5d01c7无变化。app.py仅专用缓存补丁，原SSE插入留在工作树。

最终图轴统一百分比后 browser-accepted.log：1 PASS/29.2s；实际离线HTML与390px页面通过。图表不以0.01等未标明比例造成歧义。
