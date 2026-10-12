# 2026-10-11 当前后端范围：仅 Codex

用户明确批准将修复后材料指纹 `95ddbd52fa7f4e2df78b97556f36c6c675da75603eb290ec5ecab260abfbfba1` 发送给 OpenAI Codex 执行一次真实技术审阅，并明确“deepseek暂时不测试，后续也忽略deepseek能力”。本修订覆盖 PRD、规格、任务计划和追踪表中原来要求当前双后端交付/切换/独立验收的内容。

- 当前取证与模型技术审阅的交付后端仅 CODEX。DeepSeek 不执行真实调用，也不是23及后续 tickets 的完成前提。过去12/13的实现、失败、成功与切换证据保留为历史，不能把此次排除标为新的 DeepSeek 通过。
- 当前23须在获准的准确材料上，沿真实 Codex SDK/runtime 和宿主材料读取/复现契约完成一次实际审阅，保留模型/配置/工具/指纹、异议、处理证据和局限。固定worker与本地loopback不能替代真实 Codex。一次失败仍保存失败，不自动重试获取期待结论。
- 同意意见不是资格证据。实际当前 G4/G5 FAIL、其余 INCONCLUSIVE 及 NOT_GRANTED 保留。23完成表示本票工程与真实当前后端接入完成，不表示33实际协议终点完成、G1—G7 PASS、34正式启用或人工独立复核。
- 后续24—34沿原依赖顺序与证据边界推进；所有原 DeepSeek/双后端验收条款在当前范围中记为排除，真实 Codex 的权限隔离、取消/失败、运行配置固定、可追溯性仍须验收。将来若重新启用 DeepSeek，需要新的明确范围与该后端独立证据；当前不实现这一未来路径。

授权具体材料：新材料 `b27b0047-d0ef-4c39-8d8d-46ad20becc74`，7份正文179889字节；精简正文、复现及命令清单 SHA256 `206d2ec53d85af4b28423017da24b5a6030d5078ec5237ee939233245ef84984`。[根清单](D:/dsh-proj/Roll/.roll-data/implementation-evidence/continuation-review-fixes/provider-approval-current/provider-material-manifest.json)。目的地为 OpenAI Codex runtime 的 SDK endpoint，模型 `gpt-6.1-sol`；DeepSeek不获此执行授权。旧35e42…材料及旧双后端helper保留历史，不能误用本次批准。

此次范围变更不改数据/统计/资金/账户/恢复门槛，不读SEALED、不拟合、不创建真实前向起点，不授予正式能力。批准包中的五份源码和本文档变更分离，执行前仍核精确材料及源码指纹。完整原始输入、账户资料、数据库、SEALED、凭据及无关文件不得外发。

当前宿主及界面范围检查已合入 `8497fead9faa908dfa831a89d042f6aa3b35dfb4`，独立收据提交 `1c90c6edf2671b5095a649680ca04038dd0f26d0`。新设置、取证及技术审阅在查询凭据或材料、创建运行之前拒绝 DeepSeek；旧设置如实显示并要求用户显式保存 CODEX，历史运行读取与取消继续可用。独立三项公共 METHOD 场景实际退出0，包括旧版本幂等/冲突、历史活 owner 查询/取消，以及新部署拒绝旧 METHOD 资格证明。没有 DeepSeek runtime 调用、模型拟合或实际资格签发；历史真实 ReviewRecord 不变。详见[独立验收](evidence/continuation-2026-10-11/codex-only-independent/acceptance.md)。
