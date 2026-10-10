# 23: 模型技术审阅与验证交付

**What to build:** 通过已验收的 Codex 或 DeepSeek 审阅冻结实验材料，保存复现检查、异议处理和局限，并向用户展示及导出完整验证包与真实交付状态。

**Blocked by:** [21 · 自动验证与门槛证据清单](21-validation-evidence.md)；[13 · 双后端切换与生产权限隔离](13-backend-switch-isolation.md)。

**Status:** ready-for-agent

**Completion:** partial

**Primary acceptance:** AT-51。

**References:** [规格](../spec.md) ID-08、ID-16、ID-17、ID-21；Testing Decisions 的主要边界 1、4—7；[目录与实施约束](../project-layout.md)。

## Acceptance criteria

- [x] 用户可对确定的冻结材料发起技术审阅并查看进度/结果；ReviewRecord 保存方法、后端/模型/配置、材料指纹、时间、工具与复现检查、异议、处理依据和局限，重试保留运行关联。
- [ ] Codex 和 DeepSeek 使用同一冻结材料读取与 ReviewRecord 输出契约，并分别保留真实审阅接入证据；切换只影响后续任务，不能把一个后端已通过当作另一个已验收。
- [x] 宿主核对材料指纹、依据引用、必需字段及阻断问题处理证据；坏结构、无法核实的必需项、超时或取消准确呈现，文字赞同或两个后端一致不能覆盖缺口。
- [x] 自动验证结果、review_status、实验完成状态和正式能力分开呈现；尚未到协议终点或缺必需检查时保持初步结果/未完成，不能因技术审阅生成成功就声称真实验证已结项。
- [x] 协议已结束且自动验证与审阅材料完整时，FAIL 或 INCONCLUSIVE 也可形成完整验证交付；导出包保留输入、代码/数据/协议指纹、全部尝试、结果、异议与局限，正式能力继续关闭。
- [x] 页面、验证包和资格说明如实标注“未经人工独立复核”；不要求专业人士签字，不把模型审阅称人工独立复核，不增加多角色金融裁决或 Agent 自签工具。
- [ ] 经 FastAPI 应用入口和真实持久化验证结果/缺口及导出可追溯性，补关键网页流程；将两个后端真实调用、固定输出重放和工程 FAIL/INCONCLUSIVE 样例分别留证。真实协议终点交付在 33 进行。
- [x] 遵守目录与实施约束；仅引入本票实际需要的模块、接口和校验，保留 PRD 必需控制，不新增假设性兼容层、审批或泛化框架。

## Comments

2026-10-07：按已确认拆分发布；尚未实施或验收。

2026-10-08 本轮依赖前沿核查：未启动本票。21验证与13双后端隔离未完成。保留原分诊标签和全部验收要求，不用合成样例关闭任务；实际解锁后继续。整体执行证据见[实施记录](../execution-status.md)。

2026-10-11：21 独立验收后已按顺序实现本票本地部分，Completion partial，Status ready-for-agent 保留。最终 API/SQLite 39项345.47s通过，浏览器1项56.6s、构建58模块2.00s通过；固定输出/真实SDK合成loopback与宿主终点FAIL/INCONCLUSIVE分别留证。12个19依赖源码未改，无新拟合、预算/SEALED/实际前向。完整收据见[23验收](../evidence/23/acceptance.md)。

实际 CODEX 和 DeepSeek 此批具体材料外发被自动审批审查拒绝，尚待用户明确授权，0次实际外发；不把本地worker/loopback作为两个真实后端验收。可长期点击的[根审批清单](D:/dsh-proj/Roll/.roll-data/implementation-evidence/23/provider-approval/provider-material-manifest.json)与worktree待审清单/packet同SHA。实际一致副本和浏览器640文件保全在根`.roll-data/implementation-evidence/23`，凭据文件排除，0差异。获批后从集成根执行本票接续脚本，核固定packet并分别一次真实调用；详见验收缺口。本票第2/7项及AT-51未完成；真实终点统计由33承担，当前actual诊断仍preliminary FAIL且NOT_GRANTED。
