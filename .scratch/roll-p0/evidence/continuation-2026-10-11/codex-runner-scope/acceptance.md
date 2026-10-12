# 2026-10-11 当前 CODEX 默认验收 runner 范围切片

确认依据是仓库外 `roll-p0-delivery-runner-scope-audit.md`（只读快照 097ef72，正文保存在 `audit-report.md`）及[当前用户范围](../../../provider-scope-2026-10-11.md)。新工作树 `codex-runner-scope` / 分支 `codex/roll-p0-codex-runner-scope` 基于已验收 30 source 的 c3fe7d8。交付前合入最新已验收 25 integration 371dd9c7c75d1fb5df9827a81dc580ddd5a62c63，没有复制或暂存 root 无关工作。

## 当前默认集合及保留契约

pytest `tests/conftest.py` ignore 原 `test_backend_switch.py`、`test_deepseek_evidence.py`、`recovery/test_deepseek_process.py`；原跨后端两个 tuple 与纯 DS 技术审阅 case 明确 deselect，包括直接指定它们时也不作为当前能力运行。历史文件/原件/收据保留，排除不记 PASS。资格中拒绝 DEEPSEEK review 的负向用例仍收集。

CODEX 来源继承只保留当前 CODEX 参数，fixture 的该分支不启动 DS model_server 或配置 DS synthetic key。旧 cross-provider tuple 保留原身份，另新增明确 **CODEX→CODEX** 的修订归档拒绝/重新取得/旧时间与原记录不变/无 HTTP 归档重放测试，没有机械替换 tuple 或声称跨后端验收。source HTTP 仅 `httpx.MockTransport` 固定字节，无来源网络请求。

混合技术审阅 case 保留 CODEX 同材料 retry、共享槽、取消、进程清理与冻结 timeout；DS 设置/显式请求返回 403，不增加运行、review attempt 或占槽。同材料有三个实际 CODEX METHOD 运行（取消、retry取消、有限超时），不再切新 DS 后期待其 UNAVAILABLE。公开旧配置/GET/重存版本及材料零 attempt 反向 case 保留。

两个前端默认消费者共用 `scripts/default-files.mjs` 的 11 文件集合：baseline、cash-equity、codex-evidence、codex-only-scope、csv、fills、funding、market、market-overflow、reconcile、valuation。旧 backend-switch/deepseek-evidence 文件保留历史。`--list` 是无运行的公开核对；`--file=` 只能选择当前文件，在新建 profile 前拒绝旧 DS 文件。无参数仍逐文件隔离、清除凭据。有限子集报告标明 `DEFAULT_OFFLINE_SUBSET`。

新 `codex_scope_method_app` 只在 test/全新数据库下通过公开 API 建立合成账户与原事实请求，关闭 writer 后写入旧设置/取消记录的 METHOD 字节，然后用当前 writer 打开。没有生产 reset、旧 actual profile 连接或新 DS runtime。每次新 UUID profile；截图在自己的当次报告目录，未读取/覆盖旧固定 profile 或截图。Playwright 显式绑定当前工作树 src，METHOD 时同时包含 support，继承 Python 禁写 bytecode。

## 红绿与实际命令结果

- `01-collection-red.txt`：默认 collection 首先暴露 24 helper 的 import 路径缺口，556 collected/1 error，外层 tracer 1 failed/7.77s。**这是默认 import 错误，不是 DS 范围红灯**；最小 pytest pythonpath 增加已有 `tests/support`，未改生产运行时。
- `02-collection-policy-red.txt`：路径修复后实际 collect-only 592 collected，tracer 明确因选中 DS-positive 节点失败，1 failed/6.04s。没有执行历史节点。
- `03-mixed-red.txt`：旧 mixed 场景在新 DS 保存设置时收到 403，1 failed/11.01s；在此以前只有 CODEX 固定 worker，未派发 DS。
- `04-collection-green.txt`：tracer 1 passed/5.41s。`05-mixed-source-green.txt`：CODEX slot/source 两个公开 API case 2 passed/14.22s。
- `06-browser-collection-red.txt`：Playwright **--list only** 显示旧 19 tests/12 files 仍包含两份 DS-positive、没有 current scope，node tracer 失败；没有 browser/server/provider 执行。`07-browser-collection-green.txt`：1 node tracer PASS。
- `08-default-collection-final.txt` 是新增同 CODEX 修订回归前的中间集合：567/570 selected、3 deselected；最终以 14 为准。
- `10-api-final.txt`：**9 passed / 2 historical deselected / 50.76s / exit 0**。限定当前 collection/scope、两项 CODEX 来源契约、共享 slot/cancel/retry/timeout 与原真实 OS 子进程取消；没有广域 suite。
- `11-runner-final.txt`：两个公开 CLI/list 一致性与 DS 文件拒绝 tracer **2 passed / 4.095s / exit 0**。
- `09-current-browser.txt`：canonical `--file=codex-only-scope`，**Chrome 1 passed / 20.8s / exit 0**，新选项仅 Codex、DS 403、历史设置/归档 GET 与 cancel、显式 resave/version2、旧身份不变。`browser-manifest.json` / `browser-report/` 保留实际新 UUID profile、分层状态与三个截图；已查看历史归档截图。
- `12-build.txt`：单次 TypeScript/Vite **exit 0 / 60 modules**。使用自有 frontend 依赖副本，无安装、无 root 前端缓存写入。

上述行为组合/Chrome/build 对应 c3fe7d8 产品源码。随后合入 accepted 25：`source-tested-before-25.json`证明此前 99 份产品源码未因本任务变化；`source-integrated.json`/`accepted-25-source-delta.json`记录此后 101 份源码，六条变化路径完全来自已接受 25（app/actions/reviews、action-panel/market/today），**不能称整套产品字节仍99份一致**。本任务没有产品源码修改。

`13-post25-composition.txt` 在该最新 source 上只补跑范围/技术审阅共享槽两项 **2 passed / 13.42s / exit 0**。`14-default-collection-post25.txt`实际 **591 selected / 594 collected / 3 deselected / 3.72s / exit 0**；ignore 文件未作为 selected 收集，正向 DS 不计 PASS。此次没有重复 Chrome/build；新 accepted 25 的独立 UI/build/行为收据由其责任票提供，当前 selector 两文件未因25改变。

## 运行保全与资格边界

15 份保护指纹（12模型依赖 + shadow/statistics/validation）从基线至集成后全部原始字节一致。本票不改 qualification、算法、旧材料/批准包/records，不读 auth 内容、原19数据库或 SEALED，不拟合、不造预测、不授能力；**真实 Codex、DeepSeek SDK/provider、公网来源调用均0**。CODEX METHOD 是进程/API 工程验收，不是实际后端能力证明。

所有本次新 METHOD runtime 在测试结束后复制到 root `.roll-data/implementation-evidence/codex-runner-scope/runner-2026-10-11`，**540 files / 44,276,137 bytes / 0 mismatches**，每文件 SHA+length 见 `runtime-preservation.json`。root `manifest.jsonl`只追加该新 capture 摘要，前后 SHA/长度见 `root-manifest-append.json`；旧 profiles 未 SQLite-open。`stopped-processes.json`为 `[]`。

13/31仅追加本范围说明；原历史验收和31 partial/未完成框保持。此有限结果不是当前全默认suite通过，不关闭31五入口、P95/容量、通知或其他责任票。Root README/status/trace由集成维护者更新；不 push，不清理工作树。
