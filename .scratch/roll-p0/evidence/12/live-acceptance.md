# 12 · 实际 DeepSeek 接入续验

2026-10-08，Asia/Shanghai。票12 **complete**：独立实际模型接入已经通过，资料结果仍 PARTIAL；不是模型资格、账户实盘或统计验证完成。此前缺认证/METHOD阶段的[原验收](acceptance.md)完整保留。

固定 Python3.13.12、Agents SDK0.23.1、OpenAI3.26.0、httpx2 2.13.1、`deepseek-flash`、`https://api.deepseek.com/responses`；锁文件未变化。现行[DeepSeek 官方 Responses 文档](https://api-docs.deepseek.com/zh-cn/guides/responses_api/)同日复核：无状态、多轮 function/tool output 与 text.format；真实支持以以下实际任务为准。

## 输入与边界

用户已明确提供 `D:/dsh-proj/Roll/.env` 的既有认证，并授权继续 implement-spec。生产工厂只读取仓库根 `.env` 或显式 `ROLL_ENV_FILE`；进程环境优先，字面值无插值或 shell，64KiB文件上限；显式测试数据目录不读文件，`ROLL_ENV=test` 不自动读根凭据。默认浏览器 runner 拒绝显式 env 文件及 live profile，移除 DeepSeek/Fuyao/OpenAI/Codex 凭据。

实际 Uvicorn/FastAPI、隔离真实 SQLite/归档，仅使用合成10000现金/600519持仓以打开页面；模型上下文没有账户、资金授权、私人文件或开发技能。发送字段只有公开证券、QUOTE用途/日期/截止/必需字段、静态问题及固定公开来源登记。实际取数为 SINA 报价和发行人 MOUTAI_OFFICIAL 网页。API key只用于宿主认证并经私有pipe传一次；没有复制 `.env`、账户数据源或个人认证。

首次公网尝试被自动审批拒绝：担忧外部披露 locally derived evidence。说明确切公共 payload/官网endpoint、用户现有认证与真实接入票据授权后，审批允许同一有限任务；没有绕过拒绝。默认目录内容保全的尝试也被拒绝为敏感内容转移，改为只读数量/布尔测试匹配/时间/SHA元数据，未复制内容。

## 实际结果

| 场景 | 预期与实际 | 原记录 |
|---|---|---|
| 三轮首次 | 三次真实HTTP200，依次取得SINA与官网；第三次2048输出token含960 reasoning，JSON截断。宿主INVALID_OUTPUT，零候选/父快照，原件和缺口保留；没有加预算 | [首次运行](live/multiround-run.json) |
| 关联retry | 同请求/模型/endpoint，另UUID引用首次；问题限定1条简短官网字面候选，三次真实HTTP200、两个顺序工具。PARTIAL，一条候选quote_verified=true/assertion_verified=false/cutoff_eligible=false；必需股数和事项时点未知保留，原价/实际取得时点不改 | [retry](live/retry-run.json)、[快照](live/retry-snapshot.json) |
| 任务中取消 | 第二次实际模型请求已发送，首工具原件已归档时取消。CANCELLED，两次模型请求/一次工具，已取得原件保留、子树remaining_pids=[]/临时目录删除 | [取消](live/cancel-run.json) |
| 实际401 | 用明确合成无效字符串覆盖进程认证，真实提供方401，UNAVAILABLE/DEEPSEEK_AUTH_REJECTED，仅一次请求/零工具/无重试/无账户变化。不是用户真实认证失效 | [401](live/auth-error-run.json) |
| 实际宿主硬崩 | 第二次真实模型调用期间，只杀本验收Uvicorn；重启同SQLite为INTERRUPTED，首工具/原件保留、exact任务目录清理。三个观察PID全部不存在 | [中断](live/crash-run.json)、[OS核对](live/crash-os-verification.json) |
| Chrome回看 | 成功候选、真实工具/指纹/原件，取消、401、中断逐次重载可查；归档回放网络调用0。1passed/22.0s，无新模型请求 | [浏览器报告](live/results.json)、[候选](live/deepseek-real-evidence.png)、[取消](live/deepseek-real-cancel.png)、[401](live/deepseek-real-auth-error.png)、[中断](live/deepseek-real-crash.png) |

所有实际流程前后合成账户完全相同、formal_judgment=DISABLED。成功任务真实usage为3 requests/input7588/output998/total8586；不把缓存、后台和已发送但未完成的取消请求计成实际完成token用量。

没有人为制造真实429、额度耗尽、越权模型输出或坏schema；429/未知写工具/坏结构仍以原固定响应方法证明宿主行为，不能称实际提供方返回过这些事件。实际不完整JSON已发生且留证。无新增模型权限回退、provider/model切换或SDK依赖；13负责实际后端切换，23负责技术审阅。

## TDD与回归

已确认的 FastAPI/真实SQLite/档案接口边界上：显式envfile认证配置首次红为DEEPSEEK_AUTH_NOT_CONFIGURED而非期望401；实现运行工厂加载后绿。进程认证覆盖、重启原记录、显式隔离目录不加载、test默认不加载均通过。

实际截断发现后增加固定HTTP重放：provider status=incomplete/max_output_tokens，即使文字是完整合法JSON也不得发布。首次红为DEEPSEEK_OUTPUT_SCHEMA_INVALID，新增明确DEEPSEEK_OUTPUT_TOKEN_LIMIT/INVALID_OUTPUT后绿。先归档脱敏响应，再拒绝发布；没有放宽2048/5轮/120秒预算。此前实际首次通用错误记录不回写。

相关完整测试：`pytest tests/application/test_runtime_environment.py tests/application/test_deepseek_evidence.py -q` **15 passed / 113.74s**。前一轮定向 **4 passed / 9 deselected / 36.37s**单列，不相加。前端TypeScript/Vite **53 modules**构建通过。默认CLI以显式 `ROLL_ENV_FILE=DO_NOT_READ_METHOD_ENV_FILE` 验证，在启动服务/创建数据库前拒绝profile，退出1为预期；没有读取该路径。完整旧343套由集成根单独记录，不代替本票实际结果。

初次env配置红灯未先钉住隔离数据目录，误在默认 LOCALAPPDATA/Roll 新建合成基线。已改测试首先固定临时 ROLL_DATA_DIR；只读确认默认目录15初始文件创建于本红灯03:30:21—26Z，随后本次只读SQLite探针创建空WAL/SHM，账户3事件/1基线/1缺凭据请求与公开测试字面输入布尔匹配、其他研究/来源数据全空，17文件完整SHA/长度复核后精确清理自有目录；没有重置原有用户目录。仅[元数据](default-provenance.json)和[清理回执](default-cleanup.json)保留，内容复制0。

## 原件保全

[实际运行清单](live/runtime-inventory.json)：自身隔离data目录146文件/6,011,362bytes；逐文件SHA256/长度，实际两key字节扫描匹配0。真实 `.env` 副本0、认证命名文件0。含真实提供方/公开来源原件、Parquet、SQLite及合成账户恢复档案，留在ignored runtime；永久根保全须按精确清单复制并核SHA，再清理工作树。Git只保存脱敏运行JSON、结果、截图、元数据与验收源码。
