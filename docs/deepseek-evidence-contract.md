# DeepSeek 受控取证接入

2026-10-08。票12工程接入，真实 DeepSeek API 验收待凭据；固定响应通过不能代表服务实际权限或模型支持。

沿用 [DataRequest/RetrievalRun](data-evidence-contract.md)。`POST /api/data/requests/{request_id}/deepseek` 仅接受问题和可选 `retry_of`；重试必须引用同一请求的已终结 DeepSeek 运行，保存新 UUID，旧运行与原件不覆盖。`GET /api/data/runs/{run_id}` 查询，`POST /api/data/runs/{run_id}/cancel` 有限取消，原件及快照使用07既有接口。生产固定 `deepseek-flash`、`https://api.deepseek.com/responses`，没有 OpenAI endpoint 或模型回退；页面只选后端，不让普通用户选择模型或放宽预算。

## 实际版本与协议

Python3.13.12、`openai-agents==0.23.1`、`openai==3.26.0`、`httpx2==2.13.1`、`jsonschema==4.26.0` 均在 uv.lock 固定。Agents SDK 官方 tag [c4a1d047b22488234b2ba81056e1b9b8db2127a5](https://github.com/openai/openai-agents-python/tree/c4a1d047b22488234b2ba81056e1b9b8db2127a5)，MIT发行包；OpenAI客户端 [4e152cdefe1844c2d5d78653310e9b9c0195c44e](https://github.com/openai/openai-python/tree/4e152cdefe1844c2d5d78653310e9b9c0195c44e)。没有源码复制或私有SDK猴补，没有SDK extras、handoff、SandboxAgent、插件发现或MCP服务器；MCP包是官方SDK基础传递依赖，未装载服务器或授权其工具。

实际使用公开 `Agent`、`Runner.run`、`FunctionTool`、`OpenAIResponsesModel`、`AgentOutputSchemaBase` 和 `httpx2.AsyncBaseTransport`。官方 [DeepSeek Responses协议](https://api-docs.deepseek.com/zh-cn/guides/responses_api/) 声明无状态、不支持 `previous_response_id/conversation/store/background/include`，支持 function 工具及 `text.format`，忽略 `parallel_tool_calls/max_tool_calls`。SDK固定源码 [openai_responses.py](https://github.com/openai/openai-agents-python/blob/c4a1d047b22488234b2ba81056e1b9b8db2127a5/src/agents/models/openai_responses.py) 会发送 `include=[]`；本票仅通过公开HTTP transport删除这个已发现的空字段，非空值和不支持的有状态参数拒绝，不猜测其他兼容问题。

显式具体Model/AsyncOpenAI客户端固定提供方，`auto_previous_response_id=False`。每轮完整 input 带此前 `function_call` 与 `function_call_output`。SDK独立轮数限制与HTTP实际请求限制共同计数；固定方法服务器已看到三轮0/1/2个工具结果接续及 `text.format.json_schema`。该证据不证明真实 DeepSeek strict/schema 或模型权限，真实条件待验。

## 宿主边界

两个工具 `roll_read_evidence`、`roll_read_source` 使用11已有的具体有限读取/宿主校验；无 shell、文件读取、任意URL、写HTTP、账本、资金、资格、券商、开发技能或子任务工具。原请求的 `quote_source` 与必需字段继承给子DataRequest；原件先归档，候选只核对所属原件、字面引用、结构、对象、时间口径。模型断言仍 `assertion_verified=false`、事项时点未知、`cutoff_eligible=false`，不晋升事实或消除必需字段门禁。页面事实和候选分列。

宿主上限120秒、8次工具委托、6次取数HTTP、单响应64KiB、取数累计256KiB、并发1、子任务0、自动重试0。工具并行回应经SDK worker锁与宿主单循环串行处理，每次委托单计，失败/丢弃接收字节也计累计；允许最后4096字节读取块边界越限，越限后停止联网。模型另限5次实际请求、每次输出2048 token、input 128KiB、response 64KiB、累计response 256KiB。取消/总deadline由宿主Windows Job终止整个worker树，HTTP15秒是更小单请求超时。金额上限依用户Q7已撤回，不要求填写费用统计参数。

任务在仓库外独立空cwd/home运行，继承环境仅必要Windows系统、TLS及网络环境变量，API密钥不作为环境变量传给worker。私有stdin pipe传一次认证，既非模型上下文也非工具输出；认证不落任务目录。Agents全局及RunConfig均禁用tracing，禁用日志，无OpenAI云trace调用。实际发出的必要请求摘要、模型响应和SDK版本只保留本地；响应/错误出口按实际key脱敏，错误只记录稳定code/type/HTTP status，不记录异常请求对象或头。

认证仅明确 `DEEPSEEK_API_KEY` 或管理员指定纯文本 `ROLL_DEEPSEEK_API_KEY_FILE`（最大4KiB），不扫描个人配置、不新建key、不利用网页订阅推断API权限。缺失为 `UNAVAILABLE / DEEPSEEK_AUTH_NOT_CONFIGURED`；401/403、429及404分别明确权限、额度/限流、模型不可用。测试endpoint只允许 `ROLL_ENV=test` 的127.0.0.1 HTTP并要求合成哨兵key，真实key拒绝发给固定服务器。

失败、取消、超时和中断保留已取得原件、子运行与缺口；结构错误保留脱敏provider响应，不发布未经检查的事实。超限模型响应保存有限脱敏前缀与独立实际接收计数。API硬崩由Job关闭子树；启动只中断已死亡PID/creation组合拥有的运行，不中断活跃peer。精确UUID目录/nonce marker及非reparse检查不满足时记录清理拒绝，拒绝前缀扫描或历史PID杀进程。DeepSeek未写认证文件，清理同一已登记目录。

## 当前验收条件

全部工程证据见 [票12验收](../.scratch/roll-p0/evidence/12/acceptance.md)。缺真实凭据时本票 `needs-info / partial`，不解锁13。取得明确DeepSeek API凭据后，需在上述同版本/endpoint/model冻结组合实际完成多轮取数/网页补查、结构化候选、错误/额度表现、任务中取消、页面重载及进程树清理；若提供方不支持，保持真实失败证据并仅适配已发现差异。23仍负责技术审阅专用材料和输出契约。

17实际接口已接入：在 `roll_read_evidence` 返回实际 `facts[:20]` 载荷给SDK worker前调用 `research.market_input_exposed(result,'deepseek-tool-input')`，与11共用同一具体交付点。固定SDK日线任务已证明第二模型HTTP调用收到两行事实前，SEALED_MARKET_INPUT_EXPOSED持久记录已可经API查询且confirmatory_pass_look=false；不包所有HTTP、不读取封存标签，不将输入暴露算PASS查看，无材料登记时保持07既有行为。
