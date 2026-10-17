# 13 规格审查

| 验收条件 | 结论 | 证据 |
| --- | --- | --- |
| 现有入口展示报告截止/披露/获取时点、指标趋势、缺口、原文链接；紧凑可展开 | 通过 | 单股“财务观察”、历史“财务观察复盘”；browser-green.log |
| 分析文字只来自11确定性事实与12核实依据；结论/限制分开；不补数、不排名、不目标价 | 通过 | financial_observation.py；acceptance 文本；limitations |
| 一般非金融企业可用；金融/未知行业标记专用口径未支持，通用原表仍可看 | 通过 | observation-tests.log 修订行业用例；面板保持利润表/三表面板 |
| 版本化观察，历史复盘不被最新覆盖；不改模型/账户/资金资格 | 通过 | financial_observations 只追加；旧版本相等断言；账户 0→0 |
| API+浏览器验新鲜/过期/缺失/修订、手机、原文定位、刷新重放；禁用源不影响复盘 | 通过 | FRESH/MISSING、修订版本 2、禁用源用例、真实 Chrome、按 id 重放 |
| 版本、验收、真实/METHOD 边界、原失败与剩余 | 通过 | acceptance.md、code-versions.json、INTERRUPTED 保留 |

残余：3/4 PDF 未派生；120 天阈值仅展示；行业专用报表未支持。
