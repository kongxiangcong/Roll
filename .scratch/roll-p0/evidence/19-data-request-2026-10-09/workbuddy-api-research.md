# WorkBuddy 官方 API 接入核查

核查日期：2026-10-09。只读公开文档；未授权、派发任务或查询万得。网页阅读器反复超时后，以 Python HTTPS 获取同一官方页面的公开 HTML，读取其正文；未使用登录态或私有接口。

## 推荐验证的接口：PC 本地助理

官方明确提供下面三个接口，主机均为 `https://www.workbuddy.cn`，请求使用 `Authorization: Bearer <access_token>`。[Open API：本地助理](https://open.workbuddy.cn/docs/openapi)

| 方法与路径 | Scope | 请求／返回要点 |
| --- | --- | --- |
| `GET /openapi/v2/localassistant` | `user.localassistant.readable` | `data.online` 是客户端在线状态 |
| `POST /openapi/v2/localassistant/message` | `user.localassistant.invokable` | JSON `content` 字符串、`msg_type: "text"`；返回 `data.message_id` |
| `GET /openapi/v2/localassistant/message?message_id=<ID>` | `user.localassistant.readable` | 增量返回该消息之后的消息 |

不用 `message_id` 时可用 `limit`（默认 20，上限 100）和 `offset` 分页。返回 `data.messages[]`，每项有 `message_id`、`role`、`content` **数组**、`msg_type`、`created_at`、`attachments` 数组、`metadata` 对象。发送成功只意味着消息已创建。[Open API](https://open.workbuddy.cn/docs/openapi)

**文档没有为本地接口定义独立 job ID、终态、reply-to 或每次调用的新会话。** `message_id` 是增量游标，不能据此断言所有后续消息都属于本次请求。建议桥接器串行发送，提示词带独立 `request_id`，结果必须回显该 ID，并以约定的 JSON 完成标记或文件 manifest 判断完成；这是桥接设计，不是平台保证。[接口字段依据](https://open.workbuddy.cn/docs/openapi)

## 授权与能力边界

开发者需要创建第三方应用、配置 scope 和回调、提交审核；启用后由用户完成 OAuth 授权。硬件应用可按业务申请全部权限，Buddy 应用是部分权限，须实际确认本地助理 scope 能否获批。不是拥有普通 WorkBuddy 账号便自动获得 Open API 凭据。[第三方应用](https://open.workbuddy.cn/docs/third-party-app)

官方公开的完整授权流程是 `GET /openapi/v2/authorize`（授权码、scope、state、已登记回调）→ `POST /openapi/v2/token`（authorization_code，client_id/client_secret，完全相同的 redirect_uri）。授权码一次性、10 分钟；刷新仍使用 token 端点。密钥与 refresh_token 应服务端保管。页面间 token 时长有差异，实际采用响应 `expires_in`，不硬编码。[Open API](https://open.workbuddy.cn/docs/openapi)、[第三方应用](https://open.workbuddy.cn/docs/third-party-app)

Open API 错误表虽提及 `device_auth`、`authorization_pending`、`slow_down`，但所读页面没有公开完整 device 授权端点与请求结构；不能据此补造流程。连接器的 `authDeviceFlow` 则明确用于第三方 **CLI 连接器的认证**，不能混同为调用 WorkBuddy Open API 的设备授权。[Open API](https://open.workbuddy.cn/docs/openapi)、[连接器](https://open.workbuddy.cn/docs/connector)

本地助理是本机 Agent 入口；官方企微文档进一步说明远程助理使用本机文件、Shell、凭据和插件，但它集中在一个助理会话、使用助理专属目录。因此本地路线最接近已有万得授权；仍需小测试证明万得连接器在该入口可用。[企微助理](https://www.codebuddy.cn/docs/workbuddy/Wecom-Guide)

## 云端与 Buddy 应用不能自动替代本地路线

云端接口为 `POST /openapi/v2/tasks`（`user.task.invokable`）、`GET /openapi/v2/tasks` 和 `GET /openapi/v2/tasks/{task_id}`（`user.task.readable`）。返回任务状态及 ACP link/token；列表不返回 token。ACP 用 GET SSE 接收、POST JSON-RPC 发送，经 `Acp-Connection-Id` 关联；依次 initialize、session/load、session/prompt，prompt response 的 stopReason 是本轮结束信号。[Open API：云端](https://open.workbuddy.cn/docs/openapi)

云产物通过 `_codebuddy.ai/artifact` 增量通知或 `{sandbox_url}/api/session/artifacts` 拉取；媒体可用返回 URL 下载。**这些不是本地助理回复／文件下载接口。** 文档的 ACP link 示例与 sandbox_url 推导示例有差异，实际集成需先核实返回地址。公开页面没有承诺云任务继承桌面万得连接器、授权或数据许可。[Open API](https://open.workbuddy.cn/docs/openapi)

Buddy 应用官方页面描述行业 Harness、模式、技能、连接器与 MCP Apps 配置；内置 OAuth 连接器仍需用户绑定。所查页面未给出可供任意外部程序免授权驱动桌面 WorkBuddy 的 Buddy App SDK。连接器文档的 MCP/CLI，是向 WorkBuddy **提供工具**；它不能单独证明 Codex 可调用 WorkBuddy 已绑定的万得。[Buddy 应用](https://open.workbuddy.cn/docs/buddy-app)、[连接器](https://open.workbuddy.cn/docs/connector)

## 最小验证方案

取得合法应用权限后：查 online → 串行发送既有 5 日 RAW 行情测试提示词（加入 request_id）→ 按 message_id 轮询 → 校验回显 ID、实际工具名称、单位、原始返回和文件哈希。只输出该测试范围；停在权限询问或不支持历史版本时记录实际缺口。当前结果是**官方接口闭环有文档支持，账户权限、万得可调用性和数据结果尚未实测**。
