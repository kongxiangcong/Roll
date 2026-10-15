# 12 PDF派生工程交付与真实运行缺口

Completion保持partial。新增已归档财务PDF的选页解析、持久化记录、取消和查询API，以及单股利润表/三表中的表格、文本、原页和边界查询。原PDF继续使用现有pypdf路径，解析失败仍能查看原件；派生内容不覆盖财务事实，不执行文档指令。

## 已交付工程

仅接受已有财务事实绑定的SHA，校验原件字节、页数与1—8页范围，PDF上限16MiB。幂等命令保存RUNNING/终态，进程失联转为INTERRUPTED_NO_AUTOMATIC_RETRY；输出目录失败也保存FAILED，不留下永久RUNNING。取消终止工作进程。实际适配器预设离线网络、CPU两线程、120秒与2GiB进程/作业内存限制；这些是实现约束，尚无实际Docling执行证据。

派生保留原件SHA、页码、边界、解析器版本、原始文本/表格及置信信息。页码越界或身份不符拒收；缺页、供应商部分成功明确为PARTIAL。有效身份下的失败尝试也保存为独立原件供查看。页面原样显示括号负数、单位与脚注，要求人工核对跨页表头与结构化数值；不自动修补或覆盖。METHOD和真实本地运行标记分开。

## 验收证据与限制

- api-red.log保留最初缺少服务的失败。attempt-final.log为最终API 3通过/27.19秒，覆盖真实已归档PDF加合成解析传输、幂等、重启、取消、损坏/越界、目录失败恢复、PARTIAL和失败尝试原件。该正向派生是METHOD，不是实际Docling推理。
- browser-final.log为METHOD Chrome 1通过/18.4秒；最新UI补充原表边界与失败尝试链接后，browser-latest-chrome.log为1通过/19.3秒。browser-latest.log保留误用factory名称导致启动失败，browser-latest-fixed.log保留默认Playwright浏览器未安装的失败；改用已安装Chrome完成复验，没有下载浏览器。
- build-latest.log为最新TypeScript/Vite构建通过。双只读审查见spec-review.md和standards-review.md；代码问题开放0，真实运行缺口仍保留。

## 依赖准备：已关闭，不自动重试

选定官方Docling 2.139.0的docling-slim PDF、CPU模型与RapidOCR ONNX中文路径，业务依赖未修改。runtime-plan.json记录独立环境、下载1.5GiB、安装4GiB、解析及预取上限；没有模型权重下载，也没有提交PDF到外部服务。

各次依赖解析的原始错误、缓存诊断和回执均保留。最终pip-bounded-resolution-receipt.json为CLOSED/RESOLUTION_WALL_TIME_LIMIT/600.038993秒，跟踪146次官方PyPI/文件源请求后仍无完整依赖解析报告。未安装解析运行时，未执行install_runtime.py；该脚本仍要求成功的解析报告，当前条件不满足。临时绕过本机代理只作用于隔离预演，未改系统配置。

docling-reference.json保持UNAVAILABLE。代码包/权重完整指纹及选定模型许可、实际可读财报/复杂跨页表格/扫描样例的真实推理与资源测量均未完成，不勾选完成条件，不把METHOD或依赖元数据访问算成真实验收。再次准备依赖需独立记录新的有限计划，不静默重开这次封口尝试。

官方依据：[2.139.0发布元数据](https://pypi.org/project/docling/2.139.0/)、[版本配置](https://raw.githubusercontent.com/docling-project/docling/v2.139.0/pyproject.toml)、[离线选项](https://docling-project.github.io/docling/usage/advanced_options/)、[模型下载实现](https://raw.githubusercontent.com/docling-project/docling/v2.139.0/docling/utils/model_downloader.py)。这些支持选型与适配设计，不能替代选定权重许可核验及真实运行。

13仍依赖本票真实完成；继续独立且依赖09已解除的14。09和10的真实来源预算继续关闭，不重复采集，不改变账户、资格或真实前向起点。
