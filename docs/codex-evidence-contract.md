# Codex 受控取证契约

2026-10-08。对应票11、[共用事实契约](data-evidence-contract.md)与[实际验收](../.scratch/roll-p0/evidence/11/acceptance.md)。Codex 是完整本地 app-server 任务后端，宿主负责限定获取、原件、时间检查、SQLite 发布和进程收尾。默认 `DIRECT_HTTP` 路径继续可用。

## 实际部署与入口

- Python 实测3.13.12；锁 `openai-codex==0.161.0`、其配套 `openai-codex-cli-bin==0.161.0`，`uv.lock` 保存发行物哈希。实际模型 `gpt-6.1-sol`，禁止 provider/model fallback。
- 使用发行包自带 `codex.exe` 与 `codex-code-mode-host.exe`。后者为 Rust/V8，真实动态工具需要启用 `code_mode_host=true`；无需 Node 桥。宿主采用官方同步 `CodexClient` 的自定义 approval handler，未修改私有 SDK。
- 管理员显式提供 `ROLL_CODEX_AUTH_FILE`，只接受已登录 ChatGPT 的认证 JSON；不存在则保留 `UNAVAILABLE / CODEX_AUTH_NOT_CONFIGURED`，API-key 模式为 `CHATGPT_AUTH_REQUIRED`。Roll 不自动查找个人认证，不建立 API 计费通路。执行时只复制必要 ChatGPT token 字段，个人 config、skills、状态库不复制。
- 管理员可用 `ROLL_CODEX_MODEL` 冻结具体模型、`ROLL_CODEX_TIMEOUT_SECONDS` 将120秒上限缩小至1—120秒；普通页面/API只能提交问题，额外模型/预算字段返回422。模型目录与实际运行权限分别验证，目录中不存在返回 `MODEL_UNAVAILABLE`。

官方 [Python SDK](https://learn.chatgpt.com/docs/codex-sdk)、[app-server 协议](https://learn.chatgpt.com/docs/app-server)及固定 [0.161 源码](https://github.com/openai/codex/tree/979011409de0a60b52f179721948e65531d26144) 是接入依据。SDK 与完整 Codex Runtime 已实际使用；本票没有引入闲置 Agents SDK，DeepSeek 路径及两后端运行切换由12/13分别实施。

```text
POST /api/data/requests                             -> 不可变 DataRequest
POST /api/data/requests/{id}/codex {question:string} -> 202 RetrievalRun
GET  /api/data/runs/{id}                            -> 运行/终态/脱敏审计
POST /api/data/runs/{id}/cancel                     -> 请求取消
GET  /api/data/snapshots/{id}                        -> 宿主发布的快照
GET  /api/data/archives/{sha256}                     -> 校验后的归档下载
POST /api/data/runs/{id}/replay                      -> 固定事实回放、网络0次
```

页面“持仓与关注 → 市场事实 → 取证方式”选择 Codex，输入待补问题，显示证据、逐组缺口、运行状态及取消。后端指纹和技术预算放在折叠详情中，普通用户无需选模型。

## 最少上下文与真实允许能力

每次任务建立仓库外的空 `cwd`、独立 `CODEX_HOME` 和空用户目录，过滤 worker 环境；不传账户现金、持仓数量、资金授权、资格、账本路径、私人文件或完整名单上下文。模型只接收本次对象、事实组、用途、日期/截止、必需字段和问题。取证时宿主再次检查当前对象范围。

有效配置：approval never、自定义审批拒绝、read-only、空 environments/selectedCapabilityRoots、项目文档额度0、无 fallback filenames、web search/shell/MCP/apps/plugins/browser/computer/subtask/memories 等关闭，技能 instructions/bundled/cloud 关闭，analytics/feedback/OTel 导出关闭。Windows native home 查找仍可能发现个人技能元数据；启动前只向独立 home 的 `skills/config/write` 写 disabled，再 `forceReload` 核验 enabled=0。实际 thread 返回 `instructionSources=[]`；不向模型发送技能输入、mention、localImage 或环境覆盖。

| 允许能力 | 宿主边界 |
|---|---|
| `roll_read_evidence(instrument,group)` | 一个请求内对象/事实组；调用07固定适配器；子请求继承原日期、用途、cutoff、daily/quote source、本组及公共 required_fields；不取消原数据门禁 |
| `roll_read_source(instrument,source_id)` | 当前仅 `MOUTAI_OFFICIAL` 对应 `SSE:600519`；固定官方主页 GET，拒绝任意URL、参数、重定向、非公开地址和非HTML；其他对象明确无登记来源 |
| `clock__curr_time` | Runtime 内无敏感读写的时间辅助，显式允许；不赋予账本/网络能力 |
| `functions.exec/wait` 的纯 V8 运算 | 固定发行物无 `fetch/process/require`，任何模块 import 拒绝；只能委托允许的工具；外层操作、总时限及宿主委托预算有限 |

实际 V8 能力探针和生产对抗分别登记。原生 clock 在 V8 内的调用没有逐次宿主 callback；它受外层操作次数和总任务时限约束，不宣称单独逐次 clock 计数。每次宿主数据委托仍单独计数。固定 [V8 globals](https://github.com/openai/codex/blob/979011409de0a60b52f179721948e65531d26144/codex-rs/code-mode-runtime/src/globals.rs) 与 [模块加载拒绝](https://github.com/openai/codex/blob/979011409de0a60b52f179721948e65531d26144/codex-rs/code-mode-runtime/src/module_loader.rs) 支持该运行边界。

生产 worker 不导入 Roll 账本，不提供账户、资金、资格或券商写工具。网络由宿主固定 GET 实施；外部文本只能作为数据。read-only 本身不宣称完整 OS 文件/网络隔离，实际限制来自空环境、关闭能力、允许表、审批拒绝、V8能力及宿主检查的组合。managed layer 若使技能、MCP或关键配置无法关闭，任务拒绝启动并返回可查询原因。

## 有限执行与恢复

| 控制 | 固定上限 |
|---|---|
| 端到端任务时限 | 120秒（管理员仅能缩小）；HTTP不超过剩余时限及8秒 |
| 并发 | 同一 SQLite 数据目录1个 Codex 任务；不同活跃宿主也受门禁 |
| 宿主工具委托 / Runtime 外层操作 | 各8次；超过停止，不无限重试 |
| 实际 HTTP 获取 | 6次与 DataRequest.max_calls 中较小值 |
| 单响应 / 总接收字节 | 64KiB / 256KiB；4096字节解码块，最多一个块边界超限仍记账 |
| 给模型的工具结果 | 单次64KiB / 累计256KiB，独立于实际接收统计 |
| 子任务、递归、自动宿主重试 | 0 |

失败、超限、丢弃、取消时已读取的字节都计入 `received_bytes`；不以归档长度替代接收量。`archived_bytes` 与 `model_tool_result_bytes` 单独记录，子 DIRECT_HTTP 运行公开 `retrieved_bytes`。预算耗尽后不再发请求，已有原件/子快照仍可查询。PDF超过本票64KiB预算会成为真实局部缺口，不继承07较大额度。

worker 在得到任务前加入 Windows kill-on-close Job；宿主取消先停止授权、发送官方 `turn/interrupt`，有限等候后终止所属 Job。所有已归属 runtime/bridge 子进程收尾后才保存终态及快照。异常退出、超时、取消保留独立状态，不把晚到结果发布为完成。

task root/owner nonce 先持久化，之后才写认证副本。正常完成精确移除自身副本和目录。宿主硬崩溃时 Job 关闭子树；重启通过 host PID+creation time 判断活跃所有者，保留其他仍运行的任务。只有已中断、已登记的本任务 temp 绝对路径、匹配 run UUID/marker 且无 reparse/junction 才清理；没有前缀扫描删除、历史PID杀进程。拒绝清理保留 `recovery_cleanup.status/reason`，不能静默成功。

终态包含 `PARTIAL/COMPLETE`、`UNAVAILABLE`、`INVALID_OUTPUT`、`TOOL_LIMIT`、`TIMED_OUT`、`CANCELLED`、`FAILED`、`INTERRUPTED`。普通无依据是缺口；SDK/权限错误、坏结构和真实进程错误另留 error。不是每次模型完成都代表事实完整。

## 宿主候选检查与归档

Codex 最终 schema 仅允许 candidates/gaps。宿主核查对象/事实组、当前 run 拥有且HTTP成功的原件 SHA、连续原文短引、数量及长度。原最终输出自身也归档，不能当作候选出处。无归档、越界、坏 schema 或原文引述不相符，返回 `INVALID_OUTPUT`，不发布正常快照。

宿主核验的07 facts/coverage 保留原单位、必需字段、完成度及知识时点规则；模型候选另标 `MODEL_EVIDENCE_CANDIDATE`、`quote_verified=true`、`assertion_verified=false`、`event_time=null`、`cutoff_eligible=false`。实际获取时点不证明事项时间、断言真值或过去可得性。当前旧报价仍陈旧，官方主页主营资料不成为历史事项的PIT证据；候选产生明确未核实缺口并保持 PARTIAL。

真实SQLite按单事务发布运行终态和快照，原件按内容哈希落盘、Parquet归档经API下载核验。回放只读固定归档并验证其 facts 与SQLite一致，网络0次；它补充确定性验证，不能替代真实多轮SDK任务、实际取消和权限检查。审计不含认证值或私人账户上下文，不启用自动云 trace。
