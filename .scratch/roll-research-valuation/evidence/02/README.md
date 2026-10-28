# 02 公司身份、共享证据与核查记录验收

开始：2026-10-26；完成记录日期：2026-10-27（Asia/Shanghai）。结果：complete（仅02）。最终回归42 passed in246.15s；03依赖可解除，整体功能未完成。

## 范围与入口

- 公开研究服务/请求模型：`backend/src/roll/research/company/`；HTTP入口在`api.py`，由现有app挂载。
- 用法与分页、时间和来源限制：[company-evidence-api.md](../../../../docs/research/company-evidence-api.md)。
- 沿用01共享合同；只实现身份、材料、事实版本/冲突和核查，不实现03以后的模型、快照、估值或报告。
- 开始时`HEAD`与integration均为`13caf303195c5316000eb906911d86e7f67d6d02`，祖先检查退出0；独立分支`codex/rv-ticket02`，未修改原工作区生产源码。

## 验收覆盖

| 要求 | 实现与验证依据 |
| --- | --- |
| A1数据层：公司/上市证券、A/H、同名歧义与隔离 | 同公司A/H保留不同listing；明确登记第二公司与同名别名，歧义不默选；原市场身份冲突拒绝、跨公司材料/事实拒绝。服务/API测试，无全市场覆盖承诺 |
| A3数据层：成功无新增、部分失败、失败和重述 | 逐来源/范围回执、准确最后成功与新材料数；新采集回执重用未变材料；报告期与实际取得/可消费时间分列。过期判断和经营结论留06，不把核查状态当经营判断 |
| 旧事实/原件不覆盖、未知不补写 | append-only fact/version/supersedes、冲突双方与理由；读取校验内容hash。导入未知披露时刻保持null，无任何历史PIT提升 |
| 同材料供双用途 | DAILY/REPORT读取同材料ID/规范归档；服务重开后记录和字节相同。尚无日报/报告消费者实现，不能声称A2完整通过 |
| 既有来源复用 | 现有市场快照、财报和新闻记录适配，不新增服务或隐式联网；METHOD不变REAL；余额时点/YTD、新闻关联/正文时间/转载根有实际旧采集API集成测试 |
| 迁移、备份恢复 | 新表原子创建并保持原账户schema版本；evidence_archives同一权威原件；现有Backups导出、隔离restore及服务读取hash验证，损坏结构记录拒绝备份 |

## 测试边界与真实材料

用户已确认公开研究服务/API、计算器、网页及恢复边界。本票采用公开服务/API、现有来源采集入口及Backups恢复；系统边界以外不mock内部协作对象。唯一直接SQL写入用于模拟存储边界损坏，结果均通过公共读取/备份入口断言。账户版本0保持不变；未触碰正式Decision/CapabilityGrant/ExecutionIntent或旧研究预算/SEALED。

红绿命令与实际输出见`tdd.md`及`red01.txt`至`red12.txt`、各`greenNN.txt`。新增用例均为METHOD/offline，不声称真实模型或实时来源。首次news转载绿测因供应器给SDK列表传https（既有SDK合同要求http，正文capture要求https）而被旧校验拒绝，见`green09.txt`；仅修复测试供应器后`green09b.txt`为2 passed，保留失败未改旧来源闸门。

真实样本由`archive_real_sample.py`通过公共服务导入：江西铜业2025年中国准则年报HKEX转载原件，277页、4,116,411字节，SHA256 `4493c7646001766896e6d4e3b97c702e9ee69423a86f8932df79e29bb75d5303`。真实本次received_at为`2026-10-26T16:10:18.072316+00:00`（上海2026-10-27 00:10:18）。披露精确时刻未知，保持null；旧取数台账仅记录2026-10-23日期，不能补成精确取得时间。PRC GAAP转载与另份IFRS H股报告分开。

已核对PDF第2页公司名/代码、归档hash、重开读取和备份导出。回执：[real-sample.json](real-sample.json)，命令输出`real-sample-command.txt`。归档数据保存在回执所载的工作区隔离`.scratch/rv02-real-data`目录；文件未混入生产运行路径，不复制外部参考项目的权限文件。无实时抓取或模型调用，不证明当前基本面、估值或报告质量。

复现（工作树根目录）：

```powershell
& 'D:/dsh-proj/Roll/backend/.venv/Scripts/python.exe' .scratch/roll-research-valuation/evidence/02/archive_real_sample.py --source-pdf 'D:/dsh-proj/deep-dive-research/outputs/2026-10-23-江西铜业600362/01-原始资料/2025年报-HKEX.pdf' --data-directory D:/dsh-proj/Roll/.scratch/rv02-real-data --receipt .scratch/roll-research-valuation/evidence/02/real-sample.json
```

此脚本的外部PDF参数只是本地验收来源，不是生产依赖；产品导入只接收bytes/base64或既有来源记录ID。

## 最终检查

最终回归命令与结果保存在`final-regression.txt`，包含全部02新增公开行为测试以及既有backup/assistance回归；实际结果：**42 passed in246.15s**。01冻结检查PASS（27文件、94闸门）；compileall退出0。git diff --check初次发现当前票文本编辑产生的尾部空行，已规范化后重检；不修改冻结参考文件。

未运行：新功能真实CODEX、实时财报/新闻刷新、浏览器/PDF报告渲染、两个实际盘后周期和整分支最终code-review；属于后续票，不用本票替代。资料年龄/过期策略、worker公平队列、取消/阶段恢复、经营假设/快照与实际日报/报告仍未交付。

提交前staged检查还识别到PowerShell生成的新源码末行混合CRLF和捕获日志CRLF。新源码/说明规范化为LF；按仓库既有做法为本票捕获txt/json增加限定.gitattributes，原始输出和回执字节保留。未改测试结果、来源原件或01冻结文件。
