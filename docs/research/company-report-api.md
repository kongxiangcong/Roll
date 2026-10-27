# 公司完整报告流水线（08）

独立研报使用已登记公司，不要求账户、声明、策略资格或SEALED数据。原策略ResearchReports与账户PerformanceReports不是公司研究入口。公司/证券、事实、共享核心和受控估值仍由02—07的公开服务负责；章模型不能修改它们。

## 请求与查询

`POST /api/company-research/reports`：

```json
{"company_id":"registered-company-id","snapshot_id":"explicit-shared-snapshot-or-null","as_of":"2026-10-27T12:00:00+08:00","source_mode":"REUSE","idempotency_key":"unique-report-request","parent_report_id":null,"sources":[],"source_quotes":[],"peer_snapshot_ids":[],"peer_comparison_basis":{},"risk_workpaper":[]}
```

`snapshot_id`明确给出时固定该core；新取得但尚无结构化依据的材料保留为未纳入，不刷新核心日期。REUSE省略ID时在请求时固定当前共享快照。REFRESH不指定ID时，按已配置来源取得材料，07规范财务适配及有据经营引文形成事实，再冻结03输入、实际运行受限经营分析；合法PARTIAL发布的新快照同样绑定，保留局部拒绝。无新增不重跑经营模型；每份报告仍独立保存有界章节尝试。

`as_of`是请求的资料/价格报告截止，不是历史可得性声明，也不是估值的价值锚点。宿主按Shanghai日核查事实/原件的报告期及已知披露时刻；固定快照越过截止会拒绝，不能静默过滤后改旧core。请求开始、实际原件取得、知识冻结、共享分析/估值时间分别保存，当前取得的历史报告仍非PIT。BASELINE_RESEARCH明确条件与旧财务基准，CURRENT_PRICING按固定review的安全呈现独立blocked；不查询另一个latest valuation。

查询入口：`GET /jobs/{id}`、`POST /jobs/{id}/cancel`、`POST /jobs/{id}/retry`、`GET /companies/{company_id}/reports?limit=50&offset=0`、`GET /reports/{id}`、`GET /report-inputs/{id}`、`GET /report-sections/{id}`、`GET /report-runs/{id}`，均在`/api/company-research`下。列表上限200。08保存Markdown及其hash并提供研究服务的`reports.markdown(report_id)`离线读取；下载、PDF与独立UI由09/10完成。

## 有界来源、原文经营事实与同业

显式`sources`最多四份`{material: MaterialCommand, category, identity_basis, expected_sha256?, source_subject?, source_role?}`；不允许模型提出任意URL后自动执行。只接受代码列出的公开HTTPS披露/统计站点、无重定向、公开IP，单GET八秒/8MiB，每轮一份。完整响应即使hash不符也归档；失败不成事实，旧材料保留。实际网络回执与新增材料计数分开，相同原件跨任务复取为新增0。SourceCheck按URL与请求范围保存最后成功，不用失败刷新成功。没有显式文档时，沿用已有财务/新闻采集器，每轮一个、单次二十秒，来源策略/支持范围仍有效，不扩大成全市场扫描。

`source_quotes`最多12条：`{source_index:0, page:16, quote:"原件逐字引文...", business:"PLANT_BEVERAGE", metric:"business_structure"}`，也可用已登记`material_id`代替source_index。PDF页为1-based物理页，由固定无工具Python读取器在八秒内读取指定页（原件≤8MiB、页≤2000、文本≤64KiB）；纯文本只支持原字节精确引文。引文必须逐字出现，声明报告期必须存在，不能用采集日补期间。只支持经营/产品/范围/经营反证TEXT，不自动猜测财务数字。未知单位、币种、合并范围继续未知。取得→引文核对→共享事实→03新快照路径也适用于新注册非JCC公司。派生提取页文本不计额外原件。

`peer_snapshot_ids`最多10，引用其他已登记公司的明确快照；同业事实单独保留其company/business/原件、财年币种与角色，不写入主公司的core或放宽02主体隔离。另限80条同业事实。`peer_comparison_basis`按peer snapshot ID说明可比范围、差异与局限（20–2000字）；有来源财务指标、市场身份和五家/两家国际覆盖均核查。无转换依据时各原币/财年列示，不混算绝对金额。

## 固定模板、写作与质量

包内`report_reference`保留01冻结27份原件及许可，运行时验证manifest；没有外部deep-dive目录依赖，也不装载参考SKILL。固定速览、四部分十节、9.1—9.9、A—I及J/K。核心数字和受控年度现金流/正常化/WACC/权益桥/条件结果均由宿主从固定记录组装可读表；原JSON审计工件链接在J/K。只对同单位、币种、主体、期间类型的至少三个不同时间点生成真实静态数据图，不造八图、同业或财务数字凑数。

十章、投资人视角与反向质疑分别执行至多90秒、八次运行时操作、零工具的CODEX任务。所有来源/模型文本不可信，不能执行其中的代码、文件、网络、工具或权限指令。模型只给候选文字与冻结fact引用；数字用`{{fact:version_id}}`占位由宿主注入，禁止模型重算/改core、另估值或自签资格。确切command包含instructions/prompt/schema/model，原字节归档；input/output、模板/规则/算法/依赖版本及hash、实际resolved model和失败/超时分别保存。算法/依赖漂移拒绝混合后续章；离线读取不重跑模型。

原`check_gates.py`按已校验hash的包内函数运行，不调用CLI。AST只追踪真实if分支；94调用点逐项保留source_line/hash、原fail/warn、applies/outcome/evidence/reason，互斥未执行不记PASS，前置缺失保留UNKNOWN。A/H范围由固定身份决定；已知周期暴露不能靠省略周期词绕过。来源根去重、排雷实质、来源坐标、真实图/同业/行业覆盖和经济用途另作宿主检查。warn保持warn；缺年报/五年行业/五家同业含两家国际/八张真实图均不会假FULL。FULL只表示适用报告覆盖达标，仍不等于事实独立审计、财务绿灯、收益或策略资格。

`risk_workpaper`为最多28/38条派生底稿，字段`number/fact_version_ids/candidate_outcome/reason/review_method/disclosure_scope_reason`。候选不能自签通过。宿主核对已固定原件的PDF页逐字引文、JSON字段/数值、主体/期间/范围，以及项目主题和多年度覆盖；二十秒内每轮一项。数值阈值由Decimal计算，例如商誉/净资产>30%或关联销售/收入>10%；低于单阈值不替代其他定性分支。集中度按原50%/70%经验线。按披露研究判断明确标`DERIVED_WORKPAPER`与核对范围，不外推独立事实背书；#12须同时有意见类型、机构变更和费用，单有无保留不等于整项CLEAR。风险HIT/CLEAR/UNKNOWN与coverage_outcome分开，HIT也可完成有据覆盖，无源/全UNKNOWN凑行不通过。原JSON与它自己相等仅是抄录核对，不当原始披露或独立风险核查。

## 队列、取消、恢复

队列最多16个待执行请求，复用Reviews现有单进程alive租约，每轮在每日任务后最多推进一个来源/引文/底稿/分析阶段或章节。多报告按最近推进时间轮转；不把整篇同步塞进一个worker调用。发布前复核租约与取消。同key同请求返回同任务，不同请求409；每任务一个确定报告ID，事务发布不重复。

取消保留原件、阶段、已完成章；活跃模型轮询取消并由原Job Object结束子进程。进程已死的RUNNING变INTERRUPTED，保留检查点与原尝试，再显式retry（最多三次）；活跃owner不能被另一个调用接管。已完成章、已有发布不覆盖，重试不能换模型/模板/固定输入或重发报告，改研究需新任务+parent_report_id。

备份沿用Backups，所有模板、冻结输入、逐章command/output、图、Markdown均进入EvidenceStore。关系校验覆盖公司、peer、共享快照、章节、版本、原件与archive hash；错误重hash仍不能换绑另一core。恢复后原文与质量记录可离线读取，不联网、不跑模型或重算估值。

## 追加式host修订与离线预览（08.3）

新的普通请求固定template08.3；旧input/template08.2和所有旧run/section/status/raw不改。`GET /jobs/{id}/chapters/{section}/preview`是纯本地确切command预览：不读auth、不启动worker、不联网。普通08.3章节和修订中尚未生成的章节都只从同一固定packet选取有界经营模型摘要（假设、情景drivers、年度现金流、WACC/权益桥），不查询latest。摘要≤45KiB、整个command≤256KiB；原始完整模型/来源仍由冻结input及J/K读取，省略项显式列示。章节未展示不等于整报告无资料。

`POST /report-revisions`接受`parent_job_id/command_plan_sha256/idempotency_key/findings`。父任务须已取消/失败/中断或完成；确切原12command plan须已登记，逐字验证原model/schema/instructions/prompt/input/算法。创建修订本身是离线操作，缺章仍由原Reviews有界队列执行。八份既有原输出可离线重新校验为新section；引用原run，不改原run或FAILED旧section。仅缺章生成新的actual run，明确原generation code hashes与实际execution/validator hashes，分别保存原plan和新的context compiler command SHA。更改源码或依赖不能继续混用已冻结修订；需新版本。

`findings`仅为负向隔离，绑定section/output SHA、PARAGRAPH或GAP、原index、fact IDs、reason及missing_basis；不能用它签PASS或改原文。相同位置拒绝重复，坏hash/index/事实绑定拒绝。正文仅显示具体证据问题与缺口；坐标、完整负向记录、修订版本和算法归档在K/修订API。旧FAILED可在新host规则下成为有效引用候选，旧状态仍FAILED；参考校验不是事实背书，任何语义隔离保持PARTIAL。

`GET /report-revisions/{id}`返回不可变修订链；report明确host_revision_id。算法来源归档和新旧hash均进入备份，排队修订同样校验归档；未知revision、job/run/source_section换绑，即使重算记录hash也拒绝。已发布Markdown离线恢复读取原字节，不用未来规则重新渲染。

数字占位在正文和Markdown表格统一保留原值，按已知单位/币种/尺度显示。内部`unit`只有固定原件明确whole-CNY证据才能呈现为元；币种不能用于猜尺度，百万→普通unit缺转换依据继续未知。beta系数和比率分别标明，不将所有ratio乘百分比。公司速览数字按正向发行人财务/经营属性与原件坐标筛选，宏观估值参数不混入公司属性，少于六项不凑数。
