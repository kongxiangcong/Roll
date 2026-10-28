# 当前源码真实排队任务与待人类授权边界

2026-10-28 08:54 Asia/Shanghai。统一修复已合入8dd639145f7daf2146f63ada8b9a5c6069c6bfca。两独立focused verification确认原P1/P3实现已解决，归档于[final-review](final-review/rv-final-review-resolution.md)；METHOD/59+15/UI/build不升级12真实验收状态。

## 已完成的实际准备

1. 根据process02的精确PID/ticks/CLI，只停止本票报告worker27760/22832与旧API39340/29384。自然daily worker12204/38736保持运行。8dd639合入后显式当前backend/src重启API-only8032，launcher18816/ticks639287742206714692、listener50764/ticks639287742207705529；路径与当前源码指纹见api04/preview03-runtime及actual-preview receipts。没有为本次准备载入auth或启动目标worker。
2. IAB本轮不可用，CUA库存确认Chrome连接可用后，新建独立Chrome标签132238161。真实输入000848解析Lulu，明确选择「固定财务基准条件研究」BASELINE_RESEARCH，页面显示非历史PIT/不代表当前可用价格；固定原未估值snapshot c54935d7...，source策略REUSE。
3. 网页创建真实job `9797a495-41a9-4a53-9781-70cc61428841`：QUEUED/ACQUISITION、0章节、0估值候选attempt。实际持久化截至时间 `2026-10-28T00:50:00.000Z` 晚于原snapshot/facts，合法。尝试键入02:36曾在DOM显示但未persist；不重写任务来匹配旧静态wire，以实际保存值和公共preview为准。
4. 公共 `GET /jobs/{id}/valuation/preview` 真正取得完整候选command，纯local无auth/模型/外网。132870字节，SHA **4d5ae801204adb12cc09f2c2f2b391bb99d58f639ef34b3db8dff019f67f48fe**；[exact wire](next-request-preview03/lulu-valuation-command.wire.json)、[可读command](next-request-preview03/lulu-valuation-command.pretty.json)、[实际preview与job](next-request-preview03/actual-valuation-preview.json)、[来源指纹与差异receipt](next-request-preview03/actual-preview-receipt.json)。原c54935无valuation/review绑定，51facts原packet f3e191e8...；不供应已有7a430估值结果或经营模型。
5. 对静态b8c90fb0...5fbeb逐项比较：model/tools/schema/instructions相同，prompt内snapshot/evidence/contract/purpose相同，唯一差异request_cutoff：旧2026-10-26T18:35:27.267742+00:00→实际2026-10-28T00:50:00.000Z。当前source map25项包括报告runtime、候选contract及05/04实际代码。
6. JCC原input4b2f8962...对应exact wire仍92358字节/SHA **a10d0bfd5249b96fc7cd9af37e2a99fc92e5e3cc0f25334339fe6e0d3a4f208f**，没有重取来源或重编改签。首次准备脚本误读job.sections而非section_ids触发KeyError，失败原文保留；修正后公共只读核验完成，没有执行模型。
7. 针对此新队列状态另作一次必要公共备份/恢复：backup1b7a4b3b-5d4e-46a5-a2bc-99ecb6058c27/8884313字节→全新rv12-queued-restored03。新job仍QUEUED/0章节/无valuation attempt，同源代码纯local preview完整对象与SHA4d5...f48fe相等；原c549/input/旧报告/交付及六文件SHA保持，account0，0模型/外源/auth。见[queued03-restore-receipt](queued03-restore-receipt.json)。没有重跑旧A10广审、取源或模型。

## 具体拟执行范围，尚未授权

Root已向人类提交一次明确补充授权问题，目前没有收到答复。此文件只是待审阅工件，**不能执行execute/SDK/有auth worker或API**，也不把08此前四wire许可扩大。

|阶段|正常次数上限|固定范围|
|---|---:|---|
|Lulu新受控经营估值候选|1|以上4d5ae801 exact wire，原c54935及固定51facts，明确BASELINE_RESEARCH/当前重建非PIT|
|Lulu十章及REVIEW/CHALLENGE|12|只读上述候选被宿主接受后派生并冻结的一份同公司report input/core/来源/研究假设，十章1–10加两复核部分；每次完整command/hash须归档，不查询latest或增加来源|
|JCC经营分析候选|1|以上a10d0bfd exact wire，固定32DISCLOSED facts/原研究假设/input，不混入Lulu资料|
|必要纠错尝试|最多2|仅同公司/原固定资料及候选/确定性校验错误上下文的修正；失败照计，不能换资料/重置预算或无限重试|

正常预计14次，总上限16次。目的地仅OpenAI，经用户现有ChatGPT订阅CODEX，模型gpt-6.1-sol；每次90秒、8runtime operations、tools=[]、0来源工具。内容包含已列公开资料、来源派生/候选预测假设、内部公司/input/fact/material/version ID与hash；不含账户/持仓/事件、SEALED、凭据、旧研究预算/训练写入或其它目的地/工具。不会因此给持续daily worker全局加载auth。

之后只有收到root转达的人类可信原文授权，才可沿原合法review路径执行上述具体范围；任何新拒绝均保留并报告，不能改工具/agent绕过。Lulu候选若仍blocked或资料不足，保持有用局部报告，不能改验收或把模型候选当经济背书。

当前0新增模型外发；自然盘后仍0/2（当前尚未首个15:05），12Completionblocked、整体未完成。目标报告worker保持暂停，新job保持QUEUED，现有数据、原报告、旧失败及所有服务收据保留。
