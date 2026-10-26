# 08 完整报告流水线证据

本票仍在验收中。下列记录区分工程METHOD、实际来源、实际CODEX章及公开财务底稿，未把格式完整或模型自述当FULL。真实08资料使用05备份的新副本`.scratch/rv08-real02`，原03/05/07 store均未修改。09 PDF、10独立UI、11概率未实施。

## 固定来源与核心

真实样本为承德露露。共享snapshot `7a430e8b-4172-4598-af21-6fe8600b6b93`、core SHA `37b71966590cb1cb8d0c2898c4bace4c7ec1bc3b216018d2f941204f22dcac1d`均复用05公开来源驱动底稿，不是08新经营CODEX分析。2025价值锚与2026实际取得分开；非历史PIT；BASELINE_RESEARCH conditional，CURRENT_PRICING blocked。

实际有界CNINFO GET取得2023年报和2022更新版（原SHA与回执在real-source-plan/prepare/captured），新材料未纳入该固定core。未填补五家同业、两家国际、五年行业全系列、八张真实图；这些缺口保持FAIL/UNKNOWN。取得旧年报不等于完整整理五年财务，重述调整/NCI不能机械跨版拼接。

CODEX wire范围含公开年报事实、中债/NYU参数、已注册provider历史市值及派生研究假设/内部研究ID；不是仅年报。账户/SEALED内容、秘密、私有绝对路径均未纳入。preview-08.2保存12份逐字command、schema、instructions和51facts固定input；独立递归/人工复核另见原外部审计笔记（待最终复制）。

## 实际失败保留与版本

08.1 job `d60722dc-5dc3-4dcf-8938-e8e9d7424a77`：6真实turn，5原输出；5章因宿主误拒合法Markdown小标题失败，第6取消。原records/raw不改，captured/failed-08.1逐字归档。不能把这一批称有效章。

08.2 job `82629305-575a-45b7-bf25-d6b0b03de028`：9真实turn，8原输出；1与3–8原宿主COMPLETE，2因概念性“一箱”被过宽数值规则拒绝，第9取消。7个COMPLETE仅表示引用/字面校验，不是事实背书。抽查发现正文金额漏币种（宿主注入）、首章将现金流存货调节误述成口径变化、第三章把未获模型上下文误作全报告无假设。按root指令取消并停止仅08服务，保留captured/cancelled-08.2、原input/run/section/status/hash。

最初08.2 worker启动被automatic approval review拒绝（具体公开研究payload授权不充分）；没有绕过。之后纯本地取得12份exact wire并递归审计，依据用户invoke spec“沿用既有CODEX和来源配置”等范围向同一review重新评估，同一启动入口获准后才实际执行。不能改称逐payload人类另行授权。此后因上述质量问题主动取消，与权限拒绝分账。

08.3采用追加host修订，原input/template08.2不改；新的普通任务template08.3。冻结的原12command plan `d51af8d4-b575-4b16-b505-e151377b77cf` / SHA `c0a7e025ec1fa4f34f5345df67582648d74c5099c4fd128c05232fe11bcd7471`在改生产源码之前逐份与原compiler及独立audit比对。新revision单独保存generation/execution源码hash及归档；复用8raw为新section，旧FAILED仍FAILED；语义问题按outputSHA/段/事实作负向隔离，不悄改原文或自签PASS。仅缺4章的新版context compiler选择同一固定packet的有界模型摘要，确切新command SHA与旧plan分开。实际新4调用仍待本地审计/同一review。

## 工程验证

每slice实际命令/输出留在redNN/greenNN/reviewNN。测试通过公开research service/API、原calculator和backup入口，边界worker用明确METHOD本地假进程，未把METHOD当真实CODEX。

- red18：2失败/3通过，复现金额漏币种、概念观察单位误拒；green18：5通过，原数值/尺度保留，中文未绑定财务数值仍拒绝。
- red19：缺公开revision服务而失败；green19：1通过（追加任务/固定input/独立报告/关系校验）。
- review20：sandbox METHOD子进程UNAVAILABLE，1失败/6通过；review20b：相同公开行为在escalated本地METHOD子进程下7通过。
- 最终宽回归原记录final-regression.txt：**177 passed / 5 subtests / 2 failed，959.72s**。两个Reviews失败在无08产品改动baseline独立复现（baseline-reviews.md）：mature_labels实际CHECKED vs旧期望NOT_CONNECTED；unfinished_execution_intents实际0 vs旧期望None。没有为变绿倒退既有业务连接，不能写宽回归全绿。后续仅受影响报告/恢复测试。

## 尚未完成

现已完成最终8项修订测试（final24：8passed52.33s），fresh有模型preview/typed表、financial N/A与报告结构定向检查（green23：11passed75.73s），16源码与4新wire审计、30份源码/12command的排队及8章追加后隔离恢复、27模板/10既有计算合同字节核对。详见[实际命令](commands.md)、[独立新wire审计](independent-host03-payload-audit.md)、host03-wire-verification/queued-restore03/revalidated-restore03/source-byte-check。

但四个缺章的start-roll动作再次被automatic approval review在执行前拒绝：[拒绝原文与风险](host03-review-rejection.md)。root已请求人类明确授权该特定公开+派生预测假设及内部ID payload→OpenAI/既有ChatGPT gpt-6.1-sol，目前pending-human。没有启动新服务/worker，没有重试换入口。

当前job `91a7cc25-2cde-4633-bb23-2113bac5acf4` / host revision `05b8b25b-3462-4568-aca2-1bda13548d9d` / 原input `33ee7a98-3a94-479a-8eca-131264e6a07a` 固定bdb2252f…6a77e。仅离线复用8raw为新section，旧9section/9run/input/job与初始receipt同SHA `612767517ef3653b96fb2b93e8af35ead5e36670dfaf3814d8d5a9eae4640677`，0新run/model/auth/network。下一章9，剩余9/10/REVIEW/CHALLENGE；保持QUEUED/CHAPTERS可继续。`offline-preview03.md`是明确未发布预览，94规则输出为PARTIAL；没有临时发布来冒充验收。

除明确授权后4真实章及最终报告/发布后恢复外，还需在08最终验收前核对完整资料的正向覆盖路径：当前quality临时ledger七类别统一缺口措辞、A/B/C/H附录仍使用通用缺口内容，不能把它当逐类别真实取得/失败回执或资料齐全时的完整附录。当前真实样例这些内容确实未纳入固定底稿，PARTIAL正确；但不能仅补4章就宣称全能力/票已完成。该具体剩余实现工作已交root；当前16源码/4wire先保持冻结，任何后续改算法须追加新执行修订，旧产物保留。

Completion保持in-progress，09未解依赖。该分支是安全WIP检查点，不是已验收实现，不请求merger合08。
