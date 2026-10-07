# 12 · DeepSeek受控取证

2026-10-08，Asia/Shanghai。开始2026-10-08T03:39:36+08:00。票状态 **needs-info / partial**：工程接入可运行，真实DeepSeek模型、权限和多轮任务尚未验收；不关闭12或解锁13。凭据位置的既有问题待答，无新增索求。

初始源码 `7ca8be9`，基于实际07/11/08集成 `1309387`；最终源码 `86ee42a` 已合09/17及最新集成 `9ed7dae`，最终合并 `f2db9ae`。采用已授权FastAPI/真实SQLite/原件/公开SDK HTTP边界/实际Chrome/OS进程seam；方法案例的模型HTTP与数据HTTP均为固定loopback响应，无私有SDK替身，不表示实际外部取证通过。

## 条件与层级

| 层级 | 实际状态 |
|---|---|
| 当前凭据presence | 2026-10-07T20:10:41Z仅检查presence：DEEPSEEK_API_KEY=false，ROLL_DEEPSEEK_API_KEY_FILE=false；没有读取或打印任何秘密 |
| 实际发行物 | Python3.13.12、Agents SDK0.23.1、OpenAI客户端3.26.0、httpx2 2.13.1、jsonschema4.26.0；uv.lock固定，SDK方法实际执行 |
| SDK协议方法 | 真实SDK + loopback固定Responses服务器、合成认证、真实SQLite/归档/Job。通过不证明真实DeepSeek响应能力 |
| 浏览器 | 实际已安装Chrome，经独立FastAPI/SQLite；缺凭据与SDK方法分别运行，截图与原报告分列 |
| OS故障 | 实际API进程死亡与SDK子树，合成凭据/固定HTTP。不是实际DeepSeek模型请求崩溃 |
| 实际DeepSeek模型 | **未执行**：无明确可用API认证；订阅和Codex通过均不是证据 |

## 工程行为

固定 `deepseek-flash` + `https://api.deepseek.com/responses`，明确 `OpenAIResponsesModel` 实例使用DeepSeek客户端；无OpenAI模型或endpoint回退。独立空cwd/home、sanitize环境、私有pipe一次认证，认证不落文件，不进入prompt/tool/audit。全局和RunConfig tracing均关闭，无Agent技能、MCP服务器、插件发现、handoff、shell或开发指令。

只有 `roll_read_evidence`、`roll_read_source`。07原请求的SINA选择和必需字段继承给child；每个工具委托单计，实际网络读字节包括失败和丢弃，原件/规范化/子运行保留。正式账本/资金/资格/券商写能力不在工具面。恶意官网文字不能扩大权限。

候选通过宿主字面引用/所属原件/结构/对象/时间口径检查仍为未核实模型断言，事件时点未知、历史cutoff不合格。模型坏JSON保留脱敏provider原响应，不产生事实。超限provider响应保留允许64KiB脱敏前缀，实际接收计数包含最后4096字节越限块。

SDK公开HTTP transport只删除官方不支持而当前SDK实际发送的 `include=[]`；非空include及有状态字段拒绝，未加入假设兼容层。官方发布tag及源码位置、MIT许可、直接依赖与有限预算见 [接入合同](../../../../docs/deepseek-evidence-contract.md)。

## 用例与预期/实际

| 用例 | 预期与实际 | 证据层 |
|---|---|---|
| 缺凭据、额外model参数、关联retry、重启查询 | UNAVAILABLE明确原因；model覆盖422；新run引用原run；旧记录及账户不变 | 实际API/SQLite，无模型请求 |
| 三轮接续 | 第1轮取固定QUOTE，第二轮补固定官网正文，第三轮引用所属SHA；HTTP input包含0/1/2个function_call_output，json_schema，fixed model；返回PARTIAL，原件/Parquet可查 | 真实SDK方法 |
| 原请求语义 | SINA Referer/endpoint，QUOTE.volume_shares原样继承；未取得仍gap，不因模型完成覆盖必需字段 | 真实SDK方法+宿主 |
| 无账户写工具 | 模型试图account_confirm→HOST_TOOL_NOT_ALLOWED且DENIED审计，零host委托/账户变化 | 真实SDK方法 |
| 401/429 | 一次HTTP无重试，UNAVAILABLE细分权限与额度/限流；provider回显合成认证被实际key过滤 | 真实SDK方法 |
| 坏结构 | INVALID_OUTPUT；脱敏原模型响应可下载，零候选/父快照 | 真实SDK方法 |
| 任务中取消/并发 | 第二模型调用中cancel、同后端并发409；已归档补充原件保留，Job remaining_pids=[]，临时目录删除 | 真实SDK方法+OS |
| SDK并行8委托 | host peak=1；4次超限GET消耗累计字节，收到262144<bytes<=266240后后四次拒绝联网，归档0；没有用原件长度代替接收量 | 真实SDK方法 |
| 模型5轮/绝对时限/64KiB响应 | 轮数终结TOOL_LIMIT、不继续重试；1s宿主deadline终结TIMED_OUT；response越限有限FAILED，prefix归档65536字节/实际接收<=69632/截断标记 | 真实SDK方法+OS |
| 宿主硬崩、peer、marker/junction | 实际SDK任务等待HTTP时杀本票API；子树消失，重启INTERRUPTED；活跃peer409且不被误中断。异常marker或reparse清理明确拒绝，修复本测试自有标记后只清精确UUID目录 | 真实API/SDK OS故障，合成key |
| 页面 | 缺凭据、配置指纹与关联retry重载保留；方法三轮候选原件、工具及版本可见，随后cancel/newrun重载保留 | 实际Chrome，方法/缺凭据分列 |

红→绿发现：端点未实现404；未知写工具此前仅落INVALID_OUTPUT，补明确拒绝审计；stdin executor阻塞退出，改为daemon pipe读取/async queue有限关闭；SDKUsage嵌套对象不可JSON，改公开标量；超限响应此前只error code，补限量脱敏prefix和实际接收审计。浏览器定位修正保留真实child Run历史，不改变产品数据排序。所有修复经过受影响公开边界验收，不将首失败早停记录算成功。

## 真实条件及接续

需要用户/管理员提供明确的现有DeepSeek API凭据配置位置或运行环境变量，不需要新建key、修改个人config或OpenAI API认证。本机凭据配置后，同一固定版本/模型/endpoint实际完成多轮受控取证、结构化响应支持范围、实际错误/额度表现、模型任务中取消/进程树清理和页面回看；原失败保留，新retry关联，不换提供方绕过权限。

本票暂未验证DeepSeek实际模型strict/function能力、真实用量、实际401/429或额度，也未完成真实模型取消/宿主崩溃；这些不能用上表方法案例关闭。13后端切换与共同边界、23技术审阅仍独立承接。

## 最终集成与检查

工程阶段完成记录2026-10-08T04:33:51+08:00。初始源码7ca8be9合09后4ba51eb，完成一次完整后端 **225 passed / 835.03s**，见[原输出](raw/backend-full.txt)。此阶段包含10个12应用方法案例和3个实际OS故障参数案例，且保留原07/08/09/11等回归；不代表真实DeepSeek验收。

合17集成245b1d6后新增定向真实SDK方法，第二轮HTTP接收实际日线两行之前公开研究审计已经可查：`SEALED_MARKET_INPUT_EXPOSED`、route=`deepseek-tool-input`、`confirmatory_pass_look=false`。工具结果实际payload交付前调用observer；无封存材料登记时行为不变，不读标签、不算PASS查看。见[红](raw/sealed-input-red.txt)和[绿](raw/input-union-green.txt)：**6 passed / 15 deselected / 25.16s**，覆盖本票无凭据/三轮/封存输入及17现有实际工具/查询/下载边界。较早[合17前输出](raw/sealed-input-premerge.txt)仅缺模块前置条件，不算有效产品红灯。

最终[build](raw/build-final.txt)通过。合17后[Chrome SDK方法配置](raw/browser-method.txt) **1 passed / 1 skipped / 20.2s**；[缺凭据配置](raw/browser-no-auth.txt) **1 passed / 1 skipped / 12.0s**。skip是另一互斥服务配置，分开执行各实际目标；截图、JSON报告及方法run同目录保留。浏览器方法cancel证明UI可取消并重载保留，第二次模型HTTP调用中的真实SDK任务取消由应用方法案例单独证明，未据浏览器点击时点扩大覆盖。已安装Chrome版本只读核查为154.0.8037.95；Python3.13.12与发行包版本见方法run审计。

最终9ed7dae只追加早期证据原字节属性、去两处EOF空行，无产品行为变化，合并保留双方.gitattributes；不重复已通过整套或新增实际模型请求。账户/资格、原DIRECT_HTTP、SINA来源、必需字段覆盖及17输入审计保留。本阶段最终仅文档/证据整理，无源码变化。

## 原件保全与认证清理

[逐文件清单](runtime-preservation.json)实际创建于2026-10-07T20:29:04Z。自身三组最终固定basetemp方法（stateless/sealed/no-credential）及当次浏览器精确路径`C:/Users/72449/AppData/Local/Temp/roll-browser-wEQ7m8`，在服务结束后复制到本工作树忽略目录`backend/.roll-data/implementation-evidence/12`：**71文件，5,034,176bytes，源/目标SHA和长度不一致0，认证命名文件0，真实认证副本创建0**。清单记录每个绝对源→目标、SHA与长度；无前缀删除、无个人目录扫描，源未移动或删除。该清单全部是METHOD_CASE/缺凭据材料，不是真实模型档案。

完整225测试使用过的全局pytest临时路径`C:/Users/72449/AppData/Local/Temp/pytest-of-72449/pytest-282`在结束后被后续pytest保留规则移除，未逐份永久保全全部225夹具；完整stdout和公开复现测试源码保留，最终上述必要12夹具另以固定本树路径保全，不能声称全套临时数据库均保留。17组合方法创建的唯一合成认证文件`backend/.roll-data/12-final-input-method/test_codex_actual_tool_input_d0/method-chatgpt.json`已按公开测试字面值SHA核验，精确删除；不是实际ChatGPT认证。12运行不将key落文件，也未读取、复制或新建真实DeepSeek/OpenAI凭据。后续集成永久保全应按此清单复制并逐SHA核验，不能把这些运行材料stage进Git。
