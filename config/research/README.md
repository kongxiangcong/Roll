# 个股研究档案

用 `roll research inputs 600362.SH` 读取该证券已发布档案中的公开证据引用。外部研究助手可以据此起草 Markdown，再通过 `roll research draft` 导入。研究者检查草稿后，以 `roll research publish` 显式确认。

Markdown 开头可用一对 `---` 包围 YAML 元数据。导入普通 Markdown 时，文件名（不含扩展名）作为草稿版本。发布时需要 `valid_until`，结论时点 `as_of` 缺省为导入时间。证据记录使用 `id`、`title`、`source`、`locator` 和 `url` 或 `document_id`，并可记录发行人、披露时间和实际取得时间。取得时间缺省为导入时间。结构化约束可在 `constraint_basis` 下列出支持它的证据 ID 或研究理由，确认人及发布时刻由发布命令写入。

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
