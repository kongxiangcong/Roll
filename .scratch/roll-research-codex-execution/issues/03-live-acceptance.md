# 03 · 真实个股研究与人工发布验收

Status: ready-for-agent

Resolution: completed

Closed: 2026-11-26

Blocked by: 01 受限 Codex 研究尝试、02 取消、中断恢复与同输入重试

## What to build

从验收库副本发起真实个股研究，按任务、尝试和版本复核公开证据及人工发布，记录可复核的目标机验收结果。

## Acceptance criteria

- [x] 正式 CLI 调用一次真实 Codex 得到江西铜业待审草稿，重读清单指纹、退出回执及日志。
- [x] 对照原文抽查事实引用、推断及未知字段。用同一发布入口验证仅签名被拒、事实依据、具名理由和生效计划的字段、确认人及有效期。
- [x] 记录可重跑的命令、公开输入和实际平台观测，复核文件、回环服务、进程树和同库写入，并完成后端回归。

## Comments

2026-11-26 在集成提交 `eb8fc95`、Ubuntu 24.04.5 LTS x86_64、Linux 6.8.0-138-generic、`codex-cli 0.172.0` 上验收。用 SQLite backup 制作 M0a 验收库副本，写入范围为副本。三个档案发布情形均使用工程验收署名“Codex 工程验收”。

### 真实往返与字段复核

任务 `task-c34b389365a84c7985cf839e99016aaf` 的冻结清单 SHA-256 为 `842d441dbb4de5ef4696b58f6a2be1d5f584ac95fa227001e15e535ebbf9c341`。沙箱内首次尝试 `attempt-715770afd0d74e0e99961ff47a890493` 得到 `failed / cli_exit`、退出码 1、空草稿版本。允许连接模型服务后，对原任务显式执行一次 Codex 重试。两次发送的公开输入字节完全相同，SHA-256 为 `68bcce22bb5a9338df5e39db96e25b1fc73a12d39575f7702b25214a233b2630`。各自日志的首条尝试 ID、末条退出码均与回执相符。公开输入含问题、截止时间、摘录、行情引用和既有档案的五条公开来源元数据。[实际公开输入](../evidence/public-input.json) · [成功回执](../evidence/codex-receipt.json)

真实模型 `gpt-6.2-sol` 返回 `draft_ready`，退出码 0，草稿版本和尝试 ID 均为 `attempt-3ea6fa67605b4a39bdcae7154f89c802`。用独立的 CLI 进程读回该版本的正文及字段，逐项核对如下。[按版本读回的草稿](../evidence/codex-draft.md)

| 字段 | 对照结果 |
| --- | --- |
| `fundamental_gate=pass` | 发行人 PDF 第 12 页合并现金流量表，以人民币元为单位，2026 年 1–9 月经营活动产生的现金流量净额为 14,162,724,945。草稿字段引用的材料 ID 和页码与冻结摘录相符，满足问题限定的当期净额大于零门禁。[发行人原表](https://static.cninfo.com.cn/finalpage/2026-10-29/1225636802.PDF#page=12) |
| `thesis_status=unknown`、`strategy_whitelist=[]` | 单期金额无法证明未来重复发生，草稿明确区分这项事实和持续性、投资逻辑、策略准入。两项非阻塞缺口分别要求多期可比现金流及成因说明、投资逻辑验证与具体策略准入依据。 |
| `invalidation_triggers` | 正式更正使同一期间、同一合并口径净额降至零或以下时再核查。字段引用同一摘录，正文将其列作条件。 |

### 发布、生效和历史

1. 导入 `stage02-signature-only`，保留全局证据、通过门禁及非空白名单，清空字段依据。具名发布返回退出码 2，报错“fundamental_gate=pass 须在 constraint_basis.fundamental_gate 引用对应证据”。按版本查询发布档案为空。
2. 将上述真实草稿按其回执版本发布，发布时间 `2026-11-26T14:11:30.842373Z`，生效时间 `2026-12-04T00:00:00+08:00`，恰逢旧档案到期。发布记录保留任务、尝试及第 12 页字段证据。
3. 另导入人工审阅对照版本 `stage02-review-control`，门禁有页段依据，非空白名单由审阅者限定为已冻结的日频趋势规则候选比较。发布时间 `2026-11-26T14:11:31.563162Z`，生效时间 `2026-12-07T00:00:00+08:00`。计划返回的 `strategy_whitelist` 字段依据含原理由和 `confirmed_by=Codex 工程验收`。[人工审阅对照版本](../evidence/review-control.md)

固定账本 `m0a-example`、标的和同一 LIVE_RUN 行情快照后，取得草稿、拒绝无依据版本以及两个成功发布之后，在原截止 `2026-11-26T07:38:52.909461Z` 重算的预览均与本轮发布前基线逐字段相等，SHA-256 为 `87d0ff8c65a3f0d738b511f0076f47b4c87e7c1f97b6404a92a0f0bcab541ea4`。改变计划截止时间得到下表。新版本的有效期均到 `2026-12-26T07:38:52.909461Z`；生效后的计划内确认人、期限、白名单和各字段依据与对应发布档案逐项相同。

| 计划截止（北京时间） | 预览采用的版本 | 研究状态 / 计划 |
| --- | --- | --- |
| 12-03 15:30 | `2026q3-buyback` | active / WATCH |
| 12-04 15:30 | 真实尝试版本 | active / WATCH |
| 12-07 15:30 | `stage02-review-control` | active / WATCH |
| 12-28 15:30 | `stage02-review-control` | expired / WATCH |

按原冻结计划 ID `65a4dae479fd3278cb52250927c91ef8daa835f2348aad2a4d7a1232558be9ab` 重读，发布前后与阶段 01 归档均全字段相等，SHA-256 为 `4a239d00321325854db24c664c9fb339ff951470d664e594ea3c5e808d154f5d`。按任务、两个尝试、真实草稿和两个发布版本分别重新启动 CLI 回读，均与各自的原记录相符。计划摘要使用键排序、紧凑分隔符、保留非 ASCII 原文的 UTF-8 JSON。

### 复验命令

在仓库根目录，`COPY` 指向 M0a 数据库的独立副本目录。验收使用 `/tmp/roll-stage02-acceptance-6pfq62g0`、`PYTHONPATH=/tmp/roll-stage02-accept-worktree/backend/src` 和 `/tmp/roll-v3-release-venv/bin/roll`。下例从归档恢复完全相同的提问与摘录。重跑需要新副本，以便保留发布前对照；任务 ID、尝试 ID 和实际发布时间按回执取值。表中历史日程用于回放本轮副本。若在这些生效日之后重新发布，需要选取仍在有效期内的研究材料、截止时间和未来生效日。

```sh
ev=.scratch/roll-research-codex-execution/evidence
input=$ev/public-input.json
roll_copy() { roll --data-dir "$COPY" "$@"; }
jq '.materials[0] | {title, source, locator, url, received_at, excerpt: .content}' "$input" > "$COPY/excerpt.json"
roll_copy research task run 600362.SH --executor codex --timeout 180 --basis announcement \
  --snapshot "$(jq -r .snapshot_id "$input")" --as-of "$(jq -r .as_of "$input")" \
  --question "$(jq -r .question "$input")" --require "$(jq -r '.required_titles[0]' "$input")" \
  --material "$COPY/excerpt.json" > "$COPY/run.json"
TASK=$(jq -r .task_id "$COPY/run.json")
ATTEMPT=$(jq -r .attempt_id "$COPY/run.json")
# 首次确认为连接失败时，在网络恢复后用原任务重试
if jq -e '.failure_kind == "cli_exit"' "$COPY/run.json" >/dev/null; then
  roll_copy research task retry "$TASK" --executor codex --timeout 180 > "$COPY/retry.json"
  ATTEMPT=$(jq -r .attempt_id "$COPY/retry.json")
fi
roll_copy research task show "$TASK"
roll_copy research task attempt "$ATTEMPT"
roll_copy research show 600362.SH --draft --version "$ATTEMPT"

# 在对照版本中清空字段依据，保留证据、门禁和白名单
sed -e 's/^version: stage02-review-control$/version: stage02-signature-only/' \
  -e '/^constraint_basis:/,/^---$/{ /^---$/!d; }' "$ev/review-control.md" > "$COPY/signature-only.md"
roll_copy research draft 600362.SH "$COPY/signature-only.md"
roll_copy research publish 600362.SH stage02-signature-only --reviewer 'Codex 工程验收' --effective-at 2026-12-04T00:00:00+08:00
# 上行预期退出 2，然后核对成功发布
roll_copy research publish 600362.SH "$ATTEMPT" --reviewer 'Codex 工程验收' --effective-at 2026-12-04T00:00:00+08:00
roll_copy research draft 600362.SH "$ev/review-control.md"
roll_copy research publish 600362.SH stage02-review-control --reviewer 'Codex 工程验收' --effective-at 2026-12-07T00:00:00+08:00
live=b6cac86c682fbe7d9cfeadbe65553567419472da29fd96304dfa7b55b228ce22
for at in 2026-11-26T07:38:52.909461Z 2026-12-03T15:30:00+08:00 2026-12-04T15:30:00+08:00 2026-12-07T15:30:00+08:00 2026-12-28T15:30:00+08:00; do
  roll_copy plan --preview --book-id m0a-example --symbol 600362.SH --snapshot-id "$live" --as-of "$at"
done
roll_copy plan --plan-id 65a4dae479fd3278cb52250927c91ef8daa835f2348aad2a4d7a1232558be9ab
```

### 目标机权限、进程和全套回归

集成提交从仓库根目录运行 `python -m pytest -q backend/tests`，141 项通过，耗时 97.62 秒，有一条既有 Starlette TestClient 弃用提示。实际 CLI 权限探针覆盖合成的 API key 和 ChatGPT 登录。宿主成功读取探针文件并访问回环服务，Codex 请求的工具列表为空，服务发出的两个强制工具调用均返回不支持，回环日志仅登记宿主对照。受控助手验证了取消、超时和执行者死亡后的进程树清理、同输入重试、同库并发读写与唯一终态。两组探针可分别用 `python -m pytest -q backend/tests/test_v3_codex_permissions.py` 与 `python -m pytest -q backend/tests/test_v3_research_lifecycle.py` 复跑。[权限观测](01-confined-codex.md) · [进程和同库写入观测](02-lifecycle.md)
