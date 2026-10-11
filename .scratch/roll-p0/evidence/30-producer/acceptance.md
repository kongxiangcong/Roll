# Ticket 30 producer：原件、版本与输入缺口

本轮在独立 worktree `codex/roll-p0-ticket30-producer` 实施盘后原件采集、输入包与真实消费者校验。Ticket 30 保持 **partial**：已实现有界 HOST producer、持久化任务、失败回执和离线重放，但尚无完整当前日线、上市状态和公司行动覆盖证明。未登记真实前向起点、未赋予能力、未触碰账户资金或 SEALED；未调用模型或 DeepSeek。

## 实现与适用边界

- 固定 SSE `yunhq` closing-board 原始响应，单次匿名请求，15 秒超时、8 MiB 解码上限、无重定向/自动重试。只适配 `SSE:600362`，原件先归档，日期、收盘时间、OHLC、数量及金额的有限数值校验后才生成部分事实。没有客户端日期、完整性或 REAL/PASS 覆盖参数。
- 既有 worker 在真实前向合法前置满足时使用同一持久化 source job。重复触发不新增采集；真实子进程在原件后及提交前停止，重启保留 INTERRUPTED、零事实批次、原件和具体缺口，不隐式重试。METHOD supplier 始终保持 METHOD，不能开启真实时钟。
- 输入包保存实际可得时间、原始 SHA、所选事实的原 ordinal/batch、全部状态来源、原采集回执和执行规则原件。离线重放验证原批次而非重新选择 cutoff 处最新值；同 cutoff 后续更正保留旧包。失败回执永远保留，明确后续成功采集只清除当前活动失败缺口。SQL/Parquet 同时改写事实仍不能覆盖原 closing 响应。
- Decimal 比较数值相等的量价/金额，保留真正差异及单位/范围冲突；禁止“最后一个 STATUS 胜出”和客户端 complete-status 枚举。现金事件必须绑定原公告及既有精确字段映射、登记/除权/支付日期、可得时间和生命周期，不能只提供一个原件 hash。
- 已有 14 份 CNINFO 现金实施公告保留原 SHA/字节与 gross entitlement、差异化除权参考扣减、税项的分别映射。此有限已知事件清单没有当前完整覆盖、修订/分页/无事件权威或账户到账证明，输出明确 UNKNOWN。
- `forward.py`、producer 与 prospective 源码共同绑定 successor source fingerprint；不修改旧计划的绑定元数据，不以新源码替换旧 freeze。

## 真实公开原件

仅执行一次匿名 **SOURCE_ASSESSMENT**，见 [真实回执](official-source-assessment.json) 与 [原始响应](originals/100af352fe6f66c87b18310e26f01b5eb41d932a68e27a094f87a906f78ec5ab.raw)。2026-10-11 02:45:17 UTC 实际收到 HTTP 200、193804 字节；SHA `100af352fe6f66c87b18310e26f01b5eb41d932a68e27a094f87a906f78ec5ab`。响应报告日期 2026-10-09、时间 16:29:05，600362 唯一 9 字段行，原数值 41.4500 / 42.6600 / 41.0600 / 42.5100、volume 31419158、amount 1314805240。星期日收到星期五报文，不能作为星期日当前日线或补写星期五预测。此 endpoint 的数量/金额单位及成交范围尚未独立证实，程序保留原 reported 值，转换值为 UNKNOWN，`model_daily_input_allowed=false`。

## TDD 与检查收据

- 最初默认 sandbox TestClient shutdown 挂起，无有效断言结论；中止的 `t30p-red1` 留存为诊断，不能算 red。同案独立 green 为 1 passed / 8.06s。
- 假 complete-status 证书公共 API：1 failed / 8.14s → 1 passed / 6.86s；Decimal 等值金额：1 failed / 7.41s → 当时 producer 9 passed / 45.22s；现金原件清单：1 failed / 6.64s → 1 passed / 7.54s。
- 较早 source/adapter/assessment 合计 19 passed / 99.97s。后续 final 2 为 34 passed、1 fixture failed / 331.04s（原件精度 expected 41.45 与实际 41.4500）；修正预期后同原件案例 1 passed / 1.50s。上述均为当时源码收据，不与最终轮相加。
- Source job：缺失 route 1 failed / 6.95s；子进程最初错误故障环境名为 fixture timeout / 31.67s；修正环境后缺失原件后故障点 valid red 1 failed / 31.62s；实现后持久化 job 与两个真实 OS 子进程恢复 3 passed / 30.68s。
- [Final 3](final3-pre-repair-tests.log) 在 replay/回执补修前固定源码 49 passed / 416.49s，前后源码收据一致。之后旧包同 cutoff 更正 valid red 1 failed / 9.82s → 1 passed / 8.04s；输入包漏失败回执 valid red 1 failed / 9.03s → 含重放案例 2 passed / 14.39s；独立“失败后明确成功、旧包仍重放”回归 1 passed / 9.75s。
- [Final 4](final4-pre-scope-repair-tests.log) 固定源码 51 passed / 416.38s，前后源码收据一致；包含公共 FastAPI、真实 SQLite/原件/Parquet、两个 source 和既有 forward OS 故障、既有 prospective 更正/as-of 与 CNEquity 源级回归。随后历史采集失败成为永久当前拒绝 valid red 1 failed / 8.73s → 限定当前上海日期 1 passed / 8.13s；全部历史回执和旧 cutoff 重放保持。最终当前固定源码的受影响 producer/forward adapter/assessment-binding 轮 [25 passed / 127.79s](final-tests.log)，前后源码一致，不重复未变的 OS 事务检查，也不将此前 51 项说成这次最新源码的完整轮。所有新正向 supplier 均 METHOD；真实 OS 进程不表示真实预测已启动。
- 未更改前端，未声称新增浏览器或 build 验收。原始 19 SQLite 仅 checksum 读取，仍为 `ec46257c4420f69c245791778c49079355700615cc3ed7b94d8027bd4dcf66c4`；12 个冻结19来源/参考与另 3 个已验收 validation/shadow/statistics 源文件与 root SHA/长度一致。最终前后 [源码收据](source-before.json) 及 after 收据验证固定源码。
- 合入 accepted CODEX-only source `1c90c6e` 后仅补两条 app route 组合检查：[2 passed / 13.82s](composition-tests.log)，producer/source-job/capture/离线重放均保持；再合 docs-only `25a956c` 与 cleanup receipts `0c9802e` 不重复测试。25 项固定轮源码收据另留 `source-final5-before/after.json`，组合轮另留 `source-composition-before/after.json`。

## 运行件保全与交接边界

[主保全收据](runtime-preservation-receipt.json) 和 [逐文件清单](runtime-preservation-manifest.json) 记录 13,891 文件、1,269,967,416 bytes，SHA/长度差异为 0；保全到 root `.roll-data/implementation-evidence/continuation-ticket30-producer`。前两次分别在 CopyFile2 长路径和正常路径读取处失败，不能算成功；第三次全部操作使用 Windows 扩展路径，重新核验先前已存在的 1,118 文件后续传，没有覆盖未知目标或删除原件。收据完整保留三次尝试及两个失败原因。

[独立组合检查保全](composition-preservation-receipt.json) 及 [清单](composition-preservation-manifest.json) 另记录 98 文件、16,859,917 bytes、SHA/长度差异 0，目标 root `.roll-data/implementation-evidence/continuation-ticket30-producer-composition`，仅包含本 worktree 的 `.scratch/t30p-composition-1`。主保全仅包含本 worktree 的 22 个明确自有 `t30p-*` 目录、匿名 SOURCE_ASSESSMENT runtime，以及 root 两个本轮产生的 `.scratch/t30p-red1` 和 `.scratch/t30p-green1`；精确来源目录以收据为准，不包含其他 root 未跟踪内容、配置、实际账户或私有档案。本轮没有删除 source/runtime/worktree，也没有写 root Git index；独立验收后的清理由父任务执行。原始19 SQLite SHA 在两张最终成功收据均保持一致。

## 尚未闭合的第一项

当前 closing endpoint 缺少自身单位、成交范围与完整日线证明；listing/relisting、完整当日停复牌/ST/风险警示/除权来源仍未全部适配为有覆盖权威的 producer；公司行动还缺当前区间、旧未结义务、修订/分页及无事件证明。已知现金实施公告不能填补这些维度。上述是明确的程序/来源覆盖与实际资格缺口，通知渠道的用户配置不是本票原因；不能用 METHOD、SOURCE_ASSESSMENT、客户端 complete 枚举或旧原件映射关闭第一项，也不能开启 32 的实际前向时钟。

具体接口边界：`PostClosePackets.capture()` 只实现固定 closing-board 获取，尚没有官方 suspension/listing 当前补充来源的 host route/parser；`inputs()` 输出已绑定的 suspension/risk 线索，但 `listing_stage`、`ex_rights` 与适用风险子类型的完整 source/coverage 组合尚未实现。`cash_inventory()` 已实现 **全部现有 14 原件在原 SHA 下的已审字段映射 producer**：登记/除权/支付、gross cash、独立差异化参考扣减、税项、publication precision、原 receipt/定位/lifecycle 和实际到账 UNKNOWN；每次核验 14 PDF 的原 SHA/长度，映射本身绑定冻结 `sources.json` 原 hash。它没有针对新候选公告的 PDF 自动抽取路由，也没有产出 `covered_effective_interval`、`pending_older_obligations_complete`、分页/修订/取消审计等当前 complete coverage；这些是明确的内部未实现接口/消费者字段，不能写成等待用户确认无事件。现有 14 文本和实施字段支持有限 producer，不支持完整当前 inventory 的逻辑理由已由原 manifest scope 与未知类别明示。历史 SSE daily/单位 JS、suspension 有可继续实施的有限原件 parser 前沿，但不能把其历史 source schema 直接宣称为当前 closing endpoint 单位/当前完整正常状态。

| 维度 | 本轮确切状态 | 下一最小步骤（本轮不新增联网） |
| --- | --- | --- |
| 同日日线、单位与成交范围 | SSE 9 字段 raw/parser 已适配；原响应没有单位、成交范围或 publication-complete 字段，相关 endpoint 权威语义未证实。收到的是星期五数据，无实际合法交易日的完整 closing packet；不是已证明源永久不提供这些语义。 | 只对本 endpoint 寻找并固定单位/收盘及成交范围的官方依据，再绑定下一授权实际交易日原件；不能借用另一个历史 SSE query 的万股/万元 JS。 |
| 停复牌、风险警示/ST 子类型 | closing row 的交易/名称线索已适配，source/date/hash 保留；完整当前停复牌、适用 ST 子类型与状态覆盖 producer 未实现。历史 SSE suspension 原件可以支持有限事件 parser，不能证明今天正常。 | 新增该已存官方 suspension 原件的有限事件解析与 total/returned 约束，再对授权当前区间取得同来源完整范围；风险警示名单需实际来源覆盖。 |
| listing/relisting 与特殊阶段 | closing raw 明确没有上市/重新上市日期及生命周期字段；当前 listing/relisting 官方来源 route/parser 尚未适配。用户 MarketDirectory 身份不能替代外部权威。 | 限定 600362 官方上市/重新上市事件来源与日期字段，归档并按已知交易日导出阶段，未知保持限制；不凭名称或长历史序列推断普通阶段。 |
| ex-rights、当前行动覆盖与旧义务 | 14 份已有现金原件和精确映射受保护并注册，可验证那些实施事件；当前发行人全候选公告、分页/修订、旧未结义务、无事件 authority producer **未实现**。bonus/transfer/split/rights/cancellation 等缺失不能称为无事件。 | 收窄到该发行人已有 CNINFO index 路径的候选/分页回执，连接有限实施 PDF 与生命周期解析，再形成当前区间及旧义务覆盖 audit；空查询、年度股份不变或 cash-only 清单均不能直接完整。 |
| 实际完整组合与冻结入口 | conflict/time/source/原 ordinal+batch 消费校验已实现；这些受限 sources 目前不能产出可准入的完整组合。真实冻结合格、合法预登记、规则、未来 20 session 与 21 contiguous lookback 仍是独立要求。 | 在内部 adapters 与实际原件闭合后，以 successor source-bound plan 执行一次共同实际用例；保留原冻结和旧 metadata，不自动解锁 31/32。 |
