# 23: 模型技术审阅与验证交付

**What to build:** 按2026-10-11明确的 CODEX-only 当前范围，通过已验收的 Codex 审阅冻结实验材料，保存复现检查、异议处理和局限，并向用户展示及导出完整验证包与真实交付状态。DeepSeek 当前及后续验收排除，既有接入证据仅保留历史。

**Blocked by:** [21 · 自动验证与门槛证据清单](21-validation-evidence.md)；[13 · 双后端切换与生产权限隔离](13-backend-switch-isolation.md)。

**Status:** ready-for-agent

**Completion:** complete

**Primary acceptance:** AT-51。

**References:** [规格](../spec.md) ID-08、ID-16、ID-17、ID-21；Testing Decisions 的主要边界 1、4—7；[目录与实施约束](../project-layout.md)。

## Acceptance criteria

- [x] 用户可对确定的冻结材料发起技术审阅并查看进度/结果；ReviewRecord 保存方法、后端/模型/配置、材料指纹、时间、工具与复现检查、异议、处理依据和局限，重试保留运行关联。
- [x] 当前 CODEX-only 范围真实读取精确批准的冻结材料，通过同一 ReviewRecord 输出契约保留真实审阅接入证据；DeepSeek 排除且0调用，不作为后续完成前提或记为通过。
- [x] 宿主核对材料指纹、依据引用、必需字段及阻断问题处理证据；坏结构、无法核实的必需项、超时或取消准确呈现，文字赞同或两个后端一致不能覆盖缺口。
- [x] 自动验证结果、review_status、实验完成状态和正式能力分开呈现；尚未到协议终点或缺必需检查时保持初步结果/未完成，不能因技术审阅生成成功就声称真实验证已结项。
- [x] 协议已结束且自动验证与审阅材料完整时，FAIL 或 INCONCLUSIVE 也可形成完整验证交付；导出包保留输入、代码/数据/协议指纹、全部尝试、结果、异议与局限，正式能力继续关闭。
- [x] 页面、验证包和资格说明如实标注“未经人工独立复核”；不要求专业人士签字，不把模型审阅称人工独立复核，不增加多角色金融裁决或 Agent 自签工具。
- [x] 经 FastAPI 应用入口和真实持久化验证结果/缺口及导出可追溯性，补关键网页流程；将 CODEX 真实调用、固定输出重放和工程 FAIL/INCONCLUSIVE 样例分别留证。真实协议终点交付在 33 进行。
- [x] 遵守目录与实施约束；仅引入本票实际需要的模块、接口和校验，保留 PRD 必需控制，不新增假设性兼容层、审批或泛化框架。

## Comments

2026-10-07：按已确认拆分发布；尚未实施或验收。

2026-10-08 本轮依赖前沿核查：未启动本票。21验证与13双后端隔离未完成。保留原分诊标签和全部验收要求，不用合成样例关闭任务；实际解锁后继续。整体执行证据见[实施记录](../execution-status.md)。

2026-10-11：21 独立验收后已按顺序实现本票本地部分，Completion partial，Status ready-for-agent 保留。最终 API/SQLite 39项345.47s通过，浏览器1项56.6s、构建58模块2.00s通过；固定输出/真实SDK合成loopback与宿主终点FAIL/INCONCLUSIVE分别留证。12个19依赖源码未改，无新拟合、预算/SEALED/实际前向。完整收据见[23验收](../evidence/23/acceptance.md)。

实际 CODEX 和 DeepSeek 原批具体材料外发被自动审批审查拒绝，0次实际外发；不把本地worker/loopback作为两个真实后端验收。历史[根审批清单](D:/dsh-proj/Roll/.roll-data/implementation-evidence/23/provider-approval/provider-material-manifest.json)与原packet同SHA。实际一致副本和浏览器640文件保全在根`.roll-data/implementation-evidence/23`，凭据文件排除，0差异。此原包及 `actual-review.py` 已因后续方法修正失效，仅作历史，不得执行。本票第2/7项及AT-51未完成；真实终点统计由33承担，当前actual诊断仍preliminary FAIL且NOT_GRANTED。

2026-10-11 修正后接续：三项P2已合入 `25d9b9a`，独立公共边界及DIV数学通过。新实际只读备份副本追加 linked successor，freeze `647b6164-e716-42ff-bbd6-177e60ec5759`、DIAGNOSTIC `a28f871f-42cd-4ab0-b358-ced71971a981`（G4/G5 FAIL，G7等 INCONCLUSIVE），复用原模型/三份CAL forecasts和全部四次fit/CAL历史，预算未重置。新material `b27b0047-d0ef-4c39-8d8d-46ad20becc74` / `95ddbd52fa7f4e2df78b97556f36c6c675da75603eb290ec5ecab260abfbfba1` 见[新永久清单](D:/dsh-proj/Roll/.roll-data/implementation-evidence/continuation-review-fixes/provider-approval-current/provider-material-manifest.json)。正文包含父协议/全部attempt IDs和模型工件指纹，但既有投影省略旧freeze ID/指纹/原模型UUID；完整关联只在宿主本地freeze.basis，详见[验收](../evidence/23/acceptance.md)。新helper仅编译、0外发；须另获新包/目的地明确授权。Completion继续partial，24未解锁，账户/原19/SEALED/真实forward未变。

2026-10-11 当前范围覆盖上述历史等待：用户明确批准同 `95ddbd52…abfbfba1` 包仅 CODEX `gpt-6.1-sol` 真实审阅一次，DeepSeek 当前及后续忽略。第一次真正启动的 `88f44e5c…853c` bootstrap前SDK失败完整保留，根因未知；无模型/正文工具。一次无模型 SDK 账户探针通过后，按明确指令创建唯一次 `retry_of` 接续 `ed0d834e-049b-4356-b5a7-1ff5bc853aef`，66.392s COMPLETE，ReviewRecord `2c05d94c-33a0-4353-9078-aed0060d7c6e`、七批准正文逐SHA读取及一次0网络宿主复现均核验。两个CODEX运行与归档持久化，原FAILED不改；真实helper最终exit0，12模型/6材料源SHA、账户/研究表/模型/冻结/尝试预算/原19及旧副本不变，DS0/SEALED0/真实forward未启动。六项异议、显示截断和继承正文缺口保留。当前范围 AT-51/本票 complete，可推进24依赖，但真实候选交付 INCOMPLETE/preliminary、四BLOCKING未解决、G4/G5FAIL/G7等INCONCLUSIVE、NOT_GRANTED仍明确，不能据23完成启用正式动作。详见[当前23验收](../evidence/23/acceptance.md)及[真实执行收据](../evidence/continuation-2026-10-11/review-fixes/codex-execution-receipt.md)。
