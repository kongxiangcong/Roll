# 05 · 审阅归档并完成真实助手联验

Status: ready-for-agent

Resolution: completed

Closed: 2026-11-27

Blocked by: 03, 04

## What to build

研究者从正式 CLI 完成一次江西铜业真实助手解读，核对回执中的交易和区段，按指定尝试和报告版本在任务内归档。工作台后续可通过同一任务读取完整证据；本票在 CLI 验收。

## Acceptance criteria

- [x] 在验收库副本上通过阶段 02 的真实受限助手执行一次开发解读。从报告中的收益、成本、成交日期和持仓区段定位到冻结回执，核查回撤期间持仓、差异集中情况及证据限制。保存可重放的命令和产物引用。
- [x] 归档指定尝试和报告版本。另起 CLI 按任务读回冻结预设、输入、回执、解读，以及目标尝试、报告版本、结论类别、审阅人、停止或继续的理由和归档时间。开发报告不能作为个股研究档案发布。
- [x] 核对四类结论及理由。动作一致、差异仅由缺数或费用解释、改善集中于单段时停止扩展，证据不足时保留缺口。仅在多个不重叠段仍有待解释差异时，记录下一项仓位对照的预定规则与计量口径，交由后续研究。分组日均收益仅支持提出假设，全窗平均持仓匹配仅用于事后归因，评估推广性需要新的独立数据。
- [x] 发起实验前保存固定当前盘后输入的 `roll plan --preview` 档案引用及正式验收、样本揭示和生产准入记录。归档后以相同输入核对仍引用原个股档案，各项记录逐项一致；`roll experiment verify m0a-jxcc-default` 仍能离线核验原报告。

## Comments

### 实际解读与归档

在集成代码 `b9a5bed` 上，从 M0a 验收库副本用 `codex-cli 0.172.0` 完成受限真实解读，退出码为 0。任务 `task-6e4e4c2eae104053917656ecec81b42a`，尝试 `attempt-2a6e1e03dd8f4c328a3e1db15bbc4bd6`，报告 `development-report-16b37bbc40ef27adf72b38546c536f9801dca897a08bca5c2d4c43f1de8ff9e2`。冻结回执为 `development-receipt-61f3eff090bf13cb3e4214e16ad00ef9c6bd3924c9b8b985376c603b0c014460`，实际输入 SHA-256 为 `79fbc058b32fb4278fd607a89f2cc7707ec4d514273ca31a272708152a394799`。另起 CLI 读取的尝试与原结果逐字段一致。报告引用了 2021-08-02 首次直接拦截及 2021-08-03 次日 E0 成交、后续不同的成交股数、两段相反方向的净值贡献及各自峰谷持仓。

首次联验在 `8aafe73` 得到可核对报告，暴露了费用归因判定说明的歧义。复审将它改为条件句，并让抽样公开包保留被拦截信号所链接的成交。上述最终联验使用新的任务，每次尝试由正式 CLI 调用助手一次。

`Codex 工程验收` 于 `2026-11-26T16:08:39.020367+00:00` 将最终报告归档为 `multiple_segments / continue`。理由引用 `segment:2021-08-03:2021-10-22` 和 `segment:2023-07-25:2023-10-18`。验收归档将后续比较的仓位上限示例预先固定为 50%，同时保存共同期初、权益口径和分段计量规则。独立 CLI 读回冻结清单、尝试、回执和归档，重复相同归档请求返回原记录。发布入口拒绝该版本。相同盘后预览继续采用 `2026q3-buyback`，正式验收、样本揭示、策略版本及准入事件、已发布档案与计划的行数和 SHA-256 均与归档前一致。原 M0a 回执 `experiment-result-a5da9c812eaa9e1fecacfad6b024da0b45f39fc80d63a99a26775aa21f492c85` 离线复算 `matches=true`。

### 复验命令

从项目根目录运行，将 `COPY` 设为 M0a 验收库副本的目录。实际报告、归档、离线复算和核对记录保存在[验收产物](../../../.roll-data/roll-research-e0-e1-acceptance/acceptance-audit.log)所在目录。以下命令从运行回执读取任务、尝试和报告版本。

```sh
roll_copy() { roll --data-dir "$COPY" "$@"; }
snapshot=a67c1c43cf4f284460ed6e987f8fd1a8a2f4e9f1720d9a431efe993901167bcb
roll_copy research task development --preset jxcc-e0-e1-v1 --snapshot "$snapshot" --executor codex --timeout 180 > run.json
TASK=$(jq -r .task_id run.json)
ATTEMPT=$(jq -r .attempt_id run.json)
VERSION=$(jq -r .report_version run.json)
roll_copy research task attempt "$ATTEMPT"
roll_copy research task development-receipt "$TASK"
roll_copy research task development-archive "$TASK" --attempt "$ATTEMPT" --report-version "$VERSION" \
  --conclusion multiple_segments --reviewer 'Codex 工程验收' --decision continue \
  --reason '两个区段有方向相反且超过交易费用与滑点的差异' \
  --segment-ref segment:2021-08-03:2021-10-22 --segment-ref segment:2023-07-25:2023-10-18 \
  --sizing-rule 'E0 与 E1 均固定 50% 总仓位及单票配置上限，保留各自的入场条件和共同退出规则' \
  --measurement '使用共同起点、相同模拟资金、原始收盘和税前权益，逐日计量净收益、最大回撤、费用与分段净值贡献'
roll_copy research task show "$TASK"
roll_copy research task development-verify "$TASK"
roll_copy plan --preview --book-id m0a-example --symbol 600362.SH \
  --snapshot-id b6cac86c682fbe7d9cfeadbe65553567419472da29fd96304dfa7b55b228ce22 \
  --as-of 2026-11-26T07:38:52.909461Z
roll_copy experiment verify m0a-jxcc-default
```
