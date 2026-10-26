# 公司身份与共享证据入口（02）

依据[共享合同](company-research-contracts.md)，第02票提供 `CompanyResearch(EvidenceStore(...))` 与 `/api/company-research`。这是研究资料边界，不写账户、正式资格或旧实验。模型、估值、日报和报告执行属于后续票。

## 使用与记录

先经 `POST /companies` 登记有依据的公司及其上市证券，再 `POST /resolve` 传入 `query`。公司身份稳定、登记更新追加版本；A/H证券保留各自交易所、代码、股类与币种。同名或裸代码多义时返回 `AMBIGUOUS` 候选，未登记公司返回 `NOT_FOUND`。不提供全市场公司目录，不默认推定搜索结果身份；现有A股身份如与登记名称/别名冲突则拒绝映射。港股映射仅用于研究，不进入现有真实账户证券名单。

`POST /materials` 接受 `MaterialCommand` 字段及 `content_base64`，只支持有界PDF、UTF-8文本和JSON，不接受服务器文件路径或待抓取URL。大小上限16 MiB。实际取得、可消费时间由宿主写入，披露时刻未知为null；报告期、单位、币种、合并范围、页码/表号分别记录未知字段。原件通过现有 `EvidenceStore` 登记，复用hash对应的规范归档描述；下载使用attachment/nosniff。材料校验是身份元数据、类型及字节完整性检查，不是事实真实性背书。

`POST /materials/from-source` 接受 `ExistingSourceCommand(company_id, source_type, record_id, fact_index=0)`，支持已归档的 `FINANCIAL_FACT`、`NEWS_FACT`、`MARKET_SNAPSHOT`。适配器只读现有权威记录和原件，不额外联网、不复制原来源事实库；保留来源记录hash与ID、原取得/可得时间和原披露精度。REAL_ACQUISITION才映射为PUBLIC_ACQUISITION，METHOD始终保留METHOD。财报保留POINT_IN_TIME/YEAR_TO_DATE/UNKNOWN，新闻按实际关联规则拒绝未经确认的公司关联，保留正文/列表取得时间、正文状态/错误及已有exact-content转载根。

`POST /facts` 追加版本，`GET /facts/{version_id}` 永远返回该版本。披露值与材料单位、币种、范围、期间不兼容时拒绝；派生/假设必须明确类别和依据，不隐式换算。重述显式引用 `supersedes`，冲突保留所有有效版本。`POST /conflicts/resolutions` 要求完整冲突引用和理由，旧值不删除、不覆盖。来源、结构及完整性检查不证明数值本身真实。

## 核查与分页

宿主调用 `check_source(CheckCommand(...), supplier)`；每个请求最多8个不同范围，供应器每范围最多20项。供应器返回既有来源 `ExistingSourceCommand`，或供离线验证的 `(MaterialCommand, bytes)`；后者固定标为METHOD_CASE。网络与worker的有界调度仍由既有来源执行器及后续07/08票负责，此入口不另建常驻线程。重复幂等键只读已有回执，不重跑来源；新尝试使用新键。中断尝试保存FAILED及需显式新尝试状态，已有原件保留。

成功且无新增只表示已核查范围未取得新证据；部分失败列具体完成/失败范围，失败不刷新对应范围的最后成功时间。相同来源原件与口径在新采集回执下重用原材料，核查另保存source_receipts，不凭新采集ID增加独立经营证据。

`GET /companies`、`GET /companies/{id}/materials|facts|checks` 返回 `total/limit/offset/has_more`；按offset逐页读取。材料上限每页200、公司200、事实1000、核查500，事实另有conflict/resolution计数及是否仍有分页。内部核查新增计数、冲突聚合和身份解析使用完整匹配集合，不能把第一页当全量。解析最多展示50个歧义候选并标记更多，需进一步明确名称或证券标识。

## 重放与恢复

两种用途的 `materials(company_id, purpose='DAILY'/'REPORT')` 读取同一材料记录。当前导入不取得STRICT_HISTORICAL_AS_OF资格；今天接收旧报告仍是今天接收。经营状态、资料过期策略与三类变化计算留给03/06票，不在核查回执中编造经营结论。

新增表纳入现有SQLite备份，原件纳入evidence_archives附件枚举。备份枚举还核验新增结构记录hash、跨公司/版本及原件引用；公共读取拒绝hash不符的记录。已完成隔离备份导出/恢复和公用服务重开验证。具体命令、红绿记录和真实本地PDF导入回执见[02证据](../../.scratch/roll-research-valuation/evidence/02/README.md)。

03经营假设与共享快照入口见[company-analysis-api.md](company-analysis-api.md)。02证据入口及来源分类保持原语义。
