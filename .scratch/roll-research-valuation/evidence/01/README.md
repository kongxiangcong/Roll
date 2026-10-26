# 01 合同与参考映射验收

日期：2026-10-26。结果：complete（仅第01票）。后续执行入口02，计算器、服务、UI、真实取数/模型及联合验收尚未实现或运行。本票不宣称整体工程完成。

## 变更与复现入口

- [公司研究合同](../../../../docs/research/company-research-contracts.md)：公司/证券、事实/核查、经营假设、共享快照、估值与经济审核、三类变化、任务/报告、错误、特征与需求归属。
- [模板映射](../../../../docs/research/company-report-template-map.md)：速览、四部分十节、9.1—9.9、附录A—I及新增底稿，原规则逐项适配与部分交付。
- [ADR0006](../../../../docs/adr/0006-shared-company-research-snapshots.md)和[GLOSSARY](../../../../GLOSSARY.md)：共同快照与账户/资格边界，术语定义不混入实现细节。
- [来源映射](source-map.md)、[逐项闸门清单](gate-rule-map.json)、[冻结manifest](../../../../docs/reference/deep-dive-research/20261026/manifest.json)：27文件实际hash及94处检查调用。来源文件与MIT全文一同留存，可离线复查，不依赖开发机参考路径。

在集成工作树根目录运行（已安装Python可替换解释器路径）：

```powershell
D:/dsh-proj/Roll/backend/.venv/Scripts/python.exe .scratch/roll-research-valuation/evidence/01/verify_contract_freeze.py
git diff --check
```

`verify_contract_freeze.py`是文档完整性检查，读取仓库内快照，逐文件核验hash/字节数，并从原闸门AST重新提取所有检查调用与逐项映射比对；不执行参考代码，不是后续计算器或产品测试。

## 命令与实际结果

| 操作 | 实际结果 |
| --- | --- |
| `git status --short --branch`、`git merge-base --is-ancestor codex/roll-research-valuation HEAD`、`git rev-parse HEAD codex/roll-research-valuation` | 本票独立工作树分支codex/rv-ticket01；开始时两者均ebe3fc8，祖先检查退出0，无原工作区编辑 |
| 读取项目AGENTS、3个agents规则、spec/01/索引、GLOSSARY、ADR0001/0004/0005、domain-modeling格式和tdd技能 | 已读；本票要求合同走查，不新增产品测试；TDD技能边界确认不影响本票文档验收 |
| 读取现有目录/证据/财报/assistance/worker/backup/账户计值入口 | 发现Assistance硬编码与独立线程、A股身份验证、备份仅允许受控目录，迁移边界已明确。探索时猜测的market/identity.py、registry.py/service.py、runtime/worker.py/store.py不存在；通过实际directory.py、worker.py、evidence.py核对，未以猜测路径定合同 |
| 读取参考02/15、fundamental_valuation、check_gates、测试、LICENSE及上游通知，按字节复制 | 27个实际源文件冻结成功，references全部保留供逐项核对；配套书籍未复制 |
| 参考仓库`git -C D:/dsh-proj/deep-dive-research rev-parse HEAD`及`status --short` | Permission denied，Git版本/dirty状态未核实；spec允许以实际文件hash如实记录，不伪称提交版本 |
| 运行`verify_contract_freeze.py` | PASS：27 frozen_files_checked、94 gate_call_sites_mapped、source_checkout_required=false |
| `git merge codex/roll-research-valuation --no-edit` | 从ebe3fc8快进到d068092，包含父代理保存的基线回归记录；无冲突。git自动维护提示unreachable loose objects，未做prune/clean |
| `git diff --check`与文档链接检查 | 完成时结果见[verification.json](verification.json)；不把文档结构核验当作产品通过 |

父代理基线回归是[独立记录](../baseline/README.md)的28 passed in100.63s；01未再次运行基线、不将该结果计入新功能验收。

## 合同走查

| 场景 | 合同推演与结论 |
| --- | --- |
| 公司同名/A+H | resolve返回歧义候选，listing映射同公司却保留证券/币种/报价时点；A+H缺同日A/H价或汇率拒绝反推；合同可表达A1 |
| 成功无新增/部分失败/失败/重述 | check结果与经营假设独立；0新增不代表经营未变；最近成功不被失败刷新，重述保留两值与冲突理由；合同可表达A3/A5 |
| 同一快照日报/报告 | 同snapshot ID与规范化核心payload hash；后到材料只能新快照，旧report保持原hash；合同可表达A2及恢复引用关系 |
| 三类变化同现 | 固定经营→价格→参数/方法顺序，对照固定项与路径依赖；不兼容单位/方法NOT_COMPARABLE；永续示例仅条件运算；合同可表达A4/A5，不宣称已实现数值计算 |
| 银行/保险或江西铜业口径缺失 | 保留9节方法/缺口；不强套FCFF或升审核，诊断区间usable=false，财务章节继续；不支持专用模型的范围可呈现 |
| 来源/模型/渲染失败与重启 | 阶段检查点、有限重试、owner/lease、取消、幂等发布、FULL/PARTIAL及格式交付独立；原件和工件都登记evidence_archives受备份枚举 |
| 研究/正式资格隔离 | 新API命名空间不调用账户计值/Decision/CapabilityGrant/ExecutionIntent写路径；情景权重不变概率；ADR0005/0004与旧预算/封存约束保持 |
| 模板与全部需求 | 速览/四部分/十节/原附录九项无删除，9节九子节显式映射；质量失败保留并部分交付，94检查调用逐项登记；spec§1—12到02—12票及A1—A10有归属 |

以上是文档走查，不是A1—A10的运行通过证据。三个01验收框均达到：合同完整表达、资格/许可证相容、规格与后续票对应。02依赖可解除，其他票Completion仍not-started。

## 数据、模型、限制和失败

本票使用本地源码/文档与冻结参考文件；无外部服务、无行情/财报抓取、无CODEX或其他模型调用、无账户/预算修改。参考JSON中的合成样例只供04回归准备；江西铜业样例需02归档和05/12实际核查，不能当当前估值。生产运行环境不需保留D:/dsh-proj/deep-dive-research。

未运行：估值算法测试、实时来源、真实模型、浏览器/PDF渲染、两个实际盘后周期、备份恢复、全功能code-review。这些分别属于后续票；不能用本票的冻结完整性PASS替代。参考Git版本未核实是已记录限制，不妨碍以hash冻结文件。没有改变金融语义、验收或串行依赖。

2026-10-26 用户经父代理确认后续TDD公开边界：研究服务/API验证身份、证据、快照和报告，计算器入口验证估值，网页验证流程并覆盖备份恢复。后续代理沿用该确认，不重复询问已确认范围。
