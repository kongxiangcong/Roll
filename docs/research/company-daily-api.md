# 每日公司研究（07）

日常入口从现有持仓/关注有限名单选择证券，调用已有公司解析；歧义不默选，未登记时保留量价入口和明确缺口。公司与上市证券仍分开。旧新闻/财务公网适配范围仍只有江西铜业；其他公司可以读取自己的已归档资料和共享快照，来源不支持会明确显示。BSE证券仍能读取已有公司研究，旧BaoStock量价流程尚未适配。

`GET /api/company-research/companies/{company_id}/daily?snapshot_id=...`返回一个明确共享快照、关注理由、三类变化、下一验证事件、反证/未来失效条件、原始事实与材料日期。省略ID时选择当前公司快照，返回的ID/hash为本次固定依据；历史可指定ID重读。DAILY/REPORT核心相同。变化记录引用该快照及其父版；首次读取按固定pair幂等保存比较，不选择独立latest估值。价格/方法诊断明细保留在独立change-set入口。

估值始终按该快照固定的economic_review_id以`CURRENT_PRICING`读时重查。blocked/unreviewed/缺失时不展示可用价格区间，不遮蔽经营结论；其他资料、假设、历史拒绝与缺口仍可展开。模型的量价对照只是未验证解释，宿主校验其固定snapshot_id；它不能改写core、估值或概率。

## 现有worker与刷新

`POST /api/observation-updates/{instrument}/settings`新增`research_postclose`，保留原expected_revision/basis及各开关。`POST .../requests`新增以下命令，仍使用既有有界队列、取消、SQLite租约与任务查询：

```json
{"kind":"RESEARCH","idempotency_key":"unique-attempt","basis":"按需检查公司研究","refresh_sources":false,"retry_rejected":false}
```

默认**检查已归档材料目录，未执行公网核查**。财务/新闻每类取下一批最多20条尚未纳入记录；成功、逐条拒绝/失败及原件引用分别保存。失败记录默认跳过以继续处理后续批次，原缺口count/示例保留；`retry_rejected=true`显式重查失败或拒绝记录，不将下一批成功无新增解释成旧失败已解决。修正身份依据后也通过该入口重查关联拒绝。源级失败保留重试政策；手动archive-only请求可继续核查保存材料，不能借此绕过公网来源冷却。

`refresh_sources=true`只请求旧适配器已支持的来源，沿用来源启用、预算与实际完成时间缓存（新闻15分钟、财务当日）。PARTIAL/失败逐项保留，缓存读取不是本次公网成功。非支持公司明确`PUBLIC_SOURCE_SCOPE_UNSUPPORTED_FOR_SELECTED_COMPANY`。来源核查/材料年龄、经营研究依据与页面读取日期独立。

在线盘后仍是原15:05检查点、仅当前交易日；不补造离线采集。每个worker循环至多处理一个更新，队列上限100，FIFO；RESEARCH整体上限150秒，经营模型90秒/8次运行时操作/0来源工具调用，可取消并让出原任务链。移出名单的排队任务取消，不阻断另一公司。普通观察原45秒上限保留。

## 规范财务字段与冻结分析

材料导入与事实适配各有独立进度。每次另取最多20份尚未适配的旧/新财务材料，保存不可变适配尝试；已导入material不会因此永久失去补齐事实的机会。每字段固定幂等key，重试不重复生成事实。

只映射现有规范器白名单INCOME三字段、BALANCE三字段、CASH_FLOW四字段。逐项核对原JSON中同证券、报告期与原列的精确十进制值，不用float/亿元缩放。仅已确认YUAN/CNY/CONSOLIDATED、POINT_IN_TIME或YEAR_TO_DATE以及语义basis证明可进入Fact；UNKNOWN、缺值、缺原件、未知新闻期间继续保留材料和缺口。不把负债合计当有息债务、资产当经营资本或CFO当FCFF。语义证明不代表所有列已独立逐数对照发行人PDF；原来源gaps保留。Fact.page引用JSON行，table记录报表与原列；另列语义PDF hash/page，不混为同一原件。

新增可消费事实才冻结03输入并由现有受限CODEX执行一次经营分析；旧快照继续可读，发布仍由03引用/冲突/父版本规则控制。合法PARTIAL已发布的新snapshot同样绑定到本次观察，继续显示局部拒绝/PARTIAL；UNAVAILABLE/FAILED无新快照时保留旧core。无新事实不重跑经营模型，更不生成整篇报告。超过80事实或96KiB输入上限明确保留实际缺口，不截断后宣称完整。适配批次/剩余数、未解决材料口径、模型不可用和待提取材料均形成可见PARTIAL，不能变成“今日经营已验证”。

## 量价历史与恢复

`POST /api/assistance/runs`增加`instrument`；个股symbol/人民币单位与三指数角色分别映射。`GET /api/assistance/runs?instrument=...`隔离历史；旧无instrument记录显式legacy范围归SSE:600362。页面切换清空旧公司状态并防迟到请求覆盖。公司研究由宿主按固定快照直接渲染；模型只作综合解释，量价概率/探索回测资格标签不改变。

价格请求截止、实际价格末日、请求开始、证据包冻结知识时点、经营依据/生成时点分别保存。历史end_date只限定价格覆盖；今日取得研究不能倒填成当时可得PIT。原件现在进入既有EvidenceStore归档，随共享事实、适配尝试、快照、变化与辅助结果一同备份。早期07真实样例的legacy assistance-raw字节在恢复验收中按原hash/原receipt登记，原保存run/模型packet未改写。

本票不创建报告、ForecastBundle、Decision、CapabilityGrant、ExecutionIntent或账户事件，不触碰旧预算与SEALED。真实/合成结果、已知限制及复现命令见[07证据](../../.scratch/roll-research-valuation/evidence/07/README.md)。两个实际盘后周期仍留12票观察，不以人工时钟测试替代。
