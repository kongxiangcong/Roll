# 01 · 受限 Codex 研究尝试

Status: ready-for-agent

Blocked by: 无，可直接开始

## What to build

在现有研究任务 CLI 显式选用 Codex，以冻结公开文本取得单次结构化响应，通过任务、尝试和版本重读。

## Acceptance criteria

- [x] 原离线入口及历史回执兼容；真实尝试记录实际平台、CLI 版本、权限摘要、退出诊断及按尝试隔离的日志。
- [x] 目标机用公开输入、假私有文件及回环服务核验生效权限；配置不足时拒绝执行，记录配置错误。
- [x] 通过正式 CLI 区分阻塞缺口、合规草稿、配置错误、非零退出与不合约回包；检查证据来自本清单，草稿只随成功回执提交。

## Comments

2026-11-26 在 Ubuntu 24.04.5 LTS x86_64、Linux 6.8.0-138-generic 验证。目标二进制为 `codex-cli 0.172.0`，SHA-256 为 `ad83b94c093f0cdd8176a6bc8005a461bdf23a759863e157d40f562b8a9d664d`。从仓库根目录运行 `python -m pytest -q backend/tests/test_v3_codex_permissions.py backend/tests/test_v3_codex_research.py backend/tests/test_v3_research_tasks.py` 可复验，权限探针需要本机回环接口。

- 通过正式 CLI 入口给目标 Codex 传入冻结公告，推理端在本机模拟。分别使用合成 API key 和合成 ChatGPT 登录，真实 CLI 发出的 Responses 请求都未声明工具，输入也没有附加工具目录。宿主对照成功读取假私有文件并访问工作台。模拟服务要求执行文件读取和回环请求，两条调用都收到 CLI 的 `unsupported call: exec_command`，工作台只记录宿主对照。研究数据目录上层及宿主 Codex 配置中的私有标记均未进入请求或产物。
- 公开请求按尝试保存为 `public-input.json`，回执包含文件引用和指纹。公告问题保留公告文本、定位和行情清单引用，行情问题另附实际使用的观测行。已验证缺少必要可读摘录、模型报告阻塞缺口、缺少可执行文件、服务非零退出、缺失或错误回包、越界引用和合规草稿的版本归属。
- 文件登录由原生 CLI 管理。隔离目录中只链接登录文件与配套锁文件，目标版本通过这些链接更新合成凭据，底层原缓存同步更新。关闭用户配置、技能、扩展、子代理、shell 和网页等能力的参数记录在每次 Codex 回执中。
- 真实模型服务的个股研究与发布验收由工单 03 记录。
