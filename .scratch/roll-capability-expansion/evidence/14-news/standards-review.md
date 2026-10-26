# Standards 审查

基线501777e；仅审14新闻服务、三个worker/契约模块、NewsPanel及自有策略/API/测试，排除原SSE等脏改动。未联网、安装、运行测试或修改实现。

原P2两类已关闭：

- prepared请求发送前去除Cookie/Authorization；METHOD主动seed域cookie，逐次断言未发送。
- 死宿主恢复journal原件及有效标题，保持INTERRUPTED无重试；逐个归档原件，坏BODY标记完整性失败且不抹有效LIST。子进程Job随宿主关闭防孤儿。

恢复并发P2已关闭：候选归档/规范化在锁外，BEGIN IMMEDIATE后重读RUNNING及owner，仅胜者同事务写facts+终态并显式commit；另一初始化器跳过。正常采集facts+终态亦原子提交。保留漏commit失败日志；recovery-lock-final4PASS33.18s，含Barrier双初始化后无重复且重放相同。

其余未发现确定的新问题。契约集中限制目标host/path、HTTPS正文、无重定向、公网DNS、调用/字节/时间预算；同键在写事务中重读，目录准备已在try内。来源默认关闭；摘要与全文、来源时间与首次接收、关联未验证分列，UI不执行HTML。

只读日志：review-green4PASS26.13s，Chrome-final1PASS16.1s，build通过。实际新源一次验收已CLOSED_NO_RETRY：4HTTP/218675B、10facts、列表+3HTML原件SHA核对、账户不变；生产只读Chrome1PASS11.7s。脚本exclusive attempt封口且无提取runtime。Trafilatura仍UNAVAILABLE、full_text_verified=false；两次准备失败保留，实际列表/HTML不算真实全文提取。

开放代码问题0；真实全文提取仍partial。未新增HTTP、安装或运行测试。
