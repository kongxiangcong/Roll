# 票 19 BaoStock 接入：双轴评审

固定基点：`1945d194cc0a7c295485c0579cc908b3abaac33f`。评审版本：`e51b003324163b2db4719527bbfdc3689f51dad4`。两个只读 Agent 分别检查规范与规格；不是模型技术资格审阅。

## Standards

1. **P2，文档标准违例**：`baostock_process.py` 将未知异常统一为 `PROCESS_OR_TRANSPORT_FAILURE`，丢弃 stdout/stderr；宿主又将非数字来源错误统一为 UNKNOWN。SDK 缺依赖、结构变更与程序错误缺少可定位诊断，违反 `project-layout.md`“未知异常保留可定位的脱敏诊断”。修复应保留安全阶段、异常类别、文件名和行号，不保留可能包含凭据的异常消息。
2. **P3，启发式维护判断**：报价与报价附带 STATUS 的选择表达式在扶摇与普通报价分支重复，possible Duplicated Code。计算一次当前请求条件即可；不是硬性标准违例。

## Spec

1. **P2，引入的实现缺陷**：每次 `zlib.decompress` 都重新取得完整解压预算，多页可以累计超限，同时 SDK 累积行。与来源契约“共用整次请求的总期限和调用/字节预算”“达到……解压字节……预算即失败”不符。应分别累计单次查询及整次请求的 decoded bytes，不能与 socket 接收字节混成同一口径；用两个分别合规、合计超限的压缩帧验收。
2. **既有完成缺口**：票 19 要求“在允许的开发及校准窗口取得时间外预测”和“冻结模型、校准器、特征与相关代码/数据指纹”。当前宿主采集导入仅登记真实覆盖，窗口为 NOT_PREREGISTERED，真实预检保留 FAILED。历史 PIT、完整执行状态/公司行为、实际开发校准支持及封存独立性尚未证明。METHOD 不能代替这些结果，票 19 保持 partial。
3. 未发现越出授权范围的新增行为。BaoStock、日历、显式访问模式、来源归档导入与失败预检均服务于本次数据补齐。

## 处理

同一实现 Agent 已在 `e64ab5d498baa0cc9e259afb7f9d5af1ed742160` 修复三个代码发现：累计单查询与整次请求的解压预算；保留安全阶段、异常类别及位置；共享报价选择条件。新增跨查询压缩帧及脱敏诊断回归通过。两个评审 Agent 已复核关闭上述代码发现。

实际完整取数又发现 SDK socket 捕获使用 bytearray，解析消息头时被用于集合查询，触发 TypeError。`1d0a93f05c0da88182c6818ad60e1aa03ebe99be` 将原件一次转为不可变 bytes；新增真实 TCP 与生产 BoundedSocket.recv 的公开 API 回归，原实现失败、修复后通过。11 项 BaoStock 测试通过，规格评审确认该修复；原真实失败运行保留。

实际重启又暴露恢复包清单只支持旧 research-inputs/archive_id 路径，新的 HOST_DATA_REQUEST 登记 archive_id=None 导致启动失败。`99bcfc4` 已修复并通过 changed-deployment PRE_UPGRADE、手工导出/恢复、损坏来源拒绝与共享 wire SHA/多 decoded SHA 的回归；规格评审关闭该问题。完整原件与 SQLite 来源指纹继续受恢复校验，未删除登记或跳过保全。

随后实际分红查询暴露 Windows 子进程 JSON stdout GBK/父进程 UTF-8 差异，原运行 PARTIAL 保留。`9be3176` 固定子进程 JSON UTF-8，原供应商行与 wire 解析保持；12 项 BaoStock 回归通过，规格评审无新增问题。最终实际 BaoStock COMPLETE、gaps=[]，数据资格不足继续按 FAILED 预检保留。

实际训练缺口继续保留，不通过添加客户端资格标志、缩窗、降低支持阈值或生成占位概率来关闭。

规范轴：1 项硬性违例、1 项维护判断；规格轴：1 项引入缺陷，另列真实研究完成缺口。
