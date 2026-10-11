# 当前默认验收 runner 范围核对

只读源码快照：root `097ef72f7b16f74a113485e96badcdb38ed35885`，2026-10-11。未运行 pytest/Playwright/模型/DeepSeek，以下是可静态确认的 runner 契约冲突，不是实际观察到的当前套件失败，也不是 DeepSeek 能力缺口。

## 当前入口及明确冲突

- `frontend/package.json`：`test:e2e` → `node scripts/test-e2e.mjs`。
- `frontend/scripts/test-e2e.mjs:5` 与 `frontend/playwright.default.config.ts:6`：默认文件仍包含 `backend-switch`、`deepseek-evidence`。脚本逐文件新 SQLite、清除模型凭据，能防共享账户污染，但不会将正向DS测试变成CODEX-only场景。固定文件名单也未包含新的 `codex-only-scope.spec.ts`。
- `frontend/tests/e2e/backend-switch.spec.ts:8`：明确选择新DEEPSEEK设置，期待“已保存DeepSeek v1”、随后新的DS取证与跨后端retry。当前界面只提供CODEX且host拒绝新DS，故此默认场景与当前契约不相容；其历史实际成功不能当当前默认通过。
- `frontend/tests/e2e/deepseek-evidence.spec.ts:4`：默认首例期待新DS无凭据运行、reload/retry；METHOD另例由flag开启并实际调用固定SDK路径。当前不应调用或验收这些正向DS能力，移出当前默认；历史原件保留。`deepseek-live.spec.ts`需显式旧归档flag，不在固定默认名单，不能作为当前缺口或新默认PASS。
- `backend/pyproject.toml`：pytest `testpaths=["tests"]`、`pythonpath=["src"]`，未配置DS-positive排除。`backend/tests/application/conftest.py`只有 METHOD 时钟fixture，没有collection ignore/skip。直接默认pytest会收集下列历史正向入口。
- `backend/tests/application/test_backend_switch.py`：`test_backend_settings_are_versioned_persistent_and_do_not_change_authority`、`test_running_task_keeps_its_selection_and_all_routes_share_concurrency`、`test_cross_backend_retry_reuses_verified_source_bytes_and_original_times`、`test_other_live_host_cannot_bypass_shared_concurrency_after_switch`、`test_deepseek_running_selection_survives_reverse_switch_and_cancel`、`test_corrupt_retry_archive_is_a_gap_and_is_never_researched_again`都存在新DS正向设置/派发。保持其旧版receipt，但当前默认应只核CODEX通用版本、并发、取消和归档retry契约。
- `backend/tests/application/test_deepseek_evidence.py`：无凭据新DS运行、实际SDK固定提供方多轮/写工具/错误/取消/预算/timeout/SEALED工具案例均是历史正向DS-specific；不得继续作当前默认能力验收。此处“actual SDK”主要是固定METHOD HTTP provider，不应误称当前实际DS外发，也不必执行来证实排除范围。
- `backend/tests/application/test_agent_source_contract.py:41`：`test_agent_child_preserves_explicit_fuyao_adjustment_source` 参数 `['CODEX','DEEPSEEK']`。最小当前改为仅CODEX分支；保留source inheritance断言及原历史双参数收据，不用删除该通用来源契约。
- 同文件`:73`：`test_cross_backend_retry_rejects_revised_archive_and_preserves_original` 两组合 `CODEX→DEEPSEEK`、`DEEPSEEK→CODEX`均要求新DS。两组应归历史排除；如需当前CODEX同后端retry，则另保留已有同后端归档/修订守卫场景，或最小重写具体CODEX case。不能只把两个tuple机械改成CODEX→CODEX并仍称“跨后端”通过。
- `backend/tests/application/test_technical_review.py:167`：`test_deepseek_sdk_review_uses_the_same_material_contract_and_freezes_runtime_versions`纯正向DS技术审阅，当前排除。
- 同文件`:226`：`test_cancel_timeout_retry_and_acquisition_share_the_same_frozen_execution_slot`是混合通用契约：先CODEX worker、然后切新DS、期待DS UNAVAILABLE retry，再切回CODEX测timeout。最小保留CODEX共享槽/取消/同材料retry/timeout，移出DS正向步骤；新增DS请求403不应创建attempt/占槽、旧取消历史保持只读语义。不能删整个通用并发/限时场景。

## 必须保留的当前反向和历史读取

- `backend/tests/application/test_codex_only_scope.py`：新DS设置拒绝且settings/runs不增加；missing request/retry/material lookup前403；legacy settings显式重存CODEX/version/idempotency、历史不变；有效材料也不能派发新DS review。
- `frontend/tests/e2e/codex-only-scope.spec.ts`：历史DeepSeek设置/Record如实展示、当前新选项仅CODEX、旧记录GET/取消保持、403拒绝新DS、显式保存CODEX。应以新隔离fixture保留，不运行DS runtime；其现有专用 `playwright.codex-scope.config.ts`指向历史case目录，仅用于原scope验收，不可直接照搬固定目录为默认新profile。
- `backend/tests/application/test_capabilities.py`中DEEPSEEK review不满足当前CODEX资格的拒绝case应保留。出现DEEPSEEK字符串本身不是删除理由。

## 旧05/18 runner 红与当前源码的区别

旧05共享空基线冲突在2026-10-08 `evidence/review/fixes.md`已有逐文件隔离修复及当时默认15通过/2显式profile跳过；当前 `test-e2e.mjs`确实按文件创建新目录，reconcile文件内两例共享事实链。因此不依08旧红声明今天05仍失败。当前需修的是默认名单的CODEX范围一致性，而非再修05账户确认。

18旧固定SDK METHOD 20秒轮询红的有限等待修复也有历史receipt；当前默认files不包含该执行研究profile。`frontend/playwright.executions.config.ts`只匹配 `executions-live.spec.ts`并使用显式已保存数据目录；不在默认离线入口。旧失败、同版隔离绿与后继版本绑定应分别记录，不能据旧stdout推定当前实际失败，也不能把未运行的当前profile升级为PASS。

## 最小修复收口建议（由唯一实施者执行）

只调整当前验收集合和必要CODEX fixture/通用case，保留历史测试/receipt的可追溯位置；当前默认离线runner保持新profile、每文件隔离、清空凭据。正向DS历史移出默认而非标缺少能力；混合case拆留CODEX通用断言与legacy GET/cancel/403。修后用固定CODEX METHOD worker、真实SQLite及当前浏览器selector做有限同源验收，不做真实模型请求、DS endpoint/SDK验证或全量suite以证明排除。31条款库存仍partial，P95/五入口/真实通知及30authority由责任票接续。
