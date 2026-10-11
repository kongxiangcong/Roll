# 2026-10-11 当前新任务仅 CODEX：13/23 最小范围跟进

依据用户明确的[当前后端范围](../../../provider-scope-2026-10-11.md)、ADR 0001/0003，以及仓库外 `roll-ticket31-delivery-preparation.md` 的范围差距。工作树 `codex-scope` / 分支 `codex/roll-p0-codex-scope`，实施前合入已验收 24 的 a350893，最终合入根证据 tip ee62732a6e39e3b7df35513bfe853560a90e92d8。最终行为源码未变后再写本回执。

新保存 DeepSeek 设置、新设置后端 DeepSeek 取证、显式 DeepSeek 取证，以及保存后端为 DeepSeek 时的技术审阅，统一返回 HTTP 403 `BACKEND_OUTSIDE_CURRENT_SCOPE`。入口在请求、重试或冻结材料查找之前拒绝；共同事务准入也拒绝非 CODEX 新运行。没有重新启用开关、未来 provider 框架或旧模块删除。直接来源取证保持原行为。

设置查询明确 `supported_backends=[CODEX]` 和 `resave_required`。原 DeepSeek 设置版本/时间仍原样保存于历史，不自动迁移；页面新选择仅 Codex，历史设置和旧归档仍显示 DeepSeek。旧设置下显式 Codex 可正常运行并保留当时的原设置快照；用户重新保存后生成新版本，后续设置后端运行绑定新版本。历史查询、取消入口、归档及历史 SDK/config 身份保留。

## 公开 API 红绿与最终行为证据

- `01-selection-red.txt`：1 failed/11.24s，旧保存 DeepSeek 返回 200，而当前范围须拒绝；没有启动 DeepSeek。
- `02-selection-green.txt`：1 passed/6.25s，仅最小保存设置范围检查。
- `03-admission-red.txt`：保留首次历史样本 schema 不完整的夹具失败，**不是行为红灯**。
- `04-admission-policy-red.txt`：1 failed/7.60s，有效旧配置打开后，旧显式 DeepSeek 对缺失请求返回 404；当前要求在该查找前返回 403。缺失请求使旧代码也不会读取凭据或启动运行。
- `05-admission-green.txt`：2 passed/11.38s，缺失请求/重试/材料都先范围拒绝，保存配置、账户及运行列表不变。
- `06-api-combined.txt`：6 passed/56.12s。
- `09-api-final.txt`：**7 passed/58.53s，exit 0**。四个当前范围 API tests；既有 Codex 固定 worker 的坏输出/越权工具两个案例；既有固定 worker 技术审阅、原材料重放/交付/重启案例。有效冻结 METHOD 材料的范围拒绝前后公开 review 列表均为空，材料不变；有效事实请求拒绝前后运行列表为空；显式 Codex、显式重新保存、版本冲突、关联重试及重启后的旧新运行均核实。

观察全部通过 FastAPI、真实 SQLite 和隔离归档。旧配置/旧归档夹具写入已经关闭的 METHOD 数据库，模拟历史持久化版本；初始化与业务请求使用公开 API，不查内部表证明行为、不 mock 内部服务。固定 worker 只返回已登记 METHOD 输出，不调用真实模型。此次 **DeepSeek 能力测试、DeepSeek provider/runtime、真实 Codex 模型调用均为 0**；DeepSeek 仅有范围拒绝和历史读取/取消检查。

## 页面与构建

- `07-build.txt`：TypeScript + Vite exit 0，60 modules。依赖从现有根 node_modules 复制到自有工作树；未安装包，构建及 Vite 缓存写入自有副本。
- `08-browser.txt`：保留历史 browser 样本缺少原事实请求导致的启动拒绝。用公开账户/请求创建补齐样本，无产品源码改动。
- `10-browser-final.txt`：保留 Playwright `toBeDisabled` 对原生 option 的 matcher 不适用失败；输出已经显示实际 `<option disabled>`。改为浏览器原生 disabled 属性和 DOM property 双重断言，没有弱化应禁选的要求。
- `11-browser-option-final.txt`：**Chrome 1 passed/11.3s，exit 0**。选择器只有 CODEX；AGENT 在旧设置下禁选，显式 CODEX 可选；旧 DS 时间/版本及归档模型配置保持显示；拒绝后历史不变；明确保存版本 2 后重载仍 CODEX；旧归档逐字段不变、只有原历史运行、历史 cancel 仍返回 200。四张截图保留初次状态与最终状态，已人工查看最终设置与旧归档截图。

## 保全与边界

`source-before.json`、`source-after.json`、`source-final.json`记录六份此次产品源码及 **12 份冻结模型依赖 + shadow/statistics/validation** 的原始字节长度/SHA。保护的 15 份在修复前后完全相同；六份更改是当前范围入口与 UI。旧 actual 审阅记录、材料、批准包、真实19输入均未读写或改造。源码指纹变更意味着旧依赖绑定仍应按既有校验拒绝；本票不更新旧 grant、不生成或发送新批准包，也不清除真实四项 BLOCKING/NOT_GRANTED。

全部隔离 METHOD profile 复制到 `D:/dsh-proj/Roll/.roll-data/implementation-evidence/codex-only-scope`：**1,097 files / 88,979,482 bytes / 0 mismatches**；逐文件长度及 SHA 见 `runtime-preservation.json`。`12-runtime-copy-initial-error.txt` 保留 Windows 长路径首次复制失败；helper 使用扩展绝对路径，只补 absent 文件并核对全部已存在字节，最终 `13-runtime-preservation.txt` exit 0。API/browser 结束后自有 python/node/chrome 进程查询为空。

本回执只完成已明确的当前 CODEX 范围差距，13 原双后端历史验收未改写；不把固定 worker 作为真实后端接入新证据，不宣称 25—34 完成，不改变真实研究支持、SEALED、门槛、资金授权或正式能力。
