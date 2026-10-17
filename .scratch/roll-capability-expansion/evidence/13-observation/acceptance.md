# 13 财务分析进入单股与复盘验收

新增版本化、确定性的财务观察：只消费 11 票指标与已保存财务事实、12 票 PDF 派生，不调用来源、不使用 LLM、不写模型/账户/资格。

## 交付

- `backend/src/roll/market/financial_observation.py`：读取截至时点事实并调用 `financial_metrics.metrics`；生成状态（FRESH/STALE/MISSING）、披露/更新/首次接收/可用时点、行业支持、描述性事实、结论、4期趋势、缺失原因、PDF原件与解析链接、限制；以事实/解析的输入摘要做唯一键，`financial_observations` 只追加版本，旧观察不被覆盖。
- 公开 API：`GET /api/market/financial/{instrument}/observations[?known_by=]` 返回 current + versions；`GET /api/market/financial/observations/{id}` 读取历史版本。
- 页面：单股卡片新增“财务观察”折叠区；历史记录新增“财务观察复盘”，可填已知截至回放。默认紧凑，趋势/原件/版本与限制可展开；描述性结论与限制分开。
- 不新增一级入口；行业仅 `ORG_TYPE=通用` 给出专用比率，其他/未知行业明确“专用口径未支持”，通用原表仍可读。

## 真实数据验收

- 数据：`.scratch/r10real` 的隔离副本 `.scratch/r13real`（15 条事实：INCOME/BALANCE/CASH_FLOW×5 期，均为 09/10 真实保存事实）。
- `real-observation.json` / `real-observation.log`：状态 FRESH、最新报告期 2026-06-30、行业支持 GENERAL_SUPPORTED；分析文字包含 3,071.55 亿元/+19.53%、86.32 亿元/+106.77%、58.14 亿元/0.61、5.82%/3.09%/65.48%；4 期趋势；4 份 PDF 原件；1 份真实 Docling COMPLETE 派生（10—10 页）与观察关联；账户版本 0→0，network_calls=0。
- 真实副本另经一次 Docling 解析（`b7712d44…`，此前一次在宿主截止时中断并保留 INTERRUPTED），观察升为版本 2；未删除中断记录。
- `browser-green.log`：真实副本 Chrome 1 PASS/13.0s，单股展示、趋势、原件/派生链接、390px 无横向溢出（`mobile.png`），历史复盘截至 2026-04-01 显示“缺失/不补造默认值”，0 采集POST。

## METHOD 与回归

- `observation-tests.log`：2 passed/19.36s。覆盖：当前 FRESH、报告期/时点、文本数值、4期趋势、PDF 文档、同输入幂等且只 1 版本、历史缺失、按 id 读取；修订后版本 2、行业转金融不支持、行业专用缺口、旧版本逐字节相等；禁用财务源后仍从保存事实读取且 observation_id 不变。
- `regression.log`：metrics/statements/observation/documents 11 passed/100.90s；`build.log` TypeScript/Vite 通过。
- 审查发现：当前查询把秒级时间纳入输入摘要，导致每次 GET 生成新版本；已改为当前查询使用 `CURRENT` 哨兵，显式截至才纳入时间。修复后幂等测试通过。

## 限制

- 12 票仅 1/4 份 PDF 已完成派生，观察明确列出未解析缺口，不冒充全部可追溯。
- 新鲜/过期阈值 120 天是展示规则，不是披露时限结论；历史 PIT 资格仍未授予。
- 描述性文字只由已确定值拼装，不证明因果、排名、估值或收益；不改变账户、资金、资格、模型或真实前向起点。
- 行业支持依据来源 `ORG_TYPE`；未做银行/保险专用报表口径。
