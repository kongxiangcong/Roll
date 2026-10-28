# 03 经营假设与共享分析快照验收

日期：2026-10-27（Asia/Shanghai）。本票范围：经营候选、稳定假设版本、冻结输入及不可变共同快照。最终受影响回归**51 passed in262.29s**；真实CODEX最终COMPLETE；01/02已完成，不实施04以后的估值、日报编排、报告和UI。

## 实现与公共边界

[使用文档](../../../../docs/research/company-analysis-api.md)记录`CompanyResearch`及`/api/company-research`入口、限额、引用/时点/冲突校验、原文归档和复用规则。状态模块、候选校验、模型执行、备份引用校验各自独立；既有CODEX执行器仅增加任务分派，无另建无限制模型进程。

开始时HEAD及集成分支均为`41a5f318e43f422c3618ec5744d847bc09d69240`，工作树`D:/dsh-proj/Roll/.scratch/worktrees/rv-ticket03`，分支`codex/rv-ticket03`。只在本工作树写代码；真实03数据在原工作区独立`.scratch/rv03-real-data`，未修改02或生产数据。公共TDD边界已由用户确认，未重复询问。

## 红绿及回归

每轮都通过公开研究服务/API/Backups做一个行为切片，先保存red再green；没有mock内部协作者。系统边界的METHOD worker模拟恶意工具请求，明确不是模型验收。

| 轮次 | 行为 | 实际结果 |
| --- | --- | --- |
| 01 | 冻结后材料不混入；双消费者同快照；重开/幂等 | red01缺入口；green01暴露二次record hash错误；修复后green01b 1 passed |
| 02 | 局部无效引用拒绝，假设支持/反证修订，旧版保留 | red02失败；green02 2 passed（含01） |
| 03 | 模型不可用保留输入、净化失败，不发布假结果 | red03缺入口；green03 1 passed |
| 04 | 全部已知冲突头冻结、无事实锚点验证日期拒绝 | red04失败；green04 4 passed（含前三轮） |
| 05 | HTTP同快照DAILY/REPORT及不可修改入口 | sandbox内TestClient挂起，空red05/green05不是结果；精确终止两进程后重试原API，red05b 404；green05b 1 passed |
| 06 | 备份恢复冻结输入/快照/假设，损坏结构拒绝备份 | red06未拒绝；green06 1 passed |
| 07 | 并发旧候选归档但拒绝覆盖当前父 | red07缺候选读取；green07 1 passed |
| 08 | 同段风险/缓释可双向引用且只计一个来源根 | red08过严规则拒绝；green08 1 passed |
| 09 | 已发布输入直接复用，不重复调用模型 | red09误尝试凭据；green09 1 passed |
| 安全回归 | 恶意来源请求account_write被0工具边界拒绝；错公司局部拒绝保留其他研究 | security-regression 2 passed；账户version0、子进程清理无残留 |

完整命令格式在`tdd.md`。最终受影响回归结果见`final-regression.txt`，不运行全仓所有测试。早期shell编辑还遇到Windows默认GBK读取UTF-8中文运行时文件失败，随后明确UTF-8修复；未更改原件或放宽既有安全门。末行/CRLF规范化仅用于新源码和说明，捕获输出/原文保持字节。

## 真实模型、失败与保留

原件为江西铜业2025年中国准则年报HKEX转载PDF，277页、4,116,411字节，SHA256 `4493c7646001766896e6d4e3b97c702e9ee69423a86f8932df79e29bb75d5303`。第2页核身份，`source-excerpts.json`含10段精确页号/原文/摘录hash，脚本再对实际PDF文本逐字核对。10段只有一个原始来源根，不能算10份独立证据。真实取得时刻取本次now，披露精确时刻及旧精确取得时刻未知，不构成历史PIT。

实际共运行**2次**订阅CODEX `gpt-6.1-sol`，复用用户既有认证路径，未展示或保存明文密钥。每份receipt的`real_model_calls=1`表示该次调用，非累计：

- `attempt01/`：85.385秒，原始输出SHA `1bb388c15a0b7b4d191f566c6d3aa672b172c75e9fb5f336e214eb4b57e5f86e`。得到3项候选，宿主额外加入的“同fact不得同时支持/反证”规则误拒绝风险与缓释同段，因此发布PARTIAL、2项。此规则超出合同且不合理；08轮修正为保存重叠角色并维持单来源计数。原记录/快照未改写。
- 根目录`real-*`：55.436秒，COMPLETE、3项、无拒绝。两项沿原稳定ID修订至version2，新增营运资金假设；快照`e28c866f-5fa5-458d-a48a-1ed1869d40ea`的父为`90c3e7b9-56f9-4ad6-a39a-7c343a1a95f6`。原始输出SHA `e3b0ed564d77a69e6bf43e63a365a749bac1f7453a4d70273c2c2fd2d82ffa72`，与规范化candidate hash分开。保留真实输入、原文、runtime审计、快照、回执。

最终3项是加工费向冶炼盈利传导、美元净敞口、价格/周转/结算向营运资金传导，均为附条件可检验假设，不是事实、概率、目标价或正式动作。下一验证日期均null+原因；工业/贸易/金融、合营权益产量及统计口径限制保留，没有编造FCFF或两年铜周期正常化。生成成功仅表明结构/来源及字面一致性通过，不能表示事实或经济推论已核实。

两次审计均显示enabled skills=0、MCP=0、动态工具0、instruction sources空、无额外来源采集；Windows Job隔离home/cwd，结束remaining_pids为空，临时目录及凭据副本已删除。`real-run.json`保存实际SDK/可执行文件/提示/代码hash等审计；后续幂等和历史省略记录的宿主修补不重跑或改写模型原文，最终回归覆盖最终代码。

## 重放与复现

离线检查读取`real-input.json`、`real-output.raw`、`real-snapshot.json`及`attempt01/`，或重开receipt所指隔离store，按snapshot ID读取。字节hash校验及Backups导出无需模型。`verify_real_replay.py`在最终代码下读取两个真实版本/原始输出并再次导出备份，`offline-replay.json`为PASS、model_calls=0。运行模型会生成新版本，不能称为原文重放。

从本工作树根目录运行已授权的真实新分析（使用现有环境配置，不在命令中填写认证内容）：

```powershell
& 'D:/dsh-proj/Roll/backend/.venv/Scripts/python.exe' .scratch/roll-research-valuation/evidence/03/run_real_analysis.py --source-pdf 'D:/dsh-proj/deep-dive-research/outputs/2026-10-23-江西铜业600362/01-原始资料/2025年报-HKEX.pdf' --data-directory D:/dsh-proj/Roll/.scratch/rv03-real-data --output-directory .scratch/roll-research-valuation/evidence/03/new-attempt
```

原件路径只是验收参数，产品只收bytes/现有来源ID，不依赖开发者外部仓库。脚本在已有store自动绑定当前父版本；另选空的隔离目录可重做初次研究。后续模型行为不可保证原文相同。

未运行：实时公开来源刷新、04/05计算器和经济审核、实际日报/完整报告流水线、浏览器/PDF交付、两个实际盘后周期及整分支最终code-review，均属后续票。现有模型产物不进入ForecastBundle/能力授权/账户/旧实验预算，不读取SEALED。本票完成不代表整体规格完成。

最终01冻结检查PASS（27文件/94门）、compileall退出0、git diff --check通过；仅精确路径暂存，不提交测试basetemp或整个真实store。集成分支同步与提交由本票分支完成后交父代理合并。
