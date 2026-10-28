# 固定研报文件交付

09在已发布报告上追加不可变文件交付，不重算共享快照、不重新调用模型，不改原报告的PARTIAL/FULL或经济审核。原报告的delivery_status是当时状态；当前文件状态读取独立交付版本。10可直接使用以下接口。

|接口|用途|
|---|---|
|POST `/api/company-research/report-deliveries`|创建MD/PDF交付版本|
|GET `/api/company-research/report-deliveries/{delivery_id}`|固定manifest、状态、错误、renderer、文件描述符|
|GET `/api/company-research/reports/{report_id}/deliveries?limit=50&offset=0`|新到旧历史，返回total/deliveries|
|GET `/api/company-research/report-deliveries/{delivery_id}/files/{artifact}`|仅允许markdown/pdf/manifest/references/valuation/input|

请求示例：

```json
{"report_id":"published-report-id","idempotency_key":"user-export-1","render_pdf":true,"parent_delivery_id":null}
```

同报告同幂等键、相同请求返回同交付；不同请求返回409。显式重试使用新键和parent_delivery_id，形成新版本；父交付必须属于同报告。原PDF、Markdown与旧失败记录保留。报告重生成本身仍经08生成新的report_id，09不修改已有report。没有PDF时下载pdf返回404，其他文件保持可用。

状态为COMPLETE（PDF完成）、MARKDOWN_ONLY（明确不渲染）、PDF_FAILED（MD/研究保留）。render_error提供code/detail/retryable；包含字体不可用、缺图/不安全图、超时、繁忙和一般失败。每宿主同时至多两个渲染；子进程默认45秒，可用ROLL_REPORT_RENDER_TIMEOUT设置0.01–90秒，输出限25MiB/300页。子进程只接收必要系统环境、固定源码路径和字体配置，不继承凭据配置；无浏览器、HTML执行器或网络资源加载器。下载为attachment并设置nosniff及禁止活动内容的CSP。

生产安装从backend的pyproject.toml/uv.lock获取ReportLab4.4.9及依赖。字体优先ROLL_REPORT_FONT指定的、获许可的中文TrueType/TrueType collection；否则查Windows宋体或Linux文泉驿/AR PL UMing系统字体。字体不可用明确失败，禁止替成缺字字体或把私有Codex缓存路径硬编码进应用。字体只记录SHA，不复制系统商业字体进仓库。QA使用Poppler是开发验证依赖，运行服务不依赖Poppler。

PDF适配冻结参考md_to_pdf.py的封面/目录/正文/页码/书签布局，保留MIT参考及来源；用ReportLab重实现安全纯文本管道。原HTML作为文本转义，链接作为可读文字；图只接受冻结packet.charts中绑定、哈希校验的静态SVG，支持host生成的rect/polyline/text，不接受外部URL、文件路径、data URI、SVG脚本/事件/外部引用。缺图失败保留MD。表格适配既有报告中的行间空行，独立新表头与分隔行开启新表。

manifest绑定report/input/core/template/quality及实际交付字节SHA；references包含原件坐标、事实和同行事实；valuation保留原固定valuation_binding、core及追加宿主修订中的固定计算上下文，绝不查最新值。所有工件复用EvidenceStore登记；备份同时核报告/交付/manifest/固定引用/父版本及实际文件字节。恢复后可离线读原文和文件，不重调模型。损坏或不匹配时409，不改成成功。

09真实文件验证基于08承德露露既有PARTIAL报告；没有额外取得行业/同行/图表来源，CURRENT_PRICING仍blocked，BASELINE_RESEARCH仍conditional。METHOD图/缺图/长URL/超时用例独立记账。完整公司输入到下载浏览器流程由10实现，A6/A7联合验收由12汇总。
