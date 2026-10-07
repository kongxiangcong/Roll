# 统一审阅修复与验收

固定被审阅产品 `62c8e69`，本树起点 `8a308ba`；已FF合根最后审阅/保全提交 `7c9db98`。Standards 1项与Spec 2项的原报告及复现保持不变；本文件记录修复结果。没有推送、修改父execution-status、补未来受阻模块、放宽生产预算或启用真实资金能力。

## 修复范围

| 审阅问题 | 实际修复 | 公开验证 |
|---|---|---|
| Standards P2：15保存超长理由，14消费500 | 两个入口共用market/verification_input.py公开模型；reason2000/fact_id100/field80等限制相同。新超长入口422；旧保存不兼容命令409并提示重提，旧请求/观察/知识截止和关联不改 | 原产品4失败 → 新入口与旧存量4通过，加既有正常消费1通过 |
| Spec P1：旧父分叉重获拟合预算并遗漏兄弟失败 | 原祖先lineage保留，manifest加入共同根family的全部版本/尝试；短BEGIN IMMEDIATE内整个family共同消耗5拟合/1校准，失败、中止、中断都计数 | A→B五失败→A→C额外拟合409，C包含B五失败，遗漏freeze拒绝；B校准中止后C校准409 |
| Spec P2：新实例误中断仍活宿主 | 尝试、日线执行/复评、来源解析保存PID/进程创建时钟/实例nonce；新实例只结束已死宿主或旧版身份未知记录。Registry正常关闭只结束自身nonce。完成/中断事件短事务一次；公共身份helper检查Windows同步句柄状态，不能只凭创建时间 | 活peer研究可由原实例finish；固定提供方仍运行的来源解析不改状态；METHOD外部SQLite pending执行边界保留RUNNING/定义/输入；实际OS原宿主Job终止后一次中断，活peer不受影响 |

没有新增DAG、通用实验服务或Agent框架。共同根家族预算沿原前序关联保守累计，不声明能核实宿主外未报告尝试。执行源码指纹随实际修复更新；旧结果与原件不可变，既有版本门禁继续生效。

## 已知工程债

- `npm run test:e2e` 现在有限默认11文件逐个启动真实服务/空SQLite，同文件内连续case共享事实；无产品reset、无忽略失败。每轮唯一报告目录，最新manifest保存每文件退出码与完整输出。default factory/外部/METHOD/已有目录/恢复flag不能混用；模型凭据从默认子进程环境移除，缺凭据路径不会发真实计费请求。外部来源、SDK方法、真实原件和两阶段恢复单独显式profile。
- DeepSeek方法测试用公开运行记录中冻结的timeout_seconds加10秒有限收尾；生产期限仍≤120秒，进程wait≤5秒/目录cleanup≤1秒。18原55通过/1项20秒轮询红保留，没有以一次隔离绿冒充原组合通过。
- README更新账户、市场取证/关键复盘、研究与备份实际范围、数据布局和剩余条件；17活命令改用根永久implementation-evidence目录。
- 仅移除backups.py、test_backups.py、test_backup_process.py各1个EOF冗余空行，原件与旧日志未重写。
- 默认真实Chrome暴露的旧断言也按实际语义修正：baseline使用精确能力文本（新增事实观察出现相同子串）；rights输入600001不能查600000。当前精确总成本500.01与未知gross_subscription_amount同时核验，随后费用分拆495.00/5.01且现金不再扣款；没有降低财务断言。

## 分层结果

环境见[environment.json](environment.json)：Windows11/Python3.13.12/Node25.8.1/Chrome154.0.8037.95，锁定Codex0.161.0、Agents0.23.1、OpenAI3.26.0等既有依赖，无新增依赖。

| 层 | 实际结果/时间 | 原输出 |
|---|---|---|
| 公开SQLite输入契约 | 根原产品4失败12.36s；修复加正常消费5通过15.50s | [red](raw/input-red.txt)、[green](raw/input-green.txt) |
| peer与家族定向 | 原peer2失败6.84s/原family1失败4.78s；peer+既有重启3通过11.54s，family1通过4.14s；含pending执行及校准的最终4通过12.79s；pending夹具进一步精确移除完成记录与同事务结束事件后，单例1通过/3未选4.05s（产品代码未再改） | [peer-red](raw/peer-red.txt)、[family-red](raw/family-red.txt)、[peer-green](raw/peer-green.txt)、[family-green](raw/family-green.txt)、[lifecycle-green](raw/lifecycle-green.txt)、[pending精确边界](raw/pending-boundary-green.txt) |
| 真OS | 活peer/原宿主Job退出0子进程/恢复一次中断1通过10.51s | [最终原输出](raw/owner-os-final.txt) |
| 构建 | TypeScript+Vite53module通过，6:44左右运行 | [原输出](raw/frontend-build.txt) |
| 完整默认Chrome | 2026-10-08 06:49:27—06:51:51 Asia/Shanghai，11文件/独立SQLite、15通过0失败2明确profile跳过，退出0 | [原输出](raw/browser-default-green.txt)、[逐文件manifest](raw/browser-default-green/manifest.json) |
| 完整后端 | 2026-10-08 06:43:56—07:07:57 Asia/Shanghai，343通过、1439.06s（23:59），命令退出0；产品修复版本全部覆盖，pending METHOD夹具准确性单例另列 | [完整原输出](raw/backend-full.txt) |

Chrome先前完整两轮13通过/2失败/2跳过与14通过/1失败/2跳过全部保留：[首轮](raw/browser-default-red/manifest.json)、[二轮](raw/browser-default-red2/manifest.json)，不合并增量结果冒充完整绿。最终明确跳过的2项是另需固定SDK提供方的DeepSeek METHOD和另需已有真实归档的估值；其他外部/研究/恢复profile不在默认有限集合里，不由默认结果关闭其真实验收。

OS夹具最初比较venv启动器PID与实际宿主PID失败；随后立即断言异步终止已结束也失败，均保留原stdout（owner-os-green/green2/green3及owner-final-green，文件名不表示实际通过）。最终验证先对已核实际自有宿主分配Job，再在≤5秒内等待真实死亡和Job进程归零。没有按历史PID或前缀杀进程。初次输入测试还曾缺basetemp父目录，precondition-red/green单列，不当作产品红。

## 保全与未完成条件

[精确保全清单](runtime-preservation.json)只含7个本树自有已停止来源（输入red/green、peer/family red、最终lifecycle、最终OS及最终Chrome），520件/53,035,699字节，源→本树ignored `backend/.roll-data/implementation-evidence/review-fixes` 每份长度/SHA相同，mismatches0，authnamed0；host marker确认不活。没有扫描/删除其他temp凭据，capture时活full-review未保全；最终全套退出0、宿主已结束，该完整组合DB按约定不永久复制。传统Windows长源/目标路径复制失败原日志保留，扩展路径仅补缺、已有文件须相等后全核。

本轮没有新公网取数或真实模型调用，SDK方法仅既有本地固定提供方；12真实DeepSeek凭据/多轮验收仍needs-info，19真实标签/模型/校准仍partial，未解锁其后继或授资格。此前真实原件与真实SDK证据沿各票永久保全继续有效于原版本，不由本轮METHOD、合成账户或默认离线Chrome替代。

最终审阅修复于2026-10-08 07:09收口：Standards1项/Spec2项及5项工程债均完成；343完整后端、15通过2明确跳过默认Chrome、构建与必要定向验证分层保留。当前根仍7c9db98，已合入本树；没有增量拼接全套或重写历史红。

完整测试后仅精确自有full-review宿主marker只读核对：active_hosts0，见[停止检查](full-host-stop.json)；不读凭据、不扫TMP、不杀历史PID。验证期间后端无行为变更，只有源码EOF空行、METHOD pending夹具精度及文档/证据；默认runner用最终完整Chrome命令单独验证。

提交前捕获raw137份与Git索引SHA/长度0差异；根原review capture8份与7c9db98原blob逐字节相同。全跨度58e1d21差异检查0诊断；根原CRLF捕获仅补精确属性，不规范化其原字节。本轮生成helper/JSON元数据用LF，所有raw保持原字节。
