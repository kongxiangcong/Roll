# Ticket 30 · 14 known notice obligation audit

基于独立接受的 CNINFO batch `479460f73224bc4959112cf45bf98b33addcccee`。仅复用已映射14份官方现金实施公告、原字段映射、现存官方2026日历及隔离METHOD协议元数据。**Completion仍partial、第一项未勾选，没有真实前向起点或资格变化。**

## 接口与共同消费者

- `POST /api/research/collections/{plan_id}/known-obligation-audits` 只接受protocol_id/basis，要求已登记600362及design的20-session horizon；DRAFT缺设计拒绝，caller cutoff/current/actual/complete/resolved旗标拒绝。
- SQLite追加audit ID，原件先归档；同路径GET支持protocol_id筛选，核验audit、protocol reference、calendar、cash mapping与14 notice的原SHA/长度。
- `PostClosePackets.inputs()`、包与source-gaps消费本审计，行绑定audit IDs与具体未知履行缺口。旧包重放固定原IDs，同cutoff追加不能重选，包括原空列表。
- `ForwardArchive.rows()`只读取匹配protocol与cutoff reference日期的audit。只读消费者测试使用空source输入和METHOD审计，没有登记forward、调用模型或持久化sample；损坏其他协议audit不污染所选协议，所选audit损坏拒绝。

## 原时点与窗口

[最终公开API原归档的14项证据](known-notices-proof.json)保留公告ID、PDF SHA/bytes/URL、原字段页定位、cash mapping SHA、record/ex/scheduled payment日期（DATE精度）、原publication precision与received_at。first-availability未知保持null，不用索引时间或本次登记造历史PIT。

`protocol_effective_window`是design评估/执行的reference window，绑定protocol fingerprint、design hash、horizon与calendar SHA，**不是新确认性/自然月检查点**。METHOD cutoff `2026-10-12T15:06:00+08:00` 的20个未来交易日终点为`2026-11-09`；官方日历SHA `7ea10c16202c4748f0ad5bcdfe6ee07b85b5462589504604b17c9d63865e7d8c`。POST_CLOSE_1505_SHANGHAI只是参考元数据，不登记统计look或实际forward起点；原calendar fetched_at必须≤cutoff。2026-12-31后缺2027日历时end=null、future sessions=0、calendar UNKNOWN gap保留，没有猜工作日/自然天终点。

14份旧付款安排均在上述METHOD cutoff之前，分类OLDER_SCHEDULE_WITH_RESOLUTION_UNKNOWN，不表示仍欠付或已履行。付款日期不能证明到账/权益归属/取消/延期/resolved，全部状态UNKNOWN、resolved_at=null、履行类证据数组空、actual owned amount/receipt=null。confirmed_pending_count=0不表示无pending。没有account cash event。`pending_older_obligations_complete=false`、`complete_action_coverage=false`，14known集合不能封成全部旧义务；原cash event和冻结映射未改。

## 实际TDD与固定源码验证

| 阶段 | 实际收据与含义 |
| --- | --- |
| window接口 | [valid red](window-red.log)1 failed/7.57s，接口404。[首次实现](window-green.log)1 failed/7.86s，calendar at/date契约用错；改为日期查询，独立验证source fetched_at，未改rules保护。 |
| packet消费者 | [原attempt](consumer-red.log)1 failed/8.05s，未检查失败的audit前置，不称valid red。补前置后[corrected red](calendar-corrected-red.log)1 passed/1 failed/14.27s，audit成功但packet缺字段；[green](consumer-green.log)2 passed/15.67s。 |
| protocol query | [首次夹具](protocol-red.log)1 failed/16.76s，未关联predecessor触发既有重复区间保护，不称产品red。修正公共API前置后[valid red](protocol-corrected-red.log)1 failed/9.14s，查询未筛协议；修正后[关联API](binding-green.log)10 passed/62.23s，含五类原件损坏、缺2027日历、旗标/DRAFT拒绝、旧空IDs固定。 |
| forward只读消费 | [1 passed/8.13s](forward-binding.log)，明确不是实际FORWARD调用/授权或完整正向样本。 |
| 当前固定源码 | [31 passed/174.91s](final-tests.log)：新11+既有post-close16+SSE/CNINFO各一组合+prospective asof/failed2。7个本轮source/test [before](source-final-before.json)/[after](source-final-after.json) SHA/长度相同，15保护Git blobs与market reference相对accepted base无diff。 |

未训练、读SEALED、新HTTP、实际model/registry clock/forward/grant；没有UI或OS事务改动，不重复旧40套、benchmark、browser/build、OS故障轮。fixture日期明确METHOD，只证明接口/归档语义，原PDF/public源事实不等于当前实际完整输入。

## 精确剩余前沿

| 消费字段/本轮已实现 | 内部未实现与来源限制 |
| --- | --- |
| pending_older_obligations_complete：14known schedules的protocol窗口、cutoff、逐notice审计与共同消费者已实现。 | 全部旧有效义务覆盖producer、具体履行/取消/延期→原义务绑定、pending/resolved消费者仍未实现。现14 PDF仅实施安排，无账户履行/完整旧义务清单/版本链；不得由付款日推断。下一步只消费明确指名原件和字段定位，没有本体/语义保持UNKNOWN。 |
| covered_effective_interval/complete_action_coverage | 当前有效区间全类别请求/实际分页/范围caller及覆盖消费者未实现。固定CNINFO keyword仅2013—2025/24候选，缺当前范围/全类别及官方分页语义；按实际原请求/返回receipt逐项实现，keywords/2 of 2/totalpages0不能封complete。 |
| pagination_and_revision_coverage/lifecycle_stage/event_identity | authoritative修订/取消/取代链→canonical event/obligation关联和固定原版本消费者未实现。现关联ID/title仅clue，缺具体关联公告本体、字段/文本定位、发布/首次可得与版本链，不能猜取代或删除旧cash事件。 |
| 当前STATUS/listing/risk/stop-resume/ex-rights | 有closing名称/交易线索、历史单日停牌parser；当前官方区间caller、适用listing/relisting/风险子类型及ex-rights权威route/parser/覆盖组合未实现。历史reported end date不证实际复牌，有限未返回不证正常。 |
| 当前yunhq单位/成交范围/完成 | raw-first capture已实现，该endpoint自身单位适用证据与当前完整组合尚未取得/适配；旧daily JS单位不能借用，不声称endpoint永久不提供。 |

不是用户通知配置等待；内部路径与required source分列。下一最小可执行slice见[next-slice.md](next-slice.md)，本批不追加源码、网络或扩大31案。

## 新运行件保全

[主收据](runtime-preservation-receipt.json)/[逐文件清单](runtime-preservation-manifest.json)：**2749 files/403639159 bytes/0差异**，来源仅本树12个新`t30o-*`目录，目标root `.roll-data/implementation-evidence/continuation-ticket30-known-obligations`。bytewise/Windows扩展路径，没有SQLite-open、旧manifest覆盖或worktree清理。没有打开/写旧13989/2570/2657保存件、旧SHM恢复证明、实际root SQLite/账户；后续分析DB须先另复制到新自有目录。own final API raw archive抽取也没有SQLite-open。Root status/trace/README由父任务维护。
