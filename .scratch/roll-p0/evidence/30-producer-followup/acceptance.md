# Ticket 30：有限历史 SSE producer 离线续推

本轮沿已存官方原件实施可行内部前沿，Completion 仍 **partial**。没有新 HTTP/provider 请求、训练/拟合、SEALED、实际模型/前向或能力调用；没有读取 root SQLite/账户，也没有打开上一轮保全 SQLite 副本。当前代码提供历史来源事实与具体缺口，不提升当前输入或正式资格。

## 原件和实际接口

只复制既有 compact manifest 指名的 6 份官方公开原件到 `backend/src/roll/market/reference/sse-history`，合计 **360,501 bytes / 0 SHA或长度差异**；见 [复制收据](source-copy.json)。这不是新增采集，原件的 HTTP receipt 都在 2026-10-09；同源单位JS、停牌查询JS与 response 分别保留 SHA。新增专用 `.raw binary` Git 属性，6 个 staged Git blobs 另验原 SHA/长度通过，避免 checkout 改写原字节。

默认 sandbox 首次对 root 已知公开路径返回不存在；仅升级读取固定 daily SHA 后，HOST 确认该路径实际存在并读到 1160-byte 原件。该情况是可见性诊断，不是来源丢失、迁移或外部等待；后续只读取/复制 6 个指名 SHA，没有扫描原19全部 raw。

- `POST /api/research/collections/{plan_id}/sse-history-assessments`：固定 `SSE:600362` 离线 assessment，命令只有 basis；没有客户端路径、日期、REAL、complete/PASS 标志。原 `received_at` 与本次 `normalized_known_at/available_at` 分列，publication/correction chain 未证实，`historical_pit_claim=false`。
- 官方 daily 原行是 2025-12-31 O/H/L/C **50.25/55.28/50.24/54.92**。只按该 `commonQuery` 统计自身官方 JS 的 A股/万股/万元分支映射 **128845200.00 shares / 7005041400.00 CNY**，金额原粒度 100 CNY。`HISTORICAL_DAILY_ASSESSMENT` 保持独立，`model_daily_input_allowed=false`；不把此单位借给不同的 yunhq board。
- 官方停牌 response 只归一化600362的 returned event：报告2016-02-16开始、2016-02-26结束边界，`STOP_DATE='-'`、原停牌说明及原因保留，`resume_date=None`、发布时间未知。**78/78**、page1/pageCount1 只证明那次单日有限查询返回完整，不证明当前状态或2013—2025全期。
- 新停牌接口 **0 returned / 10 total** 与 request100/response1000 page-size 差异分别列名；早期2013-01-04 daily `result=[]` 只是未取得行，不能推断无交易/停牌。所有 raw、请求范围、计数和 unknown/no-event 限制进 query audit。
- 已有 PostClosePackets 包包含独立 `historical_source_assessments`，历史事实不进入当前 DAILY/STATUS 候选；重放固定原 assessment IDs、原归档及全部原件/单位依赖，不重新选择相同 cutoff 后新增记录。parser/manifest fingerprint 参与既有 successor 绑定，不改旧冻结或计划。
- `GET /api/research/collections/{plan_id}/source-gaps` 是只读查询，分别返回当前输入缺口、当前尚未适配的来源维度、有限历史 audit gaps 与绑定事实，不隐式采集、写 packet 或启动真实时钟。

## 检查收据

1. daily route 缺失 valid red **1 failed / 6.16s** → 首次离线注册/包/重放/query **1 passed / 7.12s**。
2. 缺停牌事件 valid red **1 failed / 7.16s** → daily+停牌 **2 passed / 11.58s**。
3. 缺0/10 audit valid red **1 failed / 5.73s** → 首次检查 **2 passed、1 fixture failed / 16.41s**：METHOD test 仅前移 post-close 时钟而 prospective 仍在实际时点，合法未来cutoff门禁返回422；没有改变宿主门禁。对齐两个测试时钟后 **3 passed / 17.24s**。
4. [8 个关联公共API案例](binding-check.log) **8 passed / 48.53s**：真实公开原件字段、有限分页/日期、单位JS/停牌JS/停牌response损坏拒绝、同cutoff追加不改变旧包，以及历史单位绝不能补全当前 METHOD yunhq 输入。
5. 本轮固定生产源码的最终受影响检查 [33 passed / 192.57s](final-tests.log)：新增8 + 既有 post-close16 + forward adapter/assessment9；真实 SQLite/归档、HTTP和具体隔离行为。前后15保护源码与6原件SHA/长度一致，见 `source-final-before/after.json`。本轮未变原 acquisition/forward OS事务，不重复或宣称新增 OS/浏览器/build 验收；前轮证据另存。
6. source commit `a382dc8` 后合入独立接受31的 integration `daeecb19a11f47dfe666aea45cb6beffc8216912`（app组合变更），最小公共API/独立worker/source-job与新history组合 [3 passed / 21.91s](composition-tests.log)；本轮 producer/manifest/test 未再改变，前后15保护源码与6原件一致，`source-composition-before/after.json` 保留实际组合版本，未把合入前33项说成合入后的全套。

所有新实际API运行目录均为本 worktree 自有 METHOD fixture，虚拟规范化钟只验证算法；原件真实身份只证明已收到的过去报文。没有在 root 启动应用、登记 actual forward_started_at、改 registry 或 grant。

## 新运行件追加保全

[主保全收据](runtime-preservation-receipt.json) / [逐文件清单](runtime-preservation-manifest.json)：**2,399 文件、323,286,747 bytes、SHA/长度差异0**，目标 root `.roll-data/implementation-evidence/continuation-ticket30-producer-followup`，仅包含本 worktree 的9个明确自有 `t30h-*` 测试目录。另留 [组合保全收据](composition-preservation-receipt.json) / [清单](composition-preservation-manifest.json)：**171 文件、31,451,719 bytes、差异0**，目标 root `.roll-data/implementation-evidence/continuation-ticket30-producer-followup-composition`，来源仅 `.scratch/t30h-composition`。

全部复制与核验都是 bytewise 文件操作，使用 Windows 扩展路径；没有 SQLite-open、读写原 root SQLite或上一轮13,989保存件、覆盖旧manifest、删除运行目录或worktree。本轮保全成功于新目标，两张收据列精确来源目录及隔离标志；后续独立验收应使用相同 bytewise 方式，若需分析DB/WAL/SHM应先复制到新的自有目录，避免任何读取副作用改变已保全版本。

## 仍需推进的内部前沿与实际依据

| 维度 | 已实现/实际事实 | 尚缺及下一最小步骤 |
| --- | --- | --- |
| 历史daily及单位/停牌 | 本轮6个固定公开原件的有限parser、source/hash/date/paging audit、包重放和查询已实现。旧返回不得作当前authority。 | 如需扩大历史范围，按预先限定的同来源原件逐件适配/验证；首次发布版本/修订链仍未取得。不能因此声称通用历史producer完整。 |
| 当前yunhq日线 | 原当前board parser/raw/sourcejob 已有；本轮未新增实际交易日原件，历史JS不是该endpoint单位依据。 | 当前endpoint单位、成交范围/完成语义仍待固定官方原件与实际交易日组合；公开资料未证实，不声称endpoint永久没有这些语义。 |
| 当前完整STATUS | 历史单日停牌事件已适配；当前 listing/relisting、适用风险子类型、完整停复牌/除权来源组合未实现。 | 来源 routes/parsers/覆盖审计是可继续的内部工程；报告 end boundary 不等于复牌或普通上市状态，当前缺原件保持UNKNOWN。 |
| 公司行动候选/分页/修订 | 上轮已实现14已知cash PDF精确映射与原件绑定；本轮只读 tracked `rights-public--manifest.json`，8个keyword query 均为 **2013-01-01~2025-12-31**，没有2026区间。 | 已知CNINFO历史candidate/paging schema 是明确可实施的后续有限前沿；本轮未适配，不归为外部-only等待。该旧区间不能证明当前行动完整/无事件；当前区间、旧未结义务、分页/修订/取消、所有类别audit仍需实际来源和内部producer闭合。 |
| 完整组合、冻结及前向 | 当前源conflict/time/ordinal/原件消费规则继续有效，SOURCE_ASSESSMENT不满足REAL current输入。 | Ticket30第一项仍未闭合，不自动解锁31/32真实完成；真实完整组合、合格冻结/合法检查点与首次持久化须各自留证，资格保持NOT_GRANTED。 |

父任务拥有 root status/trace/README，本 worktree 只更新 issue30、专用验收及源代码。独立接受后再分批推进 CNINFO 历史candidate/paging，不把已有schema未实现写成用户配置等待。
