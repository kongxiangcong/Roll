# 获准批次的两次真实执行与当前硬缺口

2026-10-28。人类已明确回复「授权」，对应root唯一14正常+最多2纠错/总16次的具体问题；可信范围记于integration257dcbaa协调顶段。此授权仅本批固定Lulu/JCC资料、候选及其被接受后派生章节，现有ChatGPT订阅CODEX gpt-6.1-sol→OpenAI，tools=[]，无账户/SEALED/凭据payload，不给持续daily worker加载auth。

本次没有重复请求许可，沿同合法require_escalated执行；只用一次性目标executor。先核当前25源码和两exact wires、原9797/c549/BASELINE，ACQUISITION→SHARED_FACTS→ANALYSIS阶段均无auth，然后在每次可能发送前耐久预留预算。失败也计数，重复同kind明确拒绝，不后台无限重试。当前[预算最终快照](authorized04-budget-final-snapshot.json)为**2/16、纠错0**；14个未用槽不代表还应盲发14次。

## 真实模型/宿主结果

|项目|Lulu估值候选|JCC经营分析|
|---|---|---|
|实际run|fff7d56d-2f44-4d46-9877-a56ab31c4489|a572ee2d-62da-428f-a655-a48c1e32d988|
|实际模型/provider|gpt-6.1-sol / openai，ChatGPT auth|gpt-6.1-sol / openai，ChatGPT auth|
|exact command|4d5ae801...f48fe|a10d0bfd...208f（启动前逐字编译核对）|
|结果|BLOCKED，command_json=null，7项具体gap|COMPLETE，发布共享snapshot34f7ffea-f855-48b8-9a87-d1e33c4569b1|
|原始输出SHA|a11d62d2e1389a2d9da5bd81d623f0f9922c399eb90a8047b68aac19368613cd|a11b11505b7afa850f9651a02cb9312f62e7a4d8cb0c02a48ce20a0c126a83ea|
|经营/估值边界|没有生成05/04新valuation/review/子snapshot；9797现QUEUED/CHAPTERS但0章节|3项经营假设，core977a3bcb8f3cf4731a9ba776155b61cc27ef943d57356c1cebbcb86d0a44b0de；估值仍UNAVAILABLE|

完整实际运行/source/runtime/usage记录：[Lulu](authorized04-first-result.json)、[JCC](authorized04-jcc-result.json)。原始candidate按原字节复制到[authorized04-raw](authorized04-raw/lulu-candidate.json)，没有编辑原raw或改签新input。COMPLETE是03候选/引用边界校验，不是独立经济事实审计或投资效果。两次tools均空；没有来源拉取、fit、SEALED、账户、资格或旧预算写入。

Lulu候选明确缺少完整经营NWC/资本存量、再投资/情景、WACC/桥接/正常化等依据。对固定51facts核查，确实缺少经营NWC库存/固定资产/CIP的数值；现金流营运项目变动不能替代存量，旧表总量文字边界不是完整数值资本滚动。

候选部分表述过严：原05 sourced_rate允许有数值匹配的过去事实及明确proxy假设，不要求RF与计算日期严格同日；wacc.as_of须与config.metadata日期一致。没有输入的EPV/反向DCF可为N/A，不应单独阻断BASELINE DCF。这是已存在合同的澄清，不是放宽规则或强迫模型给价。第一项资本stock仍是实质缺口；不浪费2纠错槽重复要求同包通过。

**未发Lulu12章。** 原授权限定accepted-candidate派生固定report input，null/BLOCKED没有形成这个正向条件，root明确要求暂停章节。没有新PDF产物，不将旧PARTIAL、旧conditional复用或这次BLOCKED升级为A6/A7通过。根的独立原件研究只读提取已取得FY25/24资料，尚未改原frozen51packet、原run或活DB；之后若新事实/输入有变，必须透明比较scope与payload，不能用此处未用预算自动扩展。

## 新JCC core、旧对象与真实网页

[capture receipt](authorized04-capture-receipt.json)及[新daily原文](authorized04-jcc-daily.json)验证：新经营理由纳入固定2026H1数值、三项假设与反证/未知事件日期，新生成时间真实保存。旧e28c866f/corecce09e5...对象不变，原main库两份报告/原delivery不变，account0；保护metadata另存。新的经营候选不是当时15:05已取得，不能回填历史PIT。

当前源码API8033/web5213的真实Chrome132238163验证：默认仍保留既有量价任务固定旧e28版本；用户点击「读取最新共享版本」后实际选择34f7ffea，显示新财务关注理由、三假设及当前估值UNAVAILABLE，页面明确新版本与旧量价包不同。点同快照报告链接后，报告入口固定34f7ffea，A/H分别CNY/HKD，显示尚无已发布报告；未点击新报告任务，未新增模型。此为真实共享引用与版本读取证明，不冒充完整JCC报告。

## 升级接管与离线区间

为当前源码网页重启8033时，正常守卫报UPGRADE_REQUIRES_STOP_ALL_LOCAL_HOSTS，因为旧natural worker仍活着；[失败原文](authorized04-daily-api-upgrade-failure.txt)保留，未绕过守卫或把初次启动当成功。root随后明确批准必要受控升级。

先只读确认相关5个队列/在途均0，再逐PID/ticks/CLI只停止自身旧natural worker12204/38736，正常升级同库API8033（launcher51440），以同公共source策略/独立runtime和无auth/.env不读重启worker（launcher2620）。精确stop `2026-10-28T02:02:58.4636577Z`，首次公开确认RUNNING/last_error=null `02:04:07.937887Z`，停到确认恢复上界69.47423秒。source enabled/revision/scope/8calls18s0retry/cooldown/bytes逐项未变。见[daily-upgrade04-complete](daily-upgrade04-complete.json)。当时10:04未过15:05，natural scheduled仍0/2，未补造。

## 新真实结果的必要恢复

[恢复receipt](authorized04-restore-receipt.json)：Lulu公共backup e477c142.../9039601字节→全新rv12-executed-restored04，实际BLOCKED run/raw/exact原wire/job/原c549相等且0章节；JCC backup f10ec7d1.../9115664字节→rv12-daily-executed-restored04，新COMPLETE run/raw/newcore/daily与旧snapshot相等。恢复过程0模型/外源/auth，account0。没有借恢复重放模型。

12及整体仍未完成：A2完整双工作流、A6正向完整研报、A7新完整生成/PDF、A8两自然盘后周期未通过。0/2只按实际scheduled记录判断，手动真实source和模型次数不计周期。当前先保留确切失败、剩余预算和可用JCC研究，待真正足够且scope明确的资料继续。
