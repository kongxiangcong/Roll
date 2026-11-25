# Roll v2 重构设计方案文档

**项目定位**：个人 A 股离线优先（Offline-First）量化辅助与多维晴雨表工作台  
**运行环境**：Windows 本机（单机一键同步，无需 VPS/NAS，无需 Level-2 分时流）  
**主力数据源**：扶摇（Fuyao）REST API + AKShare（ETF 资金流/两融/广度/财报补充）+ BaoStock（免费兜底）  
**初始跟踪池**：宽基指数/ETF + 行业参考 ETF + 江西铜业（600362.SH）、中国船舶（600150.SH）、剑桥科技（603083.SH）  
**文档日期**：2026-11-24  

---

## 1. 重构目标与四条工程铁律

Roll v0 不可用的本质不是缺功能，而是被过度防御的合规官僚层（26 个 `successor_*` 模块、无 `PASS` 路径的 G1–G7 门禁、60 份 Playwright 配置、SHA-256 源码自校验、单股 `600362` 硬编码）彻底锁死。v2 重构以**“先跑通、能持续用、敢参考、易维护”**为唯一准绳，确立四条不可违背的工程铁律：

1. **拒绝过度防御代码**：全面删除源码 SHA-256 自校验、子进程 Socket 劫持、模拟机构审批流（`capabilities` / `technical_review` / `G1–G7`）、以及拒绝输出今日结果的日期封锁。数据缺失时优雅降级并标注来源状态，绝不让整个系统瘫痪。
2. **彻底解耦，绝不绑死**：不绑死单只股票（全量由 `watchlist.yaml` 驱动），不绑死单一数据源（统一 `MarketDataProvider` 接口，扶摇为主力、AKShare/BaoStock 可插拔），不绑死 Windows 后台常驻进程（支持一键离线同步 CLI、WorkBuddy 调用与本地网页三种用法）。
3. **最小化架构与中间产物**：后端从 143 个 Python 文件 / 28,792 行 / 425 个路由，压缩至 **约 18 个核心文件 / ≤4,500 行 / ≤18 个 REST 接口**；前端从 87 个文件 / 24 个页面 / 60 份 E2E 配置，收敛为 **3 个核心页面 / 1 份测试配置**；移除源码树中 19.4 MB 的静态 PDF/HTML 校验原件。
4. **信号透明且先控风险**：放弃单股 4 特征线性模型预测涨跌的死胡同，回归**“多背景交叉晴雨表（0–100）+ 历史分箱实证胜率 + 确定性仓位/止损风控”**。先管住回撤和仓位，再追求超额收益。

---

## 2. 大手术清理清单（先归档，再彻底删除）

执行清理前，先在本地切出一个只读备份分支保存 v0 完整历史，随后在主干执行大刀阔斧的删除：

```powershell
git checkout -b archive/v0-legacy
git checkout -b refactor/v2-barometer
```

### 2.1 后端清理与保留矩阵

| 路径 / 模块 | 动作 | 规模 | 理由 |
|---|---|---|---|
| `backend/src/roll/accounts/` | **保留** | 7 文件 / 1,832 行 | Decimal 精确记账、成交/现金事件、CSV 导入与对账非常扎实；仅解耦 `capabilities` 引用 |
| `backend/src/roll/market/rules.py` | **保留** | 191 行 | A 股交易日历、T+1、100 股整数手规则直接复用 |
| `backend/src/roll/research/execution.py`<br>`backend/src/roll/research/historical_costs.py` | **保留精简** | 498 行 | A 股佣金、过户费、印花税、滑点计算精确；移除原件哈希校验 |
| `backend/src/roll/research/statistics.py` | **保留精简** | 192 行 | 保留 `brier`、`reliability_bins`、`continuous_summary` 与块自助法作回测诊断，删掉 `method_manifest` |
| `backend/src/roll/market/fuyao.py` | **重构升级** | 106 行 | 抽离为标准 `FuyaoProvider`，成为主力日线/指数/除权数据源 |
| `backend/src/roll/market/baostock.py` | **简化留底** | 205 行 | 删掉子进程 Socket 劫持与 `API_KEY` 强校验，默认 `PUBLIC` 模式 + 支持复权作为免费兜底 |
| `backend/src/roll/research/successor_*.py` | **全部删除** | **26 文件** | 纯历史迭代残留，无任何实际消费者 |
| `backend/src/roll/research/validation.py`<br>`feature_protocol.py` / `policy_successors.py`<br>`independent_validation.py` / `technical_review.py`<br>`registry.py` / `design.py` / `models.py` / `shadow.py` | **全部删除** | **25+ 文件** | 死锁源头（硬编码无 PASS、特征不可执行、玩具 4 特征模型） |
| `backend/src/roll/decisions/capabilities.py`<br>`actions.py` / `intents.py` / `lifecycle_journal.py`<br>`loss_recovery.py` / `monitoring.py` / `notifications.py` | **全部删除** | **10 文件** | 过度设计的机构权限审批与状态机，由新的 `risk/` 模块取代 |
| `backend/src/roll/agents/` | **全部删除** | **9 文件** | Codex/DeepSeek 审阅与取证壳，v2 不在核心链路引入 LLM 投票 |
| `backend/src/roll/market/cnequity*.py`<br>`sse_*.py` / `cninfo_history.py` / `sentiment*.py`<br>`financial_documents.py` / `news_*.py` / `sohu.py` | **全部删除** | **30+ 文件** | 单股 `600362` 硬编码、孤立 venv、FinBERT/Docling 重型依赖与拒收 ETF 新闻的规则 |
| `backend/src/roll/market/reference/`<br>`backend/src/roll/market/financial_reference/`<br>`backend/src/roll/research/reference/` | **全部删除** | **146 文件 / 19.4 MB** | 静态 PDF/HTML/raw 报文不应提交在代码仓库中 |
| `backend/src/roll/runtime/` & `worker.py` | **全部删除** | **10 文件** | 废除三进程租约与 Windows Job Object 锁；离线一键同步不需要常驻后台守护 |
| `backend/requirements-*.lock` | **全部删除** | **4 文件** | 合并为单一 `backend/pyproject.toml` + `uv.lock`，彻底消除多套孤立 venv |

### 2.2 前端、文档与脚本清理矩阵

| 路径 / 模块 | 动作 | 规模 | 理由 |
|---|---|---|---|
| `frontend/playwright.*.config.ts` | **删除 59 份** | 60 → 1 份 | 仅保留 1 份 `playwright.config.ts` |
| `frontend/src/components/successor-*.tsx` | **全部删除** | 16 文件 | 对应已删除的后端后继协议 |
| `frontend/src/pages/` & `components/` | **精简重构** | 87 → ~15 文件 | 收敛为 3 个主页面（晴雨表 / 持仓与风控 / 回测校准） |
| `docs/`（64 份契约文档） | **全部清空重写** | 64 → 2 份 | 仅保留 `README.md` 与本设计文档 `docs/ROLL_V2_ARCHITECTURE.md` |
| `scripts/`（30 个脚本） | **删除 28 个** | 30 → 2 个 | 删掉全部 `reconstructed19_*` 与历史验收脚本；只保留 `scripts/roll-sync.ps1` 与 `scripts/start.ps1` |

---

## 3. v2 目标目录结构与极简架构

v2 是一个**单进程、离线优先、CLI 与 Web 共享同一核心库**的模块化单体。平时电脑关机完全无所谓；每天收盘后（或任何你需要的时候）点一下网页的「一键同步」或运行一条 `roll sync` 命令，10–15 秒内完成增量拉取、晴雨表重算与风控扫描，结果同时落库并支持导出 JSON/Markdown 供 WorkBuddy 读取。

```text
Roll/
├── config/
│   └── watchlist.yaml              # 宽基、行业ETF、跟踪个股、风控参数统一配置
├── .env                            # FUYAO_API_KEY=...（不提交Git）
├── backend/
│   ├── pyproject.toml              # 唯一依赖文件（fastapi, httpx, akshare, baostock, pandas, numpy）
│   ├── src/roll/
│   │   ├── config.py               # 加载 .env 与 watchlist.yaml
│   │   ├── db.py                   # 单一 SQLite (WAL) 连接与建表
│   │   ├── accounts/               # 【保留】十进制账本、成交、现金流、CSV导入、估值
│   │   ├── market/
│   │   │   ├── rules.py            # 【保留】A股交易日历、T+1、手数规则
│   │   │   ├── provider.py         # 统一 MarketDataProvider 抽象基类
│   │   │   ├── fuyao_provider.py   # 【主力】扶摇 REST API（日线前复权/不复权/指数/除权）
│   │   │   ├── akshare_provider.py # 【补充】ETF份额资金流、两融、涨跌家数、PE/PB、财报
│   │   │   ├── baostock_provider.py# 【兜底】免费历史日线回退源（PUBLIC模式）
│   │   │   └── sync.py             # 一键全量/增量离线同步引擎（幂等 upsert）
│   │   ├── barometer/
│   │   │   ├── factors.py          # 四维正交因子计算（趋势/资金流/广度与RS/估值排雷）
│   │   │   └── engine.py           # 0–100 晴雨表评分、仓位区间映射、缺失降级
│   │   ├── risk/
│   │   │   └── rules.py            # 个股 ATR 移动止损、20日低点破位、单票上限、财报红灯
│   │   ├── backtest/
│   │   │   ├── costs.py            # 【保留】A股佣金/印花税/过户费/滑点
│   │   │   ├── walk_forward.py     # 5年滚动样本外回测 + 5分箱实证胜率/回撤统计
│   │   │   └── metrics.py          # 【保留精简】Brier Score、净值回撤、块自助法诊断
│   │   ├── api/
│   │   │   ├── app.py              # FastAPI 装配入口（挂载静态前端 + 4组路由，≤18接口）
│   │   │   ├── routes_sync.py      # 同步与数据源健康检查
│   │   │   ├── routes_barometer.py # 今日晴雨表、历史序列、个股风控卡
│   │   │   ├── routes_accounts.py  # 账户持仓、成交录入、CSV导入
│   │   │   └── routes_backtest.py  # 回测执行与校准报告
│   │   └── cli.py                  # `roll sync / report / backtest / serve`（供WorkBuddy直接调用）
│   └── tests/                      # 精简为核心单元测试（账本、因子、晴雨表、回测）
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── Barometer.tsx       # 页面1：今日晴雨表 + 总仓位建议 + 一键同步
│   │   │   ├── Portfolio.tsx       # 页面2：我的持仓与3只跟踪股风控线 + 快速记账
│   │   │   └── Backtest.tsx        # 页面3：5年样本外回测曲线 + 分箱胜率校准表
│   │   └── api.ts
│   └── playwright.config.ts        # 唯一 E2E 配置
└── scripts/
    ├── roll-sync.ps1               # Windows 一键同步并输出今日报告（可配任务计划）
    └── start.ps1                   # 单进程启动 API + 托管构建后的前端网页
```

---

## 4. 数据源与离线一键同步设计（扶摇为主力）

### 4.1 数据职责分工（不重不漏）

| 数据维度 | 主力来源 | 备用来源 | 同步频率与历史深度 | 用途 |
|---|---|---|---|---|
| 个股历史日线（前复权 + 不复权） | **扶摇 API** (`/api/a-share/prices/historical`) | BaoStock (`PUBLIC`) | 首次拉 6 年（2020 至今），日常增量补齐 | 算 MA20/MA60、ATR 止损、RS、个股回测 |
| 宽基与行业指数/ETF 日线 | **扶摇 API** (`/api/a-share-index/prices/historical`) | AKShare / BaoStock | 首次拉 6 年，日常增量补齐 | 算大盘趋势、20 日年化波动率、行业 RS |
| 除权除息与复权因子 | **扶摇 API** (`/api/a-share/corporate-actions/adjustment-factors`) | BaoStock | 随个股同步增量拉取 | 精确还原真实持仓分红与后复权收益 |
| 宽基/行业 ETF 每日份额与净值 | **AKShare**（上交所/深交所 ETF 份额接口） | 手动 CSV 导入 | 首次拉 3–5 年，日常盘后增量 | 计算真实净申赎资金流：`Δ份额 × 单位净值` |
| 沪深两融余额与全市场涨跌家数 | **AKShare**（两融汇总 + 市场广度） | 优雅降级（权重重分配） | 日常盘后增量拉取 | 衡量杠杆资金风险偏好与市场赚钱效应 |
| 个股 PE/PB 分位与核心财报指标 | **AKShare**（估值序列 + 利润表/现金流/资产负债表） | 优雅降级 | 按季/按周缓存更新 | 估值分位打分 + 财报暴雷红绿灯过滤 |

### 4.2 扶摇主力 Provider 契约（复用已验证接口）

直接沿用现有 `fuyao.py` 和 `evidence.py` 中已验证过的扶摇 REST 契约，彻底剥离冗余的 SHA-256 报文封存逻辑，只保留干净的 HTTP 重试与字段清洗：

- **Base URL**：`https://fuyao.aicubes.cn`
- **鉴权头**：`X-api-key: <FUYAO_API_KEY>`（从 `.env` 读取）
- **核心端点**：
  - 个股日线：`GET /api/a-share/prices/historical?thscode=600362.SH&interval=1d&start=<ms>&end=<ms>&adjust=forward`（同时拉一次 `adjust=none` 存原始收盘价用于真实成交对账）
  - 指数日线：`GET /api/a-share-index/prices/historical?thscode=000300.SH&interval=1d&start=<ms>&end=<ms>`
  - 最新快照：`GET /api/a-share/prices/snapshot?thscodes=600362.SH,600150.SH,603083.SH`（盘中按需看一眼时用，不作为日线回测依据）
  - 除权因子：`GET /api/a-share/corporate-actions/adjustment-factors?thscode=600362.SH&from=2020-01-01&to=<today>`
- **代码格式转换**：统一在内部使用 `600362.SH` / `000300.SH` / `159915.SZ` 标准格式，告别 v0 繁琐的 `SSE:600362` 转换层。
- **增量同步策略**：查询本地 `daily_bars` 表中每个标的的 `MAX(trade_date)`，自动从 `last_date - 5天`（覆盖偶尔的上游修正）拉取至今天，使用 `INSERT OR REPLACE` 幂等写入；若本地为空，自动拉取过去 6 年历史。

### 4.3 初始 `config/watchlist.yaml` 配置模板

```yaml
provider:
  primary: fuyao
  fallback: baostock
  supplement: akshare
  history_start: "2020-01-01"

benchmarks:
  market_index: "000300.SH"       # 沪深300（主趋势与波动锚）
  broad_etfs:
    - { code: "510300.SH", name: "沪深300ETF" }
    - { code: "510500.SH", name: "中证500ETF" }
    - { code: "159915.SZ", name: "创业板ETF" }
    - { code: "588000.SH", name: "科创50ETF" }

watchlist:
  - code: "600362.SH"
    name: "江西铜业"
    sector_etf: "512400.SH"       # 有色金属ETF（行业资金流与强弱参照）
    max_position_pct: 0.25
    atr_stop_multiplier: 2.2
  - code: "600150.SH"
    name: "中国船舶"
    sector_etf: "512660.SH"       # 军工ETF（行业资金流与强弱参照）
    max_position_pct: 0.25
    atr_stop_multiplier: 2.2
  - code: "603083.SH"
    name: "剑桥科技"
    sector_etf: "515880.SH"       # 通信ETF（行业资金流与强弱参照）
    max_position_pct: 0.20        # 高波动科技成长股，单票上限略收紧
    atr_stop_multiplier: 2.5

risk_defaults:
  portfolio_drawdown_alert: 0.08  # 组合回撤达到 8% 触发降仓强提醒
  min_trading_days_for_score: 60  # 最少需要 60 个交易日才计算完整指标
```

---

## 5. SQLite 精简数据模型（单库 5 张新表 + 原账本表）

保留 `roll/accounts/` 原有的 9 张账本表不变（保证你如果已有历史账户数据可以零损迁移），彻底废除 v0 超过 25 张研究/审计/后继表，新建 **5 张极简核心业务表**：

| 表名 | 主键 | 核心字段 | 说明 |
|---|---|---|---|
| `daily_bars` | `(symbol, trade_date)` | `open_qfq`, `high_qfq`, `low_qfq`, `close_qfq`, `close_raw`, `volume`, `amount`, `adj_factor`, `source` | 存前复权（算指标/止损）+ 不复权（对账）+ 复权因子（算后复权收益） |
| `etf_flows` | `(symbol, trade_date)` | `shares`, `nav`, `delta_shares`, `net_flow_yuan`, `source` | 每日 ETF 份额变动与净申赎资金额（元） |
| `market_breadth` | `trade_date` | `advancing`, `declining`, `unchanged`, `total_turnover_yuan`, `margin_balance_yuan` | 全市场涨跌家数、两市总成交额与两融余额 |
| `fundamentals` | `(symbol, report_date)` | `pe_ttm`, `pb`, `revenue_yoy`, `net_profit_yoy`, `ocf_to_profit`, `debt_ratio`, `updated_at` | 个股估值与季度财报排雷指标 |
| `barometer_snapshots` | `trade_date` | `total_score`, `regime`, `target_pos_min`, `target_pos_max`, `pillar_scores_json`, `stock_signals_json`, `forward_20d_return` | 每日晴雨表快照；满 20 个交易日后自动回填真实收益，形成持续校准闭环 |

---

## 6. 核心算法：四维多背景晴雨表（0–100）与确定性风控

放弃单股黑盒预测，改用**全部公式透明、可回测、可解释的四维加权打分模型**。每个维度输出 `[0, 100]` 连续分值，缺失子项自动按剩余有效权重归一化（`effective_score = sum(w_i * s_i) / sum(w_i)`），并透明展示“数据完整度”。

### 6.1 四维市场晴雨表公式（总分 0–100）

| 维度 | 权重 | 核心指标与计算方式 | 映射为 0–100 分的确定性规则 |
|---|---|---|---|
| **① 大盘趋势与波动** | **35%** | 1. 沪深 300 收盘价相对 MA20 / MA60 / MA120 均线排列<br>2. 20 日年化波动率在过去 250 日中的历史分位<br>3. 两市成交额 / 20 日均量 | 站上 MA20/60/120 各得基础分；均线多头排列加分；波动率高于历史 85% 分位（恐慌暴跌）扣分；放量站上均线加分，缩量阴跌扣分 |
| **② 真实 ETF 资金流与两融** | **30%** | 1. 4 只宽基 ETF 过去 5 日与 20 日合计净申赎额（Z-score 标准化）<br>2. 沪深两融余额 10 日变化率 | 宽基 ETF 连续净流入（Z-score > +0.5）高分，持续净流出（Z-score < -0.5）低分；两融温和上行加分，急剧去杠杆（5 日降幅 > 2%）大幅扣分 |
| **③ 市场广度与行业强弱** | **20%** | 1. 全市场 5 日平均涨跌家数比 `Adv / (Adv + Dec)`<br>2. 跟踪池对应行业 ETF（有色/军工/通信）相对沪深 300 的 20 日超额收益 RS | 5 日涨跌比 > 0.55 为赚钱效应扩散区（高分），< 0.40 为亏钱效应冰点区（低分）；行业 RS 跑赢基准加分 |
| **④ 估值水位与拥挤度** | **15%** | 沪深 300 近 5 年滚动 PE/PB 历史分位数 | 低估区（分位 < 30%）给高安全边际分（80–100），中枢区（30%–70%）给中性分（50），过热区（> 85%）给低分（15–25）提醒防泡沫 |

### 6.2 晴雨表分值 → 操作与仓位映射

| 晴雨表区间 | 市场状态（Regime） | 建议总仓位上限 | 核心操作纪律 |
|---|---|---|---|
| **75 – 100** | 进攻区（Risk-On） | **60% – 80%** | 趋势与资金共振；允许对行业 RS 靠前、财报绿灯标的按计划分批建仓，使用跟踪止盈 |
| **50 – 74** | 均衡区（Neutral） | **40% – 60%** | 结构分化市；只持有相对强弱跑赢大盘的标的，不追高，触发止损即换弱留强 |
| **25 – 49** | 谨慎区（Caution） | **20% – 35%** | 趋势走弱或资金流出；**禁止新开仓**，跌破个股止损线果断减仓降险 |
| **0 – 24** | 防守区（Risk-Off） | **0% – 15%** | 系统性风险或高波杀跌；保本第一，不逆势补仓，等待右侧站回 MA20 或资金显著回流 |

### 6.3 个股评估卡与机械风控规则（针对 600362 / 600150 / 603083）

每只跟踪或持仓股每天同步后输出一张**确定性操作卡**，不给模糊观点，只给 4 项硬指标：

1. **趋势与行业共振状态**：股价是否位于 `MA20` 上方 + 所属行业 ETF 20 日相对沪深 300 是否跑赢（`RS > 0`）+ 所属行业 ETF 近 5 日是否净流入。
2. **动态 ATR 移动止损位**：以持仓入场后最高收盘价为基准，`StopPrice = HighestClose - k × ATR(14)`（江西铜业/中国船舶 `k=2.2`，高波剑桥科技 `k=2.5`），同时监控是否跌破近 20 日收盘低点；收盘价跌破即触发 **红色止损提醒**。
3. **基本面排雷红绿灯（一票否决）**：最新季报若同时出现“营收同比 < -10% 且 扣非净利同比 < -20%”或“经营现金流连续为负且资产负债率 > 75%”，标为 **红灯（禁止加仓/提示降仓）**。
4. **仓位上限校验**：结合 `accounts/` 真实持仓市值，若单票占比超过 `watchlist.yaml` 设定的 `max_position_pct`（20%–25%）或总仓位超过当日晴雨表建议上限，直接输出具体**建议减仓股数（100 股整数倍）**。

---

## 7. 务实回测与概率校准方案（替代 G1–G7 死锁）

v0 之所以永远卡在 `INCONCLUSIVE`，是因为它要求 2.5 年实盘前向数据才能解锁。v2 改为业界主流的 **Walk-Forward 历史滚动样本外回测 + 实盘持续校准**：

1. **防未来函数底线（保留好习惯，去掉官僚壳）**：
   - 所有滚动分位数（波动率分位、ETF Z-score、估值分位）严格只使用 `t` 日及之前的数据计算（Expanding / Rolling 250d Window）。
   - 调仓执行统一按 `T+1` 次日开盘价成交，复用 `backtest/costs.py` 扣除真实 A 股双边佣金（万三，最低 5 元）、卖出印花税（千分之 0.5）、过户费（十万分之一）及单边 5 bps 滑点。
2. **回测基准对比（2020-01 至今，覆盖牛/熊/震荡全周期）**：
   - **策略曲线**：按每日晴雨表分值动态调整仓位上限（0%–80%）持有宽基或跟踪池等权组合 + ATR 止损。
   - **对比基准**：① 满仓持有沪深 300（Buy & Hold）；② 简单 MA20 均线择时；③ 恒定 50% 仓位。
   - **核心检验指标**：年化收益、**最大回撤（最核心）**、卡玛比率（年化/最大回撤）、换手率与扣费后净值。
3. **晴雨表分箱实证概率表（回答“这个分数在历史上到底有多准？”）**：
   - 将 6 年历史每日晴雨表按 5 个区间（`0–20` / `20–40` / `40–60` / `60–80` / `80–100`）分箱，直接统计每个区间往后 20 个交易日的：**历史正收益胜率、中位收益率、最差 5% 尾部回撤**。
   - 每天前端展示晴雨表分值时，旁边直接附带一句实证参考（例如：“当前得分 68；过去 6 年处于 60–80 区间时，未来 20 日历史胜率 XX%，中位收益 +X.X%，最大回撤 -X.X%”），让你基于真实统计分布做决策，而不是盲信某个黑盒概率。
4. **实盘滚动自我校准**：`barometer_snapshots` 每天自动存快照；每满 20 个交易日自动回填真实涨跌幅，用保留的 `statistics.py` 计算实盘 Brier Score 与分箱偏差，持续监控模型是否失效。

---

## 8. 极简 API、3 页前端与 WorkBuddy / CLI 接入

### 8.1 精简 REST API 清单（总计 14 个接口，取代原 425 个）

| 分组 | 接口 | 职责 |
|---|---|---|
| 同步 | `POST /api/sync` | 一键触发全量/增量同步（扶摇 + AKShare），返回各源耗时与状态 |
| 同步 | `GET /api/sync/status` | 查看各标的最新数据日期、数据完整度与上次同步时间 |
| 晴雨表 | `GET /api/barometer/today` | 返回当日总分、4 维拆解、建议总仓位、对应历史分箱胜率 |
| 晴雨表 | `GET /api/barometer/history?days=250` | 返回历史晴雨表走势与大盘对照序列 |
| 个股风控 | `GET /api/watchlist/signals` | 返回 3 只跟踪股及宽基的趋势、RS、ATR 止损位、财报红绿灯与建议动作 |
| 回测 | `POST /api/backtest/run` | 按指定日期区间运行 Walk-Forward 回测（秒级完成） |
| 回测 | `GET /api/backtest/latest` | 读取最新回测净值曲线、最大回撤对比与 5 分箱概率表 |
| 账本（保留） | `GET /api/account`<br>`POST /api/account/fills`<br>`POST /api/account/cash`<br>`POST /api/account/csv/import`<br>`POST /api/account/reconcile` | 完整保留你现有的 Decimal 精确账本、成交录入、CSV 批量导入与对账能力 |
| 配置 | `GET /api/config/watchlist`<br>`PUT /api/config/watchlist` | 查看/动态增删跟踪股与风控参数（立即生效） |

### 8.2 CLI 与 WorkBuddy 无缝接入设计

为了方便你在家里的 Windows 电脑上通过 **WorkBuddy**、快捷键或 Windows 任务计划直接调用，提供独立 CLI 入口 `roll`：

```powershell
# 1. 收盘后一键同步最新数据并计算今日晴雨表与风控
uv run roll sync

# 2. 输出结构化 JSON 或精简 Markdown 日报（WorkBuddy 可直接读取解析或推送）
uv run roll report --format markdown --out reports/today.md
uv run roll report --format json

# 3. 本地跑一次 2020 至今的 6 年样本外回测并刷新校准表
uv run roll backtest --start 2020-01-01

# 4. 启动本地单进程 Web 工作台（API + 静态前端合一，端口 8010）
uv run roll serve --port 8010
```

### 8.3 前端收敛为 3 个核心页面

1. **今日晴雨表（默认首页）**：顶部 0–100 晴雨表仪表盘 + 建议总仓位区间 + 历史同区间胜率参考 + 右上角「一键同步」按钮；下方四维得分条形拆解；最底部展示今日触发的红/黄风控提醒（无事则安静显示“今日无风控触发”）。
2. **我的持仓与跟踪池**：直接展示账户真实总资产/现金/当前实际仓位 vs 晴雨表建议仓位的偏差；下方列出宽基与 **江西铜业、中国船舶、剑桥科技** 的实时风控卡（现价、MA20 位置、行业 RS、ATR 止损价、距止损百分比、财报灯）+ 快捷「记录成交 / 导入 CSV」抽屉。
3. **回测与校准验证**：展示 2020 至今晴雨表动态控仓 vs 满仓沪深 300 的净值与回撤对比图、5 分箱历史 20 日胜率/盈亏比表格，以及实盘跟踪校准记录。

---

## 9. 4 周分阶段实施工单（可直接按单落地）

| 阶段 | 时间 | 核心工作 | 明确验收标准（DoD） |
|---|---|---|---|
| **Phase 1：清仓瘦身与扶摇打通** | 第 1 周 | 切备份分支；执行第 2 章删除清单；新建 `config/watchlist.yaml`、`db.py`、`FuyaoProvider` 与 `sync.py`；配置 `.env` 写入 `FUYAO_API_KEY` | 运行 `uv run roll sync` 能在 30 秒内用扶摇拉通 2020 至今沪深 300 与 600362/600150/603083 的前复权+不复权日线并落入 SQLite；无任何 503 或硬编码报错 |
| **Phase 2：补齐 AKShare 资金流与晴雨表引擎** | 第 2 周 | 接入 `AKShareProvider`（ETF 份额净申赎、两融、涨跌家数、PE/PB、季报 4 项）；实现 `barometer/` 四维打分与 `risk/` ATR 止损；上线 `roll report` CLI | `uv run roll report --format markdown` 输出完整的今日 0–100 晴雨表、建议总仓位及 3 只股票的止损位与财报灯；任一外部源临时失败时系统优雅降级不崩溃 |
| **Phase 3：6 年 Walk-Forward 回测与分箱校准** | 第 3 周 | 复用 `costs.py` 与 `statistics.py`，编写 `walk_forward.py` 跑通 2020–2026 历史回测；生成 5 分箱实证胜率/回撤表并写回晴雨表引擎 | 输出真实扣费后的净值与最大回撤对比报告；验证晴雨表高分区与低分区存在单调区分度，按实证结果微调 4 维权重并锁定 v2.0 参数 |
| **Phase 4：3 页前端收敛与 WorkBuddy 联调** | 第 4 周 | 重构精简 `api/`（14 接口）与 3 页 React 前端；编写 `scripts/start.ps1` 与 `scripts/roll-sync.ps1`；接通账本真实持仓并配置 WorkBuddy 调用 `roll report --format json` | 在 Windows 本机双击/单条命令即可启动 `http://127.0.0.1:8010`；一键同步 → 查看晴雨表 → 核对持仓止损 → 录入实际成交全链路跑通，端到端测试 1 份配置全绿 |
