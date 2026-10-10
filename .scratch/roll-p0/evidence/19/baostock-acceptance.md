# 票 19 江西铜业补齐验收 · 2026-10-09

**结果：partial / needs-info，20 不解锁。** 本次完成 BaoStock 实际采集、来源登记、失败预检、研究页面、恢复兼容性与零联网重放；未完成真实时间外模型/校准器冻结，未生成实际收益概率或启动正式前向实验。仅跟踪江西铜业 `SSE:600362`，保留用户此前确认的账户基点，无需个人历史成交记录。

## 实际数据

请求范围为 2023-01-01 至 2026-10-08，原价日线实际覆盖 2023-01-03 至 2026-10-08。所有接收时间按真实取得时刻保存，未回填为历史当时可得。

| 来源 | 最终结果 | 覆盖 |
| --- | --- | --- |
| Fuyao | COMPLETE | 909 原价日线、909 当前前复权日线、5 公司行为记录 |
| BaoStock 官方 PUBLIC | COMPLETE | 909 原价日线、909 日期对应交易状态、1377 自然日日历记录、5 分红记录；来源取数 gaps=[] |

BaoStock API_KEY/VIP 的一次查询返回 `10001015`；公开官方资料未查到其定义，不推定为过期、欠费或永久不可用。显式采用官方免费 PUBLIC 模式，SDK 子进程不接收密钥，无静默认证回退。依赖锁定 BaoStock 0.9.4、Python 3.13.12；探针运行环境与生产锁定环境分列。

两来源 909 个重叠交易日的开高低收与股数成交量全部一致；成交额 908 天一致，2023-05-08 有 1 天差异。原值与差异保留，不挑选、平均或填充。两来源上游独立性未证明，一致不构成资格通过。日历为供应商 A 股报告，未冒充交易所官方历史权威；状态/ST 与分红字段未冒充全部历史执行状态或公司行为完整处理。

实际原始 socket 接收字节、SDK 解码响应和 Parquet 全部存于本机运行目录，逐 SHA 验证。认证帧不入档；所有公开证据无配置密钥值。来源数据权威为 `NONE; MARKET_DATA_ONLY`。

## 修复与保留记录

1. 原完整 BaoStock 调用因 bytearray 被用于集合查询而失败，保留原 FAILED 运行；`1d0a93f` 一次转为 bytes，真实 TCP/生产 recv 回归先红后绿。
2. 新 HOST_DATA_REQUEST 数据集没有旧 archive_id，升级前备份清单因此不能启动。`99bcfc4` 从 SQLite 校验原请求/运行/快照的指纹、原件与解码关联，兼容旧 METHOD 路径；升级、备份、导出、恢复及损坏拒绝验证通过，同一原件对应多份解码记录也受支持。实际后端已恢复并保持 HTTP 200。
3. 第一次修复后真实采集为 PARTIAL：日线/状态/日历成功，中文分红 JSON 通信受 Windows 编码影响失败。`9be3176` 固定子进程 JSON 为 UTF-8，保持供应商原字节及 SDK 字段解码不变；12 个 BaoStock 回归通过。再次明确创建新完整采集，原 PARTIAL 保留。
4. 最终来源登记后继协议链接原预检协议，失败尝试继续计入同一谱系预算。两个预检均 FAILED，无模型/校准器/概率产物，无资格与前向起点。没有封存读取、真实账户写入或 Fuyao 重复请求。

## 验收

- 双轴代码审查的诊断、预算与重复条件问题修复，并复核关闭。实际运行发现的 socket、恢复与 UTF-8 问题同一实现 Agent 修复，规格评审无剩余可操作发现；见 [评审](baostock-review.md)。
- 实际重启后 7 个来源/数据集/预检对象与重启前完全一致；两来源归档 SHA 和 facts/observations 离线重放一致，网络调用 0。手工恢复包导出包含这些全部市场原件，逐项指纹核对通过；含账户的恢复包只在本机私有目录，未发布。原账户与任务开始基线完全一致，见 [持久化证据](baostock-durability-results.json)。
- 安装的 Chrome 实际研究页显示 909 天覆盖、FAILED · RESEARCH、窗口/PIT 缺口、NOT_GRANTED，无 METHOD 概率混入、无页面错误。页面只 POST 一次归档重放，无新取数或拟合，见 [浏览器证据](baostock-browser-results.json)与[研究区域截图](baostock-actual-research.png)。
- 前端生产构建通过，见 [build](baostock-build.txt)。初始后端基线 372 passed；本次最终完整集合 **392 passed，0 failed/skipped/errors**，四个隔离测试进程覆盖每个模块恰好一次（111/87/79/115 项），测试期间代码及测试指纹不变。最慢分组 664.92 秒；与串行初始基线的执行配置分列，见 [完整集合与指纹清单](baostock-backend-full-manifest.json)及其中四份原始分组日志。
- `.env` 指纹保持不变，公开变更文件无配置密钥值，私有账户/恢复包仍忽略，见 [保全核对](baostock-preservation-results.json)。

## 仍不能关闭票 19 的原因

本次补拉证明当前供应商档案覆盖和可重放性，无法证明其在过去各决策时点已可得的版本；完整公司行为处理、全部特殊交易状态、历史规则有效范围仍缺可审计证明。江西铜业实际 DEV/CAL/SEALED 窗口尚未预登记，不能沿用旧工程 80/40/21 分片；历史封存独立性仍 UNPROVEN。

真实来源入口目前完成覆盖登记与资格预检；实际拟合/时间外预测/独立校准/完整模型冻结仍未交付合格证据，现有可拟合路径为 METHOD 工程。不能仅增加客户端 PIT 标志、重新命名封存、降低每类 20/有效块等门槛、缩窗或生成占位概率来关闭。需要能够审计的合格输入、预登记研究窗口、满足原支持条件的实际成熟标签及真实训练接入；个人证券历史成交不能代替这些市场与研究证据。

## 原证据入口

- [最终两来源汇总](baostock-real-acquisition.json)：分别保留接收时间与精确运行 ID，离线比较不重新联网。
- [初始 FAILED 与 Fuyao COMPLETE](baostock-real-acquisition-initial.json)、[中间 PARTIAL](baostock-real-acquisition-partial-utf8.json)、[最终 BaoStock COMPLETE](baostock-real-acquisition-repaired.json)。全部旧运行继续存于实际运行目录。
- [认证第一方核查](baostock-auth-investigation-2026-10-09.md)、[VIP 探针](baostock-vip-probe.json)、[PUBLIC 探针](baostock-public-probe.json)、[生产版本](baostock-runtime-versions.json)。探针不是正式来源归档或训练资格。
- [免费补充源调研](free-data-research-2026-10-08.md)：腾讯/新浪/Yahoo 探针仅可行性验证，不冒充本次训练输入或历史 PIT。
