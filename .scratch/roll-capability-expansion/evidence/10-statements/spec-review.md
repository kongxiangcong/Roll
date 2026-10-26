# Ticket 10 — Spec review

只读审查相对 `e5977b3` 的自有财务增量，排除原 SSE 脏改动；未执行测试、联网或取数。依据 [ticket 10](../../issues/10-balance-cashflow.md)、spec US-19/20，定向复核后开放 0 项。

**P2 已关闭：跨接口幂等键命名空间。** 固定枚举 `INCOME/SUPPLEMENT` 选择各自 run table，同一服务逻辑复用，用户原键不再加前缀；旧 `financial_income_runs` 与09旧键保持原状，补充 run 存 `financial_supplement_runs`，facts 仍共用不可变版本表。公开回归以 statements=`three-once`、income=`SUPPLEMENT:three-once` 证明不再互斥，并保留重复返回和重启查询。`key-red.log` 保留原失败，`key-green.log` 4 PASS/33.22s；本复核未重跑。

其余检查未发现实质口径错误：复用原SDK/原件/版本框架，双接口同一8调用/18秒/8MiB预算；仅来源索引派生最近五期，原响应保持。资产负债时点与现金流年初累计分开，未证明的主体/单位/期间保持 UNKNOWN；负号与 null 保留，重复JSON列拒绝。关联同时核对证券、期间、主体、币种、单位、来源更新日和证据类型，返回每表fact版本引用；缺表不拼接。平衡差额按来源整数元精度给出1.5元容差，不平账改值。

`browser-green.log` 1 PASS/17.2s 证明 METHOD 单股联读与刷新；中文 reference 读取已明确 UTF-8。

## 独立生产验收复核

用户另批一次后，`production-attempt.json` 已成功并 `CLOSED_NO_RETRY`：5 HTTP、10 新事实、5 原响应 SHA 验证、账户及原09事实未变。脚本独占创建一次回执，逐字节核对后复制已关闭09隔离profile，仅调用新 statements collect；断言 production worker=None，没有固定响应或重新调用旧income端点。

`actual-source/capture.json` 为固定1.19.1/原源码SHA的真实SDK，完整保存 Index、两份日期索引及两份报表响应，共681064字节。`production-query.json` 中仅2026H1三表 MATCHED，资产差额0/容差1.5；其他新报表口径仍 UNKNOWN，保持单列，未为联读强拼。`production-browser.log` 1 PASS/13.8s；只读既有归档，验证原响应/PDF、负号、刷新及390px，collect拦截计数0。

原剩余真实整链运行项已补齐，可同步 acceptance/ticket/handoff 后记本票工程 complete，开放0；保留单证券、已证明口径范围，历史 PIT、模型输入和资金权限仍不授。预算继续封口，本复核没有执行任何HTTP或运行验收脚本。
