# 11: Codex 真实受控取证

**What to build:** 用户发起同一事实请求，可由完整 Codex 任务后端查得可追溯依据或明确缺口，并在运行记录中看到后端、工具、材料、时点和完成状态。

**Blocked by:** [07 · 单源日线与报价证据闭环](07-market-evidence.md)。

**Status:** ready-for-agent

**Completion:** complete（2026-10-08；完整Runtime接入通过，实际资料保留PARTIAL，12/13/23独立验收）

**Primary acceptance:** AT-77。

**References:** [规格](../spec.md) ID-06—08、ID-17—18、ID-20—21、Testing Decisions 1、4、6—7、Further Notes 外部资产追踪；[目录与实施约束](../project-layout.md)。

## Acceptance criteria

- [x] 调查实际本机环境与官方接入能力，锁定 SDK/runtime、模型、认证方式、工具和必要桥接版本；完整 Codex 任务运行时接入共用 DataRequest/RetrievalRun，不将普通聊天补全或单次连通标作完整任务接入通过。
- [x] 常规接口缺失的事实可由受控任务实际查找网页或其他依据；返回经宿主时间/口径检查的证据候选，保存原文/原响应、链接、获取时间及运行指纹，无依据时明确缺口。
- [x] 生产任务使用独立工作目录、明确配置与允许工具，只收到必要对象和问题；不自动装载开发 AGENTS、SKILL、个人技能或参考仓库指令，不建设插件发现框架。
- [x] 固定运行的 backend、model、config_fingerprint、sdk_runtime_version 和实际工具；工具结构或缺权限的真实限制记录为局部能力，不用已有订阅推断全部接口权限。
- [x] 任务时长、调用量、并发、递归与取消由宿主控制；坏结构、缺工具、权限不足、超时、取消和部分证据分别返回可查状态，不伪造成功或无限重试。
- [x] 取证工具不能直接写账本、风险授权或资格；外部材料的指令不改变权限，网络工具也受副作用限制。密钥不进上下文或审计，默认本地脱敏记录而不自动上传含账户数据的云 trace。
- [x] FastAPI 发起的任务在真实 SQLite/归档中留下可查询结果，页面展示证据与缺口；真实运行验证多轮工具取证、结构化结果和取消/错误，固定归档补充确定性回放，二者分开报告。只测替身或单次 API 的项目不能标为真实接入通过。
- [x] 本票独立验收 Codex，可与 12 并行；13 负责运行中切换和共同权限组合，23 另验技术审阅输出。记录环境、版本、实际输入/结果、工具及证据，不把本票通过推及 DeepSeek。
- [x] 遵守目录与实施约束；仅引入本票实际需要的模块、接口和校验，保留 PRD 必需控制，不新增假设性兼容层、审批或泛化框架。

## Comments

2026-10-07：按已确认拆分发布；尚未实施或验收。

2026-10-08T01:34:00+08:00：07 已实际完成，基于集成 `1159dc71b610d15c17fd7d889f08c98978f0bc40` 开始本票；独立树/分支 `11-codex-evidence` / `codex/roll-p0-11`。沿已确认 FastAPI、真实 SQLite/隔离原件、Chrome 与实际 Runtime/进程验收 seam 逐切片 TDD；父管理 execution-status。锁 Python SDK/runtime 0.161.0，不引入未使用 Agents SDK 或自造 Node 桥。真实运行与外部 worker 方法案例分别留存。

2026-10-08T04:23:32+08:00：完成代码 `653c300a3de7540ddc3d7e25985cc1ecb8f6e571`，已合最新集成 `12c95639755ce42d711a7c415eeed98a47d981dc`。实际ChatGPT SDK/runtime0.161.0、gpt-6.1-sol/openai、独立空cwd/home及必要认证、技能0/MCP0/instructionSources空均核验。真实生产纯V8探针只允许两host读取+clock，fetch/process/require不可用，node:fs拒绝；禁止敏感读取/写入/POST，账户不变。实际完整多轮、候选宿主校验、Chrome显式Sina来源与任务中取消通过，资料PARTIAL不升级truth/PIT/资格。总接收字节含失败/丢弃、父必需字段/来源继承及活跃宿主保护补TDD；真实SDK API宿主硬崩Job归零/marker精确auth清理与METHOD_CASE崩溃、marker/junction拒绝分列。完整后端173通过（08合前），最后自身14与合08后的07/08/11交集44通过，45模块构建通过；实际Sina Chrome47.6秒通过，08方法工厂独立11.9秒通过。保留早期真实失败和夹具配置错误，不称默认全部浏览器suite全绿。146运行文件根ignored永久保全、SHA不匹配0/auth复制0；明确自有真实auth副本0遗留。见 [验收/状态分层/实际原件](../evidence/11/acceptance.md)、[契约](../../../docs/codex-evidence-contract.md)、[永久保全清单](../evidence/11/root-runtime-preservation.json)。不推及DeepSeek、切换或技术审阅；暂无本票外部阻塞。
