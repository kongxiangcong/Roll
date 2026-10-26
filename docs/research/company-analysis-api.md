# 公司经营分析与共享快照入口（03）

03在[02证据入口](company-evidence-api.md)之上扩展`CompanyResearch`，不依赖用户账户确认，也不创建交易、资格或原研究预算事件。服务、存储、模型候选校验与CODEX适配分别放在`research/company/analysis.py`、`candidates.py`、`model_runtime.py`及`agents/company_analysis_runtime.py`；既有`codex_process.execute`只增加明确的任务分派。

## 冻结和执行

`freeze_analysis(AnalysisCommand(company_id, as_of, fact_version_ids, parent_snapshot_id, purpose, evidence_gap_reason))`或`POST /api/company-research/analysis/inputs`绑定输入。`as_of`须为不晚于冻结时刻的带时区ISO时间戳；事实及其材料必须已可消费。今天取得旧年报不能回填历史取得时刻。输入无事实时必须说明缺口。

显式选择最多80个事实版本。宿主补入所选事实序列已存在的全部冲突头及完整处理理由；不能只取有利一边，也不把分页首页当全量。已知冲突若不满足截至时点或80项/96 KiB输入上限，则拒绝冻结并保留原件供下一次缩小范围。父快照须为同公司当前版本。包内保留原件hash、页/表、来源根、单位/币种/范围、披露及实际取得/可消费时刻、冲突及历史假设版本。后到事实不会进入已冻结包。

`run_analysis(input_id)`或`POST /analysis/inputs/{id}/run`同步执行一次有界尝试；阶段队列与报告任务由08负责。只使用既有`ROLL_CODEX_AUTH_FILE`和`ROLL_CODEX_MODEL`配置，默认`gpt-6.1-sol`。复用现有Windows Job容器、临时隔离home/cwd、订阅认证、禁用skills/MCP/外部应用/联网/文件和shell的运行时；给模型的动态工具为零。宿主等待模型期间不持SQLite写事务，默认180秒、8次运行时操作、0次来源工具调用。相同公司活跃尝试互斥；已发布输入复用同一快照，不再调用模型。无有效凭据或运行失败保存净化错误与原输入，不以fixture替代真实结果。

## 候选和发布

`apply_analysis_candidate(input_id, candidate)`或`POST /analysis/inputs/{id}/candidates`接收候选。外部候选固定标为`EXTERNAL_CANDIDATE`，不能自行宣称真实模型来源。候选上限64 KiB，只有宿主可以发布快照。候选原文UTF-8字节、规范化JSON及其hash分别保存，模型原文不经重新序列化冒充；输入及原文走现有`evidence_archives`权威归档。

业务结构、关注理由、反证逐项引用冻结fact-version；无依据需说明缺口并标`UNABLE_TO_JUDGE`。经营假设包括稳定key/ID、版本、业务、判断、期限、观测指标及口径、支持/反证、失效条件、下一验证事件、缺口和修改理由。修订必须引用被冻结的前版，历史版本永远可查；本次省略的旧假设版本ID明确列出。具体验证日期须逐字见于所引事实，否则保留null及未知原因。字面数字支持校验只是有限的一致性检查，不证明经济推论或事实真实。

同一段落可以同时披露风险与缓释，保存`overlapping_evidence_roles`；不能因此增加独立来源。不存在的引用、其他公司的引用、错误修订、缺口或格式问题按项目拒绝，`rejections`保留原因，其他可用研究继续发布。少于三项假设保存明确原因；没有证据时允许无法判断，不能填造判断。并发新父已发布时拒绝旧候选；候选归档仍可查，旧快照不被覆盖。

## 读取与恢复

`GET /analysis/inputs/{id}`、`GET /analysis/inputs/{id}/candidates`、`GET /analysis/runs/{id}`、`GET /hypotheses/{version_id}`可追溯输入、候选、模型审计与历史假设。`GET /companies/{id}/snapshots`及候选列表分页，最大200项/页。

`analysis_snapshot(snapshot_id, purpose='DAILY'|'REPORT')`与`GET /snapshots/{id}?purpose=...`始终返回同一规范化核心payload及hash。已发布快照无修改入口；更新创建新输入和父子版本。快照明确保存估值为空的原因，不假装04/05已执行。离线重放读取保存原文与快照，不重新调用模型冒充原文再现。

新增表、输入/候选/原文归档均纳入既有备份；备份校验结构hash、同公司事实/材料/假设/父版本/输入/归档引用。03真实模型与隔离恢复证据见[验收记录](../../.scratch/roll-research-valuation/evidence/03/README.md)。生产任务不需要开发者PDF路径。
