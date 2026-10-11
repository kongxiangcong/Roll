# Ticket30：固定 CNINFO 历史候选与分页审计

本轮只推进已有原件支持的有限内部 producer，Completion 仍 **partial**，第一项不勾选。没有新 HTTP/provider 请求、拟合、SEALED、实际模型/前向、registry/能力调用；没有读取 root SQLite/账户或打开此前13,989与2,570个保存件。用户通知配置不是本票内部缺口原因。

## 来源及已实现接口

从既有 tracked `rights-public--manifest.json` 指名的8次查询中，只读取并复制6个唯一公开 raw SHA，合计 **17,848 bytes / SHA与长度0差异**；不扫描原19全部raw。原件的真实 HTTP receipts 是2026-10-09，全部请求均为 `600362,gssh0600362` / `2013-01-01~2025-12-31` / page1 / size30。原full manifest SHA来自该compact收据声明，不称本轮重读或重新核验full manifest；compact本身和原件实际SHA记在新映射及[复制收据](source-copy.json)。默认sandbox对已知忽略路径的可见性问题由固定公开路径HOST读取解决，不归为来源丢失或用户等待。

- `POST /api/research/collections/{plan_id}/cninfo-history-assessments` 只有basis命令，固定SSE:600362，离线注册独立 `CNINFO_HISTORY`。实际返回24行/24个唯一公告候选，8个query audits与6个source hashes。原row、SHA、query ID、ordinal、原received_at及本次available_at分别保存。
- `totalAnnouncement`、`totalRecordNum`、实际returned/unique count、hasMore与totalpages原值进入audit。实际停牌查询 **2/2** 但`totalpages=0`；保留 `returned_count_matches_total=true`，`finite_query_completed=false`与`CNINFO_PAGE_COUNT_SEMANTICS_UNPROVEN`。注销/送股/配股共享空报文也不证明无事件。
- `announcementTime` 保留原opaque值，例如1224816852的 **1763654400000**；`index_time_precision=UNKNOWN`、`published_at=None`。URL中的2025-11-21仅是source path定位日期，不冒充出版/首次可得，也不以索引字段建立历史PIT。
- `associateAnnouncement`及标题修订/取消关键词仅进入clue audit，生命周期解释、修订/取消覆盖保持UNKNOWN。例如1201981143关联1201981166，但后者未返回；不能据此断定取代、取消、正常状态或复牌。
- 与原14现金PDF映射按**公告ID+相同官方PDF域/日期路径**精确关联13个候选，输出原PDF SHA/bytes/page locator、原cash mapping hash及candidate raw locators；不使用相似标题。1224816852对应原PDF SHA `e486d0e9a99e5aa0dc77a4aa2037963022a44a1d3f6cd3315290b8e6afe2a28c` /145503 bytes。原映射已知1202538463未被这组关键词返回，作为命名gap保留；PostClosePacket依然保留全部14个独立known cash事实，不删除第14个、不改原freeze或mapping。
- 复用已有具体SQLite assessment表、PostClosePackets、只读`source-gaps`和离线replay，SSE与CNINFO两个有限family分别验证原件。包固定原assessment IDs，后续相同cutoff追加不能重选；原index/mapping/PDF损坏拒绝重放。新parser与映射加入既有source fingerprint，旧source-bound计划需要successor，不更新旧记录。
- 历史候选不加入当前DAILY/STATUS输入。当前完整行动、旧未结义务、no-event与revision coverage继续为false/UNKNOWN，forward_started_at不因历史审阅启动，资格NOT_GRANTED。

## 验证记录

1. 缺route的有效red [1 failed /6.34s](index-red.log) → [1 passed /7.24s](index-green.log)。
2. 缺精确cash links的有效red [1 failed /6.60s](cash-red.log) → [2 passed /13.22s](cash-green.log)。
3. 新关联公共API [7 passed /42.44s](binding-check.log)：真实固定原件字段、opaque date与分页保守解释、现金精确链接与未返回项、index/mapping/PDF损坏拒绝、mixed family原IDs固定及caller complete flags422。
4. 固定源码最终受影响 [40 passed /222.29s](final-tests.log)：新增7+既有SSE8/post-close16/forward adapter与assessment-binding9。15保护源码及SSE6/CNINFO6原件前后一致，`source-final-before/after.json`；[6个新staged Git blob](staged-originals.json)逐字节核验同原SHA/长度，使用专用`.raw binary`属性。
5. Source commit **e984edb46707b82b7fe86010f441fa07e1cf001f** 后合入accepted ticket25 integration **371dd9c7c75d1fb5df9827a81dc580ddd5a62c63**。首次组合collector [2.47s环境失败](composition-collection-error.log) 是test_actions所需测试support目录未加入PYTHONPATH，无案例执行、无生成basetemp；诊断保留，不称产品red或通过。
6. 合最终accepted runner integration **ed936ce56ccdeacfb2f35a0fa81cbb9dc3ed3bab**，own merge **9327e2cc00941703a490fec8b590c869a73bb863** 后，加入own `backend/tests/support`导入路径，最小组合 [4 passed /27.25s](composition-tests.log)：CNINFO route+source gaps/replay、SSE/CNINFO混合原IDs、独立worker/source job、25ungranted caller。15保护源码、SSE6/CNINFO6及本轮own source前后相同，`source-composition-before/after.json`；初次未执行collector前的metadata另存`source-composition-initial-not-run.json`。没有重复整套40、benchmark/browser/build，未将合入前40项称为合入后的完整轮。

本轮测试的规范化时间是明确METHOD可控钟，只验证接口/归档语义，不能称宿主真实当前归档或前向。没有UI改动，不宣称新browser/build/OS故障验收；原已接受OS事务未改，不重复无关整套。

## 新运行件保全

[主收据](runtime-preservation-receipt.json)与[逐文件清单](runtime-preservation-manifest.json)：**2,439文件 /346,346,030 bytes /SHA-length差异0**，来源仅本worktree6个明确新建`t30c-*`目录，目标root `.roll-data/implementation-evidence/continuation-ticket30-cninfo-history`。bytewise复制/核验使用Windows扩展路径；没有SQLite-open、旧manifest覆盖、worktree清理或删除。后续验收同样应逐字节读取；分析DB/WAL/SHM时先另复制到新的自有目录，保持保全件不可变。

[组合收据](composition-preservation-receipt.json)与[清单](composition-preservation-manifest.json)：**218文件 /35,055,992 bytes /差异0**，来源只`.scratch/t30c-composition`，目标root `.roll-data/implementation-evidence/continuation-ticket30-cninfo-history-composition`。所有test命令均已退出；未启动独立后台服务。两批合计 **2,657文件 /381,402,022 bytes /差异0**，不含此前保全件。最后合parent docs-only tip **c2bf9313ce8937dadea01b68b05396ed57a4f1f5**，其product/config未变，不再重复检查。

## 确切剩余前沿

| 维度 | 已有接口与事实 | 内部未实现与来源限制 / 下一最小步骤 |
| --- | --- | --- |
| 有限历史CNINFO候选 | 本轮固定8keyword/6raw/24candidate及原count、请求范围、clue、13精确cash links已实现。 | `totalpages=0`解释、日期过滤语义及associated IDs原件仍不足；不能从2/2或hasMore=false造complete。后续只在明确官方schema/固定来源证明支持时补相应有限audit。 |
| 当前公司行动 | 14known cash PDF原映射继续独立支持已知实施公告；历史关键词没有2026范围。 | 当前区间及全类别候选/实际分页、修订取消生命周期、旧未结义务producer尚未实现，相关当前范围/版本/first-availability原件也未取得。需先取得明确范围/来源证据，再适配具体route/消费者字段；不是用户配置等待。 |
| 当前完整STATUS | 已有current closing原件/冲突消费者及历史单日停牌事实。 | listing/relisting、风险子类型、完整停复牌和ex-rights的权威route/parser/覆盖组合仍未实现，现固定历史原件不足以推导当前正常。按具体官方schema推进，缺项保持UNKNOWN。 |
| 当前yunhq DAILY | 有界raw-first采集/日期与收盘校验、job恢复及输入消费已有。 | 该endpoint单位、成交范围/完成与当前完整组合尚无充分固定证明；不能借旧SSE daily JS单位。需要该endpoint自身资料与合法实际交易日完整组合证据，不能声称endpoint永久不提供。 |
| 真实完整输入及资格 | 历史assessment/包/重放/缺口查询工程通过；未动核心数学/冻结。 | Ticket30第一项仍partial；32实际首次合格持久化与33真实终点各自留证，不能由METHOD或历史索引触发计时/授权。 |

Root status/trace/README由父任务维护，本轮只提交本票source/tests/issue30与专用证据，留树待独立接受。

后续行动相关接口缺口分项如下，均尚不能从本历史包产生当前PASS：

| 所需事实/现有消费者字段 | 明确尚未实现的内部caller/消费路径 | 必需来源与下一有限slice |
| --- | --- | --- |
| 当前请求区间与全行动分页：`covered_effective_interval`、`complete_action_coverage` | `PostClosePackets.inputs()`仍调用known-only `cash_inventory()`；没有绑定当前区间原请求/返回分页/类别清单的当前producer及其消费路径。旧`cninfo_payload()`固定2013—2025，不承诺当前caller。 | 对具体官方current issuer范围建立有界原请求/返回receipt，并核验pageNum/returned/total/hasMore以及官方分页语义；关键词选择本身不足证明全行动类别。下一slice按实际原件实现有限当前query audit，缺语义保留UNKNOWN，再按有证据的类别逐件接消费。 |
| 修订/取消/取代：`pagination_and_revision_coverage`及事件`lifecycle_stage`/`event_identity` | 当前没有将authoritative revision/cancellation链链接到原canonical event、重放固定原版本并检查旧新义务的producer/consumer。clue audit不承担该路径。 | 需要关联公告本体、明确修订/取消字段或文本定位与发布时间/首次可得/原ID版本链。优先消费指名关联ID的固定官方原件；缺本体或语义时仅clue UNKNOWN，不删除原cash事件或猜supersession。 |
| 旧未结义务：`pending_older_obligations_complete` | known-only inventory固定false，没有依实验/检查点effective window把旧record/ex/payment/取消/延期及履行状态逐项核对的caller与source-bound obligation审计。 | 需要覆盖窗之前仍有效义务的明确原件范围、事件链与可证明履行/取消/延期事实。先对已映射14known notices建立限定known-obligation audit，不能从公布的payment date推断实收，也不能将14known集合封成全部旧义务。 |

上述是内部后续实施项与required source的区分，不把adapter/消费者未写统称外部等待；本批先独立验收，不同时扩展范围或降低current准入门禁。
