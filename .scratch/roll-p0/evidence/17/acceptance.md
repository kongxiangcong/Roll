# 17 · 研究登记与完整尝试验收

本票沿 implement-spec/TDD 的已批准 FastAPI/真实SQLite/raw+Parquet 纵向边界实施。源提交 afef19c、02d6f31、0e3bf9d；实际合入最新集成68e3b59（09/11）为7e8566d。保留09估值/资金分类和11SDK宿主、fetch预算/cancel，新增唯一实际 Codex 工具输入观察回调；未增加依赖或编辑父 execution-status。完整接口、M0具体设计和分阶段责任见[研究契约](../../../../docs/research-protocol-contract.md)。

## 真实输入、设计和权限边界

真实研究输入是根保全07-browser公开源运行 a77909f8-cf68-41a3-a598-a281f97bed7d / 快照7539cdf1-7856-4060-afb1-ee35a22755b9：SSE MAIN普通股票600519，181个原价交易日2026-01-05—09-30。只读复制并校验43份原件/Parquet及源JSON，首次本树44文件；最终隔离包另有本轮具体工程输入暴露说明，45文件逐SHA复制见[清单](final-input-copy.json)。费用另实际取得三份官方HTML，原SHA/实际取得时点/生效范围及日/月精度固定登记；[Gitblob与过滤检出字节检查](authority-byte-check.json)零差异。

只按日期/对象/覆盖元数据划窗：80开发、20标签隔离、40校准、20隔离、21封存。宿主真实生成三个单独Parquet，开发返回80行，校准返回40行及前20行只作特征上下文，19不需获取整档再自行filter。原数值/available_at保留，SHA映射可查；完整历史amount缺失、当前provider修订非历史PIT、历史特殊状态/公司行为不足继续限制，不回填历史获知时点。

M0一个透明候选、20日期限、最小NAV净改善25bp及固定必要基线、风险/覆盖/依赖支持门槛、固定G5成本/延迟/参数邻域、正式期运行哨兵/成熟检查点和三自然月硬终点均已事先登记；不是这些统计检验已通过。25bp依据显式研究成本和半仓NAV尺度，未读候选最终收益选阈值。三自然月现代中国标准时间月末夹取/跨年/闰年公开测试通过；实际前向首个预测起点仍归30/32，不由登记、工程账户或历史回放启动。

此前工程档案已公开，本轮元数据脚本误打印600519于06-22—06-30、09-21—09-30原价/qfq输入，已如实保存源文件SHA/日期范围和时间精度未知；没有计算标签、候选训练、策略收益或最终结果。后续实际sealed-input和原容器下载是明确工程输入/哈希边界验收，持续记录输入暴露，绝不称为一次确认性PASS判断。历史独立性UNPROVEN，换协议名/包名/重叠范围不能恢复独立封存；没有删改记录。

21个封存日最多1个20日期限成熟标签、有效20日块上界0，校准理论成熟上界20；尚未计算实际标签/类别支持。不能确认性PASS或冻结假完整模型。19必须按实际可评分标签训练/校准，未知状态/公司行为导致不可评分时不能默认为无事件或训练未知标签；20完整冻结真实模型/政策/数据/代码与方法，21准入判断，22独立风险政策证据单列。未知券商佣金不是0；3bp佣金只是含规费的研究场景，监管/经手费不重复另收。研究合成100万元不是用户资金授权或运行收费金额预算。

## 场景、预期与实际

| 主责任场景 | 输入/预期 | 实际与证据 |
|---|---|---|
| 登记/比较/重启 | SQLite保留草稿/固定M0、指纹、前序；缺产物不冻结、不授能力/前向起点 | 公开API和真实HTTP均保持不可变协议；旧版逐JSON比较不变；页面前序比较，[真实运行](real-registration-final.json) |
| AT-55 全部尝试 | FAILED/ABORTED/RUNNING，实际重启末项INTERRUPTED；遗漏失败拒绝，后继也不能藏前序失败 | 全谱系manifest、原子终态并发200/409、预算含失败/中断、五次拟合/一次校准守卫及拒绝配置留痕通过；旧记录不覆盖 |
| AT-54 封存访问/再命名 | 原输入工程访问须审计，普通SEALED分片403；未冻结结果入口拒绝；重复窗口须关联、不恢复独立性 | sealed-input/raw attachment/nosniff/SHA、市场快照/列表/客观观察/离线重放审计通过；真实模型结果及确认性结果查看属于19/20/21后续，未以本票输入访问冒充完成它们 |
| 模型实际工具收到输入 | 11 host actual roll_read_evidence返回[:20]事实，送固定worker前持久记录，失败回调不给输入 | METHOD_CASE_CODEX固定worker/MockTransport的公开API验证2条RAW/qfq输入审计，实际SQLite；不是实际SDK/训练证据。11既有应用12项保持通过 |
| AT-57 可选停止 | 操作/安全/用户停止单列，EARLY_PASS拒绝并留偏离；完整冻结前STATISTICAL_FINAL拒绝 | OPERATIONAL_CHECKPOINT、OPTIONAL_STOPPING_DEVIATION、RESULT_ACCESS_REFUSED持久保存；无临时PASS，无亏损延长期限 |
| AT-59 当前名单条件性研究 | 当前明确股票身份、HISTORICAL，未知域/名单回溯不继承资格 | 固定有限适用域与历史PIT/名单限制、NOT_GRANTED、封存不足页面可见；未启动实际模型或扩域资格 |
| 源完整性/安全 | 变坏原件拒绝，宿主标识不能越路径，无来源账户导入 | SHA损坏409、路径422、不登记坏包；实际两次隔离HTTP验收账户始终0，与前后完整JSON相同 |

## 实际检查层次

TDD先看到登记/分片/封存/检查点404、预算超限201、后继遗漏失败manifest未报缺项、Codex输入未审计的失败，再逐纵向实现。市场观察方法输入最初只上涨1%，不能触发已有≥10%下跌观察，修正明确方法输入100→80后核验真实观察语义；没有更改观察阈值或产品范围。DIRECT_HTTP本身只返回run元数据，测试修正为实际facts查询/重放才计输入暴露。Chrome首次命令从错误工作目录执行，启动失败；从frontend预定目录运行通过。未把这些早期red当最终通过。

合09/11的17+11应用组合22 passed/49.20秒，保存为明确[工具观察记录](backend-union-observed.json)，不是重建原stdout。其后仅将所有既有带日期的源观察归入输入审计、验收脚本用完整前序manifest；最终17专项10 passed/20.71秒[原stdout](backend-research-final.txt)覆盖这一局部delta。65 passed/128.49秒[相关组合原stdout](backend-shared-final.txt)及[时点/source metadata](backend-shared-metadata.json)：07/08 market query/replay、09估值、账户公开应用。未声称一个最终HEAD完整全backend套件一次全跑，也未重复无变化真实Codex运行/无关恢复套件。

最新合入后真实子进程HTTP有两次不同PID的中断/重启，完整manifest不漏前序，原件SHA下载正确，账户不变：[最终实际报告](real-registration-final.json)、[进程命令原输出](real-process-final.txt)。此报告保存实际source文件SHA/uv.lock与真实runtime时间。固定失败/中止记录明确METHOD_ATTEMPT_ERRORS，没有冒充真实模型训练失败。此前[pre-integration运行](real-registration-pre-integration.json)与[首次合入后的报告](real-registration-first-final.json)同样保留。

最新Chrome研究独立1 passed/9.9秒：[原输出](browser-final.txt)、[报告](browser-final-results.json)、[页面](17-research.png)，实际181档案/真实SQLite，验证五个primary保持、失败/中止/中断、冻结缺口、sealed-input审计、前后版本和账户0。生产构建47modules通过：[原stdout](build-final.txt)。后端最后一行观察分类/验收manifest的delta由10专项+实际HTTP复验覆盖，前端无再变化。默认全文件npm e2e仍有已记录05共享夹具冲突，不宣称全绿；分组原则及17重跑命令在[浏览器说明](../../../../docs/browser-acceptance.md)。

## 保全与结项限制

实际 `ROLL_DATA_DIR` 分别为 `D:/dsh-proj/Roll/.scratch/worktrees/17-research-protocol/backend/.roll-data/acceptance-17` 和 `.../acceptance-17-final`。151文件/20,893,789字节（原件、原与宿主分片Parquet、源JSON、工程暴露登记、真实SQLite、日志、历次实际报告）逐路径/SHA在[runtime-preservation.json](runtime-preservation.json)。根07来源只读未动；本树暂保留，清理前须复制到长期implementation-evidence/17并逐SHA/bytes验证，不能只留指纹删原件。

17工程登记/尝试/封存边界完成，不是完整实验冻结、研究PASS/G7或正式资金授权。实际历史状态/PIT/公司行为、完整amount、券商费用与独立封存不足保留；新未使用窗、真实成熟标签、训练/校准、政策、统计覆盖验证和确认性测试分别由19/20/21及30/32完成。独立风险政策22不继承收益模型资格。父68e已有09保全JSON的CRLF全合并diff warning来源保留，本票对68e基准diff--check无误，未改他票原件换行。
