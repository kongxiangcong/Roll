# Ticket 23 本地工程验收（2026-10-11）

Completion **partial**。本地工程已完成，两个真实 provider 分别审阅此批实际材料的接入尚未完成。当前候选没有真实协议终点、完整必需检查或正式能力。本记录不将固定输出/loopback/METHOD 证据升级为真实模型审阅或真实统计结项。

## 结果与边界

- 公共 FastAPI + 真实 SQLite + 隔离归档最终定向回归：**39 passed，345.47s，exit 0**，见 [final-api.txt](final-api.txt)。9 项新审阅测试与原 backend-switch / Codex / DeepSeek 取证测试同轮运行，没有重跑完整后端。
- 实际 React/FastAPI 浏览器：**1 passed，56.6s**，见 [browser-final.txt](browser-final.txt)；用户冻结、影子验证、审阅、导出、刷新恢复流程通过。审阅 worker 为有界固定输出 METHOD 工具过程；不是实际 Codex 审阅。浏览器截图 [technical-review.png](technical-review.png) 已查看。
- TypeScript/Vite：58 modules，**2.00s，exit 0**，见 [build-final.txt](build-final.txt)。此前错误的依赖路径和缺省 Chromium 缓存，以及业务按钮缺失红回执分开保留；最终使用现有 msedge 和锁定依赖。
- CODEX 固定输出进程与 DeepSeek 真 Agents SDK + 合成本地 loopback 都读取同一冻结材料、调用宿主确定性复现并提交相同 ReviewRecord 契约。后者证明 SDK/契约接线与进程约束，**不是 DeepSeek 外部真实审阅**。

ReviewRecord 绑定材料指纹、后端/模型/配置/SDK/宿主源码版本、时间、每次工具读取及引用、宿主复现 SHA、异议和局限。错误结构/伪造引用/伪造复现/缺乏处理证据分别 INVALID_OUTPUT，原始输出及重试关联保留。取消、超时、后续后端选择、重启持久化与归档损坏拒绝通过；审阅和 acquisition 共用原子并发槽。两个工具仅允许已列明材料读取及宿主复现，沿用既有私有凭据管道、Windows Job、任务隔离与清理。

审阅记录完整、阻断异议处理、实验完成、自动判决和正式能力分列。即使模型表示赞同，宿主未完成检查/G7/其他非 PASS 证据仍保留。局部模型历史清单标为“记录时”，当前审阅状态独立恢复。页面与包始终标注“经自动验证与模型技术审阅，未经人工独立复核”。不会增加人工签字条件或 Agent 签发能力。

已完成终点与检查的 FAIL/INCONCLUSIVE 工程例通过同一公共 API/SQLite/导出逻辑；宿主文件工厂仅在显式 test 环境加载且冻结来源，生产拒绝，客户端不能声明终点或 PASS。实际候选仍 preliminary；真实终点由 33 取证。risk_policy 使用自己固定 evaluation/input/dependency 指纹与五门槛复现，不借 profit 的 G3/G4/G7 或审阅记录签字；funding.py/risk_policy.py 未改。

本地完整导出绑定完整冻结输入、协议、模型/校准工件、相关代码/数据、全部尝试/输出/结果/异议/局限。宿主验证每个本地归档与源码引用；不循 metadata 读取尚未准入 SEALED，不导出整个数据库或无关原件。向 provider 的精简材料与本地完整导出各有明确边界。

## TDD 回执

按行为逐项红/最小实现/绿推进，原输出保留：01 冻结审阅与持久化（404→通过）；02 宿主缺口不可被赞同清除（true→false）；03 全量本地导出（缺 registry 源码→完整）；04 risk_policy 独立材料（404→通过）；05 终点 FAIL/INCONCLUSIVE 工程材料（构造不支持→通过）；06 DeepSeek SDK 版本绑定（缺版本→通过）。见 `01`—`06` red/green 文件。06 先前 fixture 内容格式错误单列，不冒充业务红。07 结构/引用拒绝及 08 取消/超时/并发回执单列，最后均收入39项最终回归。

## 实际资料、外发阻塞与保全

21 停止的一致副本通过只读 SQLite backup 建立 23 隔离副本；3822 原件，701,484,403 bytes，逐件 SHA/长度差异0，源 DB 前后相同。根原19没有启动或修改，没有新拟合、预算消耗、SEALED 或真实前向。副本位于 `D:\dsh-proj\Roll\.roll-data\implementation-evidence\23\actual-current-copy`。实际 validation `baf981b6-b2bf-4f6f-b46f-1726f261de8e` 当前 G4/G5 FAIL，其余 INCONCLUSIVE。

自动审批审查拒绝了 `actual-review.py` 实际外发，原因是“用户仅授权继续实现 tickets，未明确授权这批敏感材料分别发送到这些具体目的地”。拒绝发生在启动前；**0 actual review runs，0 external transmissions**。根代理已向用户展示这批可审查材料及目的地并请求明确外发授权，当前未收到批准；没有重试，也没有换合成外发绕过。

纯本地材料预览 [provider-material-manifest.json](provider-material-manifest.json) 指纹 `35e42b0da239e415e2b7e3f3f0c9243d4e32a3e3bc02ceac92a92b17559ac9da`，7份内容181647 bytes，8次工具结果最大186512 bytes，初始 CODEX/DeepSeek command 4824/4827 bytes。正文包含冻结协议/全部尝试元数据、验证门槛及局限、models/execution/shadow/statistics/validation五份相关源码、宿主复现结果；排除账户金额/持仓/身份、完整原始输入、SEALED、凭据、整库和无关原件。目的地为 OpenAI Codex ChatGPT-auth runtime（gpt-6.1-sol，endpoint由现有SDK选择）和 `https://api.deepseek.com/responses`（deepseek-flash）。历史上下文重复与模型输出不能被上述正文数字误称为真实最终联网字节；实际外发尚未执行。

浏览器停止后640文件保全到根 `.roll-data/implementation-evidence/23/browser-method-final`，全部 SHA/长度差异0，明确排除 METHOD synthetic auth.json。审批packet和仅本地完整材料/actual-copy清单13文件保全到同级 `provider-approval`，原预览路径继续保留供待决审批。可长期点击的[根审批清单](D:/dsh-proj/Roll/.roll-data/implementation-evidence/23/provider-approval/provider-material-manifest.json)与当前待审清单字节/SHA一致；packet各文件逐件同SHA。逐件见 [preservation-manifest.json](preservation-manifest.json)。完整实际输入及packet仅保存在运行证据目录，不提交源码仓库；manifest中的路径仍指向原待审预览，根保全副本按文件名在 `provider-approval/provider-materials` 可定位。不得将本地完整 input/export 外发。

[source-before-final.json](source-before-final.json) 与 [source-after-final.json](source-after-final.json) 记录最后校验阶段源码稳定性：除 validation.tsx 外所有列明源码 normalized SHA 相同；validation.tsx 做 CRLF→LF 并删一个末尾空行，向后快照内容加一个换行即精确匹配前快照 normalized SHA，语义未改。12个19 model-code依赖相对19基线内容均不变。源码快照在最后校验阶段采集，不声称之前每项红/绿版本均有完整源码快照。

## 未完成条件

待用户明确批准此批材料向上述两个目的地发送后，核 packet SHA 不变，在最终代码版本分别执行一次真实 CODEX 和 DeepSeek 审阅并保留结果；不要求二者赞同或把重复调用变成获取期望结论。两后端真实证据不足使 AT-51 与 ticket23 保持 partial。实际终点/必需检查/G1—G7 及正式能力按各后续票承担，当前工程 METHOD 和审阅成功不能解除。

`actual-review.py` 已改为相对当前 checkout 定位 root `.env`/根23副本/根审批packet，不依赖将被归档的 ticket23 工作树。获批之后从集成根设置 `ROLL_ENV=test`、`PYTHONPATH=D:\dsh-proj\Roll\backend\src`，用根venv执行 `.scratch/roll-p0/evidence/23/actual-review.py`；脚本首先核验上述固定指纹与每个packet SHA/长度，读取已批准material，不再创建不同材料，并拒绝已有review attempts时自动重复。记录写根 `.roll-data/implementation-evidence/23/actual-provider-results`。**本次只编辑及静态编译此接续脚本，没有执行它。**
