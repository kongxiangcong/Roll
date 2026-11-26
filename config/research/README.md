# 个股研究档案

用 `roll research inputs 600362.SH` 读取该证券已发布档案中的公开证据引用。外部研究助手可以据此起草 Markdown，再通过 `roll research draft` 导入。研究者检查草稿后，以 `roll research publish` 显式确认。

Markdown 开头可用一对 `---` 包围 YAML 元数据。导入普通 Markdown 时，文件名（不含扩展名）作为草稿版本。发布时需要 `valid_until`，结论时点 `as_of` 缺省为导入时间。证据记录使用 `id`、`title`、`source`、`locator` 和 `url` 或 `document_id`，并可记录发行人、披露时间和实际取得时间。取得时间缺省为导入时间。结构化约束可在 `constraint_basis` 下列出支持它的证据 ID 或研究理由，确认人及发布时刻由发布命令写入。

新发布的档案如设 `fundamental_gate: pass`，须在 `constraint_basis.fundamental_gate.evidence_refs` 引用本档案已登记的对应证据。设 `thesis_status: intact` 或给出非空 `strategy_whitelist` 时，对应字段须引用证据或用 `rationale` 写明人工判断理由。人工判断随发布记录确认人，沿用档案有效期。用 `roll plan --preview` 查看生效档案的逐项依据。

## 离线研究任务

用 `research task run` 固定问题、证据依据、行情快照和带时区的截止时点。下面的 `SNAPSHOT` 和 `AS_OF` 取自本地行情快照与研究截止时间。

```sh
roll research task run 600362.SH --snapshot "$SNAPSHOT" --as-of "$AS_OF" --question "核对经营现金流变化原因" --basis announcement --require "季报" --material report.json
roll research task run 600362.SH --snapshot "$SNAPSHOT" --as-of "$AS_OF" --question "最近交易日的收盘价是多少？" --basis stock-close
roll research task run 600362.SH --snapshot "$SNAPSHOT" --as-of "$AS_OF" --question "近五日个股相对行业的收益率差是多少？" --basis industry-comparison
```

公告问题默认使用 `announcement`。每份 `--material` JSON 填写 `title`、`source`、`locator`、`url` 或 `document_id`、实际取得时间 `received_at`，以及原文摘录 `excerpt` 或本地文件路径 `file`。可重复传入 `--material` 和必要公告标题 `--require`。

`stock-close` 核对快照覆盖范围内最近交易日的有效收盘价。`industry-comparison` 取该交易日结束的五个交易日收益率差，需要已确认的行业归属、行业指数和个股连续六个有效收盘价。草稿给出实际区间、数值和冻结行情引用。行情材料取得时间须在任务截止时点以内。缺少所选依据时按尝试返回阻塞缺口。

用 `research task show 任务ID` 重读冻结清单，用 `research task attempt 尝试ID` 重读结果。`research task supplement 任务ID --material report.json` 或 `--snapshot 新快照ID` 生成关联任务。`research task retry 任务ID` 复用冻结清单，用新回执的版本按 `research show 标的 --draft --version 版本` 审阅。

## 用 Codex 研究一份公开摘录

在已登录 Codex 的 Ubuntu 24.04 x86_64 主机上，先用 `codex --version` 确认版本为 `codex-cli 0.172.0`。与离线示例使用相同的材料 JSON，在命令中显式选择执行器。`--timeout` 是本次尝试的总秒数，默认 180 秒。

```sh
roll research task run 600362.SH --executor codex --timeout 180 \
  --snapshot "$SNAPSHOT" --as-of "$AS_OF" --material report.json \
  --question "报告第 12 页披露的累计经营活动现金流量净额是多少？"
```

运行时终端会显示任务 ID 和尝试 ID。另开终端并使用同一数据目录，即可执行以下命令。

```sh
roll research task attempt "$ATTEMPT_ID"
roll research task cancel "$ATTEMPT_ID"
roll research task retry "$TASK_ID" --executor codex --timeout 180
```

取消后查看 `cancelled` 回执，超时为 `timed_out`，执行者意外退出为 `interrupted`。同输入重试生成独立回执；补材料时用 `research task supplement "$TASK_ID" --executor codex --material 新材料.json`。遇到 `failed` 时，查看 `failure_kind` 与 `error`。`configuration` 提示应检查的安装或登录配置，`cli_exit` 给出服务或运行失败的诊断，`invalid_response` 表示结果未通过格式或证据校验。`log_ref` 和 `input_ref`（如有）均相对于 Roll 数据目录。取得 `draft_ready` 后用回执中的 `draft_version` 审阅，再具名发布。

## 江西铜业示例

两份草稿基于 2026 年 11 月 26 日核对的公开材料。初版提出盈利兑现假设，刷新版纳入实际回购进展。证据表保存披露日期与材料核对时间，发布命令另行记录实际发布时间。两份示例的有效期分别截至北京时间 2026 年 12 月 1 日和 12 月 4 日零时。

从仓库根目录使用一个独立的数据目录演练。

```sh
roll_research_demo_dir=$(mktemp -d)
roll --data-dir "$roll_research_demo_dir" research draft 600362.SH config/research/600362.SH/2026q3-cashflow.md
roll --data-dir "$roll_research_demo_dir" research publish 600362.SH 2026q3-cashflow --reviewer "本地研究者"

roll --data-dir "$roll_research_demo_dir" research draft 600362.SH config/research/600362.SH/2026q3-buyback.md
roll --data-dir "$roll_research_demo_dir" research show 600362.SH --draft
roll --data-dir "$roll_research_demo_dir" research show 600362.SH
roll --data-dir "$roll_research_demo_dir" research publish 600362.SH 2026q3-buyback --reviewer "本地研究者"

roll --data-dir "$roll_research_demo_dir" research show 600362.SH
roll --data-dir "$roll_research_demo_dir" research show 600362.SH --version 2026q3-cashflow
roll --data-dir "$roll_research_demo_dir" research inputs 600362.SH
```

发版时可用 `--effective-at` 指定未来的生效时点。以 `research show 600362.SH --as-of` 配合带时区的 ISO 8601 时刻回读当时的有效档案。到期时应核对新增公告并更新有效期，再以新版本发布。

`600362.SH/dividends.json` 记录了 2020 至 2026 年 11 月 25 日的八次 A 股权益分派。数据来自发行人实施公告，可用 `roll market import config/research/600362.SH/dividends.json` 追加到本地数据目录。每条记录保留公告定位、实际核对时间和可得时间依据。登记日、除息日及支付日来自原公告。每股实际派息用于在途权益和到账核算，除息参考扣减用于交易报价。

刷新版的经营现金流门禁读取结构化证据。用 `roll market import config/research/600362.SH/2026q3-cashflow-observation.json` 录入发行人三季报中的原始金额。档案用 `feature`、`operator` 和 `threshold` 声明可执行条件，正文保留研究推理。 [三季报第 12 页](https://static.cninfo.com.cn/finalpage/2026-10-29/1225636802.PDF#page=12)
