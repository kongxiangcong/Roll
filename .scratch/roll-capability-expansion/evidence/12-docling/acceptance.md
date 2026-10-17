# 12 PDF派生工程交付与真实运行缺口

Completion已具备实际运行时与真实 PDF 验收（2026-10-18）。新增已归档财务PDF的选页解析、持久化记录、取消和查询API，以及单股利润表/三表中的表格、文本、原页和边界查询。原PDF继续使用现有pypdf路径，解析失败仍能查看原件；派生内容不覆盖财务事实，不执行文档指令。

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


## 2026-10-18 实际 Docling 运行时与真实 PDF 验收

旧 600 秒依赖解析记录保持 CLOSED。新独立尝试 DOCLING-DEP-ATTEMPT-02 经环境既有 HTTPS 代理访问官方 PyPI：250 请求、394,962,657 字节、88.821 秒，83 个 wheel 全量 SHA256 锁定后离线 `--require-hashes` 安装成功。隔离 venv：docling-slim 2.139.0、docling-core 2.101.1、docling-ibm-models 4.0.3、docling-parse 7.22.3、torch 2.10.0（CPU 推理）、torchvision 0.25.0、transformers 5.20.1、rapidocr 3.10.0、onnxruntime 1.31.0；业务 venv 未修改。

模型尝试 DOCLING-MODEL-ATTEMPT-01：官方 docling-layout-heron（Apache-2.0）、docling-models TableFormer accurate（CDLA-Permissive-2.0）与 rapidocr 自带 PP-OCRv6 small 中文/英文 ONNX；47 文件、701,230,057 字节、99.3 秒，低于 1.5GiB 上限。离线解析设置 HF_HUB_OFFLINE/TRANSFORMERS_OFFLINE 且适配器导入前拒绝 socket。

真实运行（全部为 09 票已归档 PDF，经归档 SHA 绑定）：
- 2025 三季报第 10 页（文本型）：SUCCESS，9 文本 / 2 表（31×3、2×3），86.8 秒。
- 2025 年报第 102—103 页（pypdf 零文本、纯图像扫描页）：SUCCESS，22 文本 / 2 表（13×4 属第 102 页、29×4 属第 103 页），48.6 秒；OCR 识别出“合并利润表”“营业总收入 544,623,484,060”等真实数值。
- 公开 API：2025 三季报第 10 页 COMPLETE，派生工件 65,938B；年报第 102—103 页 COMPLETE，工件 115,755B；页码均为 [102,103]，账户版本 0→0，network_calls=0，原 PDF 归档仍 200。
- 跨页边界：两页各自成表、各自保留页码与 bbox，告警明确 `CROSS_PAGE_HEADERS_AND_FOOTNOTES_NOT_AUTOMATICALLY_MERGED`，不静默合并或改数。

审查修复（真实运行暴露）：
1. 子进程环境缺少 USERPROFILE/HOME → `Could not determine home directory`；补齐 home 相关变量。
2. 缺少 USERNAME → `No username set in the environment`；补齐 USERNAME/USER 等。
3. 实际置信度含 NaN 导致 FastAPI JSON 序列化 500；新增 `json_safe` 把非有限浮点转为 null，并在读取旧记录时同样净化。旧 FAILED 尝试与旧 500 记录均保留，未删除。

回归与页面：`regression.log` 3 passed/29.18s；`real-browser-green.log` 真实副本 Chrome 1 PASS/36.9s，页 10 表格单元 7,089,672,734、原 PDF 第 10 页链接 200、390px 无横向溢出（`real-mobile.png`）。构建沿用当前源码，前端无改动。

限制：未对 OCR 全页字符准确率做人工基准；扫描页来自年报中真实无文本层页，不是另行构造的扫描件；跨页表头不自动合并，只保证边界与告警；权重许可按官方模型卡/仓库元数据记录，不构成法律意见。系统仍 `system_usable=false`，不改账户、资格或真实前向起点。13 的 12 依赖解除（11 已完成），可进入 13。
