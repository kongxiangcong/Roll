# 09 独立生产整链验收

2026-10-15用户明确批准独立一次预算。integration-plan.json固定600362、8HTTP/18秒/8MiB、零重试重定向、隔离.r09real；之前来源评估不重开。integration-attempt.json已CLOSED_NO_RETRY，实际生产worker=None、AKShare1.19.1：3HTTP、API采集11.623秒、5个报告期、3份原响应SHA验证、查询保存事实一致、账户未变。完整宿主脚本含启动/验证18.288秒，不把该总时长当作网络采集时间。无真实模型/资金/前向操作。

实际收入2026-H1为307154938743元，5期保留合并/CNY元/YTD及匹配原PDF口径；实际可知时点不回填成历史PIT。生产响应见integration-response.json。

Chrome integration-browser-final.log：1 PASS/21.0s，真实SDK采集的同一隔离库重启后只读查询5期、原响应/PDF200、刷新390px无横向溢出，collect请求拦截计数0，未再次取数。首个浏览器命令从根目录执行未进入验收，已停止并保留日志；修正工作目录只影响本地浏览器验证。此前METHOD异常/取消/修订及SDK强杀前缀/API/构建验收仍按acceptance.md引用。

09首个完整利润表切片工程完成，正式能力/PIT/三表或Docling并不随之完成。生产源继续默认关闭（仅隔离profile显式启用）；本次预算封口，不自动重复。
