# Ticket 14 — Spec review

相对 `501777e` 只读检查新闻采集、SDK transport、离线抽取、API/UI与测试，依据 [ticket 14](../../issues/14-news-ingestion.md)、spec ID-09。未联网、安装、执行测试或修改实现。定向复核开放 0 项。

**P2 已关闭：坏正文保留列表与标题。** archive现逐实体登记原件；BODY失配的实际字节保存为 integrity_verified=false，标题事实标 BODY_INTEGRITY_FAILED、正文及提取元数据不授。缺文件也保留完整LIST标题。`review-green.log` 为4 PASS/26.13s（原RED保留），公开损坏回归检查PARTIAL/2标题/2原件/禁止全文，符合本票要求。

**P2 已关闭：死宿主恢复并发插入重复标题。** 归档及候选规范化在锁外，避免原件服务另开SQLite连接死锁；`BEGIN IMMEDIATE` 后重读当前RUNNING/owner，只有仍需恢复的一方提交facts+INTERRUPTED并显式commit，另一方不插随机fact。正常采集facts/终态也原子提交。Barrier双初始化回归验证只有2标题且两次读取同一回执；保留漏commit首轮失败，`recovery-lock-final.log` 最终4 PASS/33.18s。

其他观察：来源默认关闭，明确SDK第一页10条/最多3正文，不把文档100条上限称实际覆盖；摘要和全文分列，来源时间未猜时区，提取日期不替代首次收到。固定HTTPS域/文章数字路径、公网DNS检查、禁环境代理及禁重定向构成明确SSRF边界；不接受任意URL/文件或将正文作指令。原HTML与抽取文本分开，查询不发HTTP。

`browser-final.log` 已1 PASS/16.1s，构建已通过，为METHOD工程证据。真实一次新闻来源现已封口：`source-attempt.json` CLOSED_NO_RETRY，4 HTTP/218675字节/10标题事实/4原件逐SHA验证，账户未变，状态PARTIAL且 full_text_verified=false；脚本生产worker=None并显式移除Trafilatura环境变量，未借固定响应或财报预算。`production-browser.log` 1 PASS/11.7s，只读原列表/3HTML，不新采集。Trafilatura reference=UNAVAILABLE，依赖准备失败不能计实际全文抽取；本票保持 partial，不自动重开来源或依赖封口预算。
