# 11 Codex 真实受控取证验收

开始：2026-10-08T01:34:00+08:00；验收日期：2026-10-08，实际运行UTC时间分别保存在原记录。初始集成 `1159dc71b610d15c17fd7d889f08c98978f0bc40`，最终代码 `653c300a3de7540ddc3d7e25985cc1ecb8f6e571` 已合最新集成 `12c95639755ce42d711a7c415eeed98a47d981dc`（01—08/10与07/08档案保全）。证据提交仅追加文档；父管理 execution-status。

结果：本票完整 Codex Runtime 接入通过；实际资料结果仍为 **PARTIAL**，不把候选、模型完成或已有订阅标为事实完整/历史可得/正式资格。未调用 API-key 计费通路，没有推出 DeepSeek、运行中切换或技术审阅通过。

## 验证分层

| 层 | 实际结果与证据 |
|---|---|
| TDD公共API、真实SQLite/隔离归档 | 必需字段 RED 子请求为空；修复后逐组/公共字段继承。失败/丢弃流 RED 六次请求，GREEN 四次耗尽256KiB，后续拒绝。坏JSON/缺工具/禁API key/无认证/有限deadline/取消/实际子进程/活跃宿主保护分别验证。发行人HTTP固定流另验。 |
| 全部后端兼容 | [173 passed，591.15s](backend-tests.txt)，08合并前 `ee422df`；最后issuer增量后 [14 passed，51.34s](backend-codex-final.txt)。之后08加入的共享取证与新Sina组合 [44 passed，106.73s](backend-08-11-union.txt)，涵盖本票15例、07事实、08用途/修订，不声称一次最终全套173+新增均运行。仅一项既有Starlette/httpx弃用警告。 |
| 合成worker、真实OS崩溃 | 实际uvicorn宿主死亡使Job子树归零；重启INTERRUPTED并精确清理。marker不符与实际junction均拒绝清理、哨兵保留；修复精确自有夹具后重启收尾。仅METHOD_CASE token，和真实SDK硬崩下列证据分开。 |
| TypeScript/生产构建 | [合并后45模块构建通过](frontend-build-union.txt)；此前43模块输出另留。 |
| 实际Chrome、ChatGPT完整任务 | [首次Tencent浏览器完整任务通过](browser-live.txt)，55.5s；[08合并后显式Sina完整任务通过](browser-live-union.txt)，47.6s，均原件SHA/Parquet验证、页面候选/缺口、只读回放网络0次、账户不变、实际SDK turn后点击取消。 |
| 实际Chrome、无认证/兼容 | [缺认证状态/刷新历史通过](browser-compatibility.txt)；[名单/日历页面通过](browser-direct-http.txt)；[原07 DIRECT_HTTP真实公开源页面/归档/回放通过](browser-direct-http-live.txt)，14.9s。08固定修订工厂按独立空账户复验，输出见 [方法页面](browser-08-method-isolated.txt)。 |

一次共用空基线假设不兼容的双方法文件调用发生确认冲突，保留 [原失败](browser-08-11-shared-baseline-red.txt)。另一次工厂误写为导入的 `create_app`，得到 REAL_ACQUISITION 而非METHOD_CASE，保留 [原失败](browser-08-wrong-factory-red.txt)，改为仓库明确规定的 `resolution_method_app:factory` 单独复验。没有修改产品版本/确认校验来通过夹具；不声称默认全部浏览器suite全绿。

## 版本、权限与桥接

[环境](environment.json)登记 Python3.13.12、SDK/runtime各0.161.0、模型gpt-6.1-sol/openai、EXE SHA、bundled bridge SHA、工具/schema/宿主源码及有效配置指纹。`uv.lock`锁实际发行物。官方 [固定源码9790114](https://github.com/openai/codex/tree/979011409de0a60b52f179721948e65531d26144)、[SDK](https://learn.chatgpt.com/docs/codex-sdk)、[app-server](https://learn.chatgpt.com/docs/app-server)与公开同步approval handler用于接入，未猴补私有SDK，未增加Node或闲置Agents SDK依赖。

先检查实际目录，再独立ChatGPT认证完整任务验证；不由model catalog推全部模型权限。真实模型不存在路径返回MODEL_UNAVAILABLE。必要认证字段只复制到已登记的独立home；个人config/skills/state不复制或修改，SDK env继承已由宿主过滤，API key拒绝。有效配置禁止云trace导出、shell、任意file环境、插件/MCP/联网写/递归。

Windows实际发现38个技能元数据，HOME覆写不足以关闭：只向独立CODEX_HOME写disabled，再forceReload；实际enabled=0，thread `instructionSources=[]`。残留disabled路径元数据不作为有效开发指令或可调用能力。

最初关闭bridge的真实任务 `444d3d0f-4ffe-494a-a176-5249092dc6f0`，模型完成但3次工具均Runtime内部“code-mode host disabled”，宿主0次，不算多轮通过。最小启用固定Rust/V8 `code_mode_host=true` 后实际通过；read-only配置不单独宣称完整OS隔离。

## 实际完整任务与状态

| 实际运行 | 观察 |
|---|---|
| `711b6142-ac50-4fbf-946a-c7dee43e56dc` | 首完整成功链：2026-10-07T17:55:36.706487Z—17:56:40.832565Z，3host工具，腾讯报价→官方网页→公告接口，2原文候选，PARTIAL；真实数据与副作用控制，旧版本指纹保留。 |
| `f192ee43-2211-4fbb-afea-10354ec5f900` | 首最终Chrome链：18:48:59Z—18:49:42Z，3工具/HTTP、实际接收67362字节，报价/事项缺口、官方主营连续短引；[旧版本结果](runtime-codex-browser-before08.json)，不覆盖它声称新版本。 |
| `3be88ed0-76ce-4f16-8f9d-b18e1e8c0067` | 合08真实Chrome：19:06:28.694957Z—19:07:06.963162Z，显式SINA，3工具/HTTP、实际接收67104字节、1候选、PARTIAL；[run/snapshot](runtime-codex-browser.json)、[页面](live-union-ui.png)。 |
| `92d91913-ed91-4cc1-944a-56010bfc15b3` | 最新Chrome实际turn后取消，约5.366秒（含SDK启动），CANCELLED，剩余PID0、目录已删除；[记录](runtime-browser-cancelled.json)、[页面](cancel-union-ui.png)。另有实际API取消 `b55e86ba-2d4a-4259-901d-48ed802a029c`，约9.394秒。 |
| `76061352-cd4c-4912-951a-69f1ca0828b2` | 真实SDK turn已开始，精确终止该worker→FAILED/WORKER_EXIT，所属Runtime余下子树归零、认证副本删除；[记录](runtime-real-crash.json)。 |
| `fe63e00d-b656-4bdf-bcb3-a2fec8febbfd` | 真实SDK启动使用管理员2秒期限→TIMED_OUT，约2.35秒收尾；不是模型turn超时证明；[记录](runtime-real-timeout.json)。 |
| `2397172c-5ac6-4350-b4a5-0c739be5e84b` | 真实独立认证与catalog中无冻结模型→UNAVAILABLE/MODEL_UNAVAILABLE，不发该模型请求；[记录](runtime-real-missing-model.json)。 |
| `30c70eb2-8ce6-415b-9eb8-38d5b848048b` | **真实ChatGPT SDK API宿主硬崩**，实际turn已开始、有真实必要认证副本；宿主死后4所属子进程归零，重启INTERRUPTED、marker核验后REMOVED/credential_removed=true、账户不变；[原运行与恢复](runtime-real-host-crash.json)。不是METHOD_CASE或仅杀worker。 |

首任务 `13ce4ae0-e672-4750-a4d7-a37dddd4464b` 提前停止并出现Runtime日志库清理锁定，真实FAILED记录保留，[原记录](runtime-failed-start-task-1-live-task-1.json)。曾有中文原文校验拒绝 `9c4e3e0b-a2af-4f49-bc73-a070212bc7ac`，真实INVALID_OUTPUT保留，后补GBK兼容；合08后Sina组合再次以公共API复现对应漏项并修复。所有失败运行不改写成成功。

## 实际敏感能力对抗

最终生产API `64b13072-bc50-41ea-aa25-db6ae02a6c83`：实际先取得报价，并运行纯V8探针；`fetch/process/require`均undefined，ALL_TOOLS仅 `clock__curr_time/roll_read_evidence/roll_read_source`，`import("node:fs")`实际返回unsupported import。私文件哨兵不披露、写哨兵不存在、本地接收器GET/POST均0、账户投影不变，Job剩余PID0。[实际结果](runtime-real-adversarial-final.json)。对于不存在的能力，只记录未授权且未调用，不虚称已执行敏感操作后遭OS拒绝。

独立 [同版本SDK/V8组件探针](runtime-v8-component-probe.json)实际执行clock取得18:31:23UTC，另证同样的无Node模块能力；它与生产API对抗分列。固定 [V8 globals](https://github.com/openai/codex/blob/979011409de0a60b52f179721948e65531d26144/codex-rs/code-mode-runtime/src/globals.rs) 与 [模块拒绝](https://github.com/openai/codex/blob/979011409de0a60b52f179721948e65531d26144/codex-rs/code-mode-runtime/src/module_loader.rs)核对。内置clock无逐次SDK回调；显式允许并由外层exec/wait操作次数与120秒deadline/Job约束，不宣称每次clock单独计数。每宿主数据委托仍单计8次、HTTP6次、接收256KiB。

## 原件、时点、预算与保全

最后候选短引为“主营茅台酒及茅台系列酒的生产与销售”，来自登记的茅台官方主页原文；其实际收到时间只证明获取，event_time=null/assertion_verified=false/cutoff_eligible=false。报价仍是供应商旧日期，不当作10/08当前盘中现价；公告页未给日期窗内原文，保留NO_ORIGINAL_IN_BOUNDED_METADATA_PAGE/NO_HOST_VALIDATED_FACT。候选没有升级truth、账户到账、交易资格或PIT模型输入。

固定源GET无任意URL/POST/redirect，DNS公开地址检查，单响应64KiB/累计解码接收256KiB，最多一个4096字节块边界超限仍记账。已失败或丢弃正文不漏计；给模型的结果字节与原件字节分别记录。07默认DIRECT_HTTP仍原预算，Codex子请求以显式keyword传缩小限制、剩余deadline及取消事件。08 Sina Referer/解析/原请求quote_source保留；本组/公共required_fields通过父子请求实际API验证，缺DAILY.adjustment_factor保持缺口和model_daily_input_allowed=false。

[运行与安全原件清单](runtime-preservation.json)列明确own目录、runID、SHA及无剩余认证副本；Git仅保存公共原件/Parquet/脱敏审计，未复制auth、个人config/skills、SDK日志/状态库或方法token。浏览器SQLite以唯一runUUID只读确认精确目录 `C:/Users/72449/AppData/Local/Temp/roll-browser-S3JgZq` 后保全；服务已结束。

[根永久保全清单](root-runtime-preservation.json)：146文件、12840005字节、SHA不匹配0、认证文件复制0，精确source→destination登记，根保留于 `backend/.roll-data/implementation-evidence/11/`，原源目录仍保留。该目录已忽略，不纳入Git。旧自有probe-q6lrynkv认证副本已精确删除，旧首次task-7cj4wpea已无auth；两个旧SDK元数据目录保留，不从前缀扫描删除。自动审批曾拒绝宽泛前缀清理，已改为精确归属路径核验/清除，没有待批准动作。

## 后续边界

详见 [Codex契约](../../../../docs/codex-evidence-contract.md)。当前仅一个明确登记的官方补充网页，其他对象或资料会如实返回来源未登记；PDF超64KiB是局部缺口，不伪装已有大预算。SDK/runtime真实可用只覆盖本机此次认证与冻结模型，不推订阅全部能力。12独立DeepSeek、13切换/共同权限、23技术审阅及19/25真实模型消费/动作仍有独立联验。本票未实施这些后续任务，也无外部登录/额度阻塞。
