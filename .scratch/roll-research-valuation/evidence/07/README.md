# 07 每日公司研究交付证据

日期：2026-10-27（Asia/Shanghai）。本目录只验收07，不实施08。普通分诊保持ready-for-agent，Completion在最后受影响检查完成后单独更新。宽回归实际结果为**134 passed、5 subtests passed、2 failed，693.93秒**；失败及修复后的窄回归结果单列，不能称整次宽回归全绿。

## 实现与复现入口

- [公开接口与运行边界](../../../../docs/research/company-daily-api.md)：固定snapshot/core、安全CURRENT_PRICING、持仓/关注有限名单、历史隔离、原worker RESEARCH类别、存档与公网核查区分、逐条失败/增量批次、规范财务字段及恢复。
- 日常网页：`http://127.0.0.1:5207/`；独立API8027、worker租约1。样例store：`D:/dsh-proj/Roll/.scratch/rv07-real01`，恢复store：`D:/dsh-proj/Roll/.scratch/rv07-real-restored01`。生产8010/5173和原账户store未使用。
- 工作树`D:/dsh-proj/Roll/.scratch/worktrees/rv-ticket07`、分支`codex/rv-ticket07`。开始时clean，精确基线`1e493f043a8a042b29a5d170272c953c6afc848e`，祖先检查退出0。交付前快进合入coordination-only集成tip`38dc628ea30a6f7040150c40f49e5944ad7e2bfe`，见`integration-merge.txt`。

公司研究由宿主按共享快照直接展示：关注理由、三类变化、现价要求/缺口、催化/未知日期、风险与未来失效条件、资料时效，以及可展开的支持/反证原文、页/JSON行、原件、假设和历史拒绝。未来失效条件明确“若出现/尚待验证”，不当作已发生事实。固定快照引用的审核在每次读取时检查当前用途；blocked/缺失估值不突出价格区间，也不遮经营研究。原量价辅助、回测和原概率标签保留。

规范财务适配只机械映射现有INCOME3/BALANCE3/CF4白名单，核对原JSON精确十进制及已确认期间/单位/币种/范围；没有FCFF、WACC或经济批准推断。JSON行和语义PDF页分开，继承原来源缺口，不声称每列已独立核对PDF。材料导入和每批20材料的事实适配进度独立，旧材料可补齐；逐字段幂等，适配尝试不可变并纳入恢复。未知新闻期间与UNKNOWN财务口径继续保留材料/缺口，不以采集日填期间。新增事实才冻结03输入并最多执行90秒经营模型；没有新增不重跑经营模型或完整报告。

## 真实样例与合成结果分账

### 真实江西铜业

`prepare_real.py`从03已存在backup`373db805-d94c-45a0-a41e-a20bb29b566f`恢复到新07目录，未创建/修改原03研究记录；`real-prepare.json`保留回执。继承真实2025年报原件及两次03真实CODEX历史：当前快照`e28c866f-5fa5-458d-a48a-1ed1869d40ea`，核心hash`cce09e5c244b4a6cdf4293477c6d46d804de46ee4801ce8f5a60f05a4623fc52`；首版`90c3e7b9-56f9-4ad6-a39a-7c343a1a95f6`的HYPOTHESIS_CONFLICT和可用假设不足原因仍可读，没有抹平旧失败。

本票另外实际运行**2次**BaoStock PUBLIC＋订阅CODEX `gpt-6.1-sol`日常辅助，不是重新生成03经营核心：

| 新07运行 | 实际结果 |
|---|---|
|`2becf239-5f19-42a7-95ed-19c898550c96`|COMPLETE；四源各80行，保留探索回测、0模型工具；见`real-assistance-request.json`、`real-assistance-result.json`。该历史任务尚无新增结构化research_comparison，页面不补写为当时已核对一致。|
|`0d3e916d-5d09-41ba-a9f5-fc5a7ca5028c`|COMPLETE；最终结构化对照为NOT_COMPARABLE，固定e28快照。解释短期量价偏空和面向下一报告期的条件经营假设，不能确认同向或冲突，不改core/估值。见`real-assistance-request02.json`、`real-assistance-result02.json`。|

实际价格覆盖截至2026-10-26；请求开始、后续原件取得、证据包冻结知识时点、经营依据/生成时间分别保存。历史价格日期不冒充全部研究当时可得PIT。未请求新的OpenAI API key，凭据未打印/进入证据；JSON凭据字段检查匹配0。

江西铜业当前仍无可用条件估值区间，真实经营/周期/分部口径缺口未解决。本票真实样例不声称已完成12要求的当前正向估值全链。第二公司承德露露只登记真实身份，不导入/冒充其财务或估值；页面准确显示无事实/快照。新增规范财务字段正向链使用METHOD公开采集测试，不能当成本票新取得的真实财报。

### 实际手动刷新、失败、重试

`run_real_updates.py`使用真正运行的原worker和实际时钟。`real-updates.json`和最终代码下另一次`real-updates02.json`分别保存完整任务/核查回执：JCC两次archive-only COMPLETE且同一observation_id，未重复发布、未重跑模型、原core/hash不变；露露公网scope不支持为PARTIAL，随后显式新key archive-only重试COMPLETE。此重试只成功检查已归档目录，不表示原公网缺口已解决。账户version0。

本票实际新增公网取数仅上述BaoStock任务；没有宣称新的真实财务/新闻公网核查成功。存档目录的SUCCESS_NO_NEW只表示所列下一批范围无新增，未将其写成经营不变或今日验证。实际盘后周期观察数**0**，两个真实周期按票约定留12汇总。

### 浏览器与恢复

`real-browser.txt`：真实本地store的Chrome只读走查PASS，覆盖固定历史、旧拒绝、两公司隔离、实际scope失败、重载、1440/390宽度；0新增模型、0公网刷新、0写请求（解析调用除外）。父代理另用IAB独立核对相同内容，记录在外部`rv07-browser-checklist.md`及协调记录；本目录脚本/截图是独立可复现证据。

- [实际桌面](real-daily-desktop.png)、[手机](real-daily-mobile.png)
- [支持/反证与页码](real-daily-evidence.png)、[旧版局部拒绝](real-daily-old-partial.png)、[第二公司缺口/失败](real-daily-company-gap.png)
- `browser-final.txt`及[合成桌面](synthetic-daily-desktop.png)/[合成手机](synthetic-daily-mobile.png)：另外的METHOD网页场景，覆盖刷新503失败→重试、共享历史选择和公司切换；不当作真实研究结论。

`verify_real_recovery.py`先按原hash/原receipt把早期07任务的legacy assistance-raw字节登记进EvidenceStore，不重写原run或packet；新生产路径已直接归档。随后实际创建backup`7e9ada0e-64a3-42f7-bc6f-e65e1d182394`并隔离恢复，见`real-recovery.json`/`real-recovery-command.txt`：共享snapshot与DAILY/REPORT完全相同、两次辅助结果原文结构/packet hash不变、8份源原件hash有效、检查记录保留、账户0、network/model调用0。

## 红绿、失败与实际命令

测试边界沿用用户已确认的公开研究service/API、calculator、网页和Backups；不重复询问。新测试的供应器模拟系统边界，SQLite只用于外部legacy/corrupt存储fixture设置，断言仍通过公开服务/API/备份。没有新写私有实现镜像测试。

| 切片/检查 | 实际结果与保留的失败 |
|---|---|
|01固定共享正文|red01缺daily_view；green01通过，缺估值仍展示经营，跨公司快照拒绝。|
|02证券/历史隔离|red02/02b/02c最初是fixture公司名、口径、名单revision设置错误，不称产品red；red02d正确复现缺通用构造入口。green02源fixture日期越界导致无material；green02b修正后通过。|
|03存档无新增/失败重试|red03缺refresh入口；green03通过，同key复用、无新增不发布新快照。|
|04原worker多公司队列|sandbox TestClient空red04挂起，精确中止本票session后escalated red04e得到缺入口；green04暴露嵌套SQLite写锁，改有限名单只读检查后green04b通过。空日志不算产品结果。|
|05时点|red05缺独立价格日/知识时点；green05另暴露checks列表键名错误，green05b修复后通过。|
|06未来失效条件|red06无类型，裸列易误认为当前事实；green06明确kind/未验证及对应假设，通过。|
|07备份引用|red07重hash的跨公司daily绑定竟可备份；green07增加关系校验并恢复通过。|
|08经营/量价解释|red08无比较schema；green08固定snapshot_id对照，错版本拒绝，2 passed。解释不等于经济事实背书。|
|09/10批次与坏记录|review09首次fixture archive未传received_at，修正review09b通过。red10首个坏新闻阻断后续合法记录；green10逐条保存失败并继续。review12/17覆盖20+5+0、首20份缺原件仍推进后5份、原缺口保留。|
|11/12/17模型及范围|review11 sandbox停滞，精确中止同session后review11e通过；无认证为UNAVAILABLE且model_executed=false，保留旧core。review17移出名单取消、另一公司继续。|
|13原件归档|red13来源缺raw_archive；green13进入EvidenceStore，随后真实legacy原件登记和恢复也通过。|
|14/15规范字段|red14规范报表只成material而不能自动分析；green14正向7字段。red15已导入旧BALANCE漏掉assets；green15独立适配phase修复。review16已知字段/UNKNOWN口径2 passed。|
|18盘后工程场景|review18使用明确METHOD时钟，仅当前日一次，跳过离线日期且同输入不重复观察，1 passed；不算两个实际盘后周期。|
|19旧命令兼容|red19新增可选retry字段造成旧持久化命令hash409；默认false兼容旧hash，原job不改写。修复结果在最后窄回归中。|
|最终宽回归|`final-regression.txt`：134 passed、5 subtests passed、2 failed，693.93s。两项旧observation测试覆写prepare(job)，07给旧kind也传第二cancel参数，任务卡RUNNING。修复为仅新RESEARCH传cancel、旧kind保留单参。|

最后窄回归`final-delta-regression.txt`实际为**36 passed in161.30s**，包括全部新daily、全部旧observation和assistance；不把已发生的宽回归失败写成全绿，也不无故重复已绿的估值/恢复suite。

主要执行命令（工作树根，使用已安装依赖，无install）：

```powershell
$env:PYTHONPATH='backend/src;backend/tests;backend/tests/application'
& D:/dsh-proj/Roll/backend/.venv/Scripts/python.exe -m pytest -c backend/pyproject.toml backend/tests/company_research backend/tests/test_assistance.py backend/tests/application/test_observation_updates.py backend/tests/application/test_company_research_sources.py backend/tests/application/test_backups.py -q --basetemp=D:/dsh-proj/Roll/.scratch/rv07-final01
& D:/dsh-proj/Roll/backend/.venv/Scripts/python.exe -m pytest -c backend/pyproject.toml backend/tests/company_research/test_daily_research.py backend/tests/application/test_observation_updates.py backend/tests/test_assistance.py -q --basetemp=D:/dsh-proj/Roll/.scratch/rv07-final-delta02
```

`npm run build`最终通过，既有大于500kB chunk提示保留，见`build-final.txt`。`node frontend/scripts/daily-research-real-check.mjs`应在frontend目录执行为`node scripts/daily-research-real-check.mjs`，合成场景同理。真实服务使用start-roll.ps1独立DataDirectory/API/Web端口及既有授权，未输出凭据。初次依赖junction使用错工作目录导致失败、初次5190端口占用被launcher安全拒绝；未停止该旧进程，最终使用8027/5207。中间UI字面反斜杠导致Vite overlay、合成fixture缺reviews.calendar导致页面崩溃，均保留失败输出并修正；最终两类浏览器均PASS。

01冻结检查`source-freeze.txt`为27文件/94调用PASS。`method-source-check.json`证明10份04/05/06计算/审核/比较及许可证实际字节与基线完全一致。首次git diff --check指出新源码/票末尾CRLF/空行，随后仅规范新改文件并重检；捕获日志/JSON按限定.gitattributes保留Windows字节。最终staged source一致性和HEAD/clean记录交付前追加。

## 限制

仅当前适配范围与有限名单；没有任意PDF/未知新闻期间的自动事实抽取。未知口径、>80事实、来源拒绝、缺原件、模型失败均可局部交付，旧研究不被改成今日验证。来源结构/字面一致性不是独立事实审核，模型解释也不是收益验证。当前JCC不具备可用估值，真实露露05条件估值未在07复制来冒充JCC。未生成08完整报告/PDF、未扩展正式资格、未修改账户、ForecastBundle、旧预算或SEALED，未运行两个实际盘后周期或全仓所有测试。

最终判定：07 complete，08 next，整体in-progress。末次窄回归36 passed；独立METHOD盘后检查review18为1 passed，不算实际盘后周期。最终git diff --check通过。提交前staged字节检查单列，最终HEAD由提交结果报告；真实样例服务留在独立5207供查看。

最终补充20：red20经实际受限METHOD worker返回带局部拒绝的合法候选，03已发布PARTIAL新snapshot，但07回执仍指旧版；修复为COMPLETE/PARTIAL都校验同公司/同input后绑定已发布snapshot，PARTIAL错误及拒绝仍保留。green20定向验证该路径和UNAVAILABLE旧core保留，**2 passed in13.62s**。该修复后未无故重跑已绿宽suite；前面的完整受影响窄36项结果单独保留。网页读取最新版本也同步刷新历史选项，避免新core与旧selector混淆；构建/浏览器重检结果见build-final02/browser-last。

提交前最终校验：staged-source-check.json为23/23实际暂存源码字节与测试工作文件一致；git diff --cached --check通过。最终真实与合成网页重检均PASS，build-final02通过（既有chunk提示保留）；独立5207的API/worker/web状态均RUNNING。仅结束本票已无用途的合成5189开发server，其他已有进程/端口未动。
