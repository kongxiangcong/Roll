# Roll v2.1 个人盘后工作台

Roll 在 Windows 上按需运行。记账、日线、冻结日报共用本机 SQLite。缺省数据库为 `%LOCALAPPDATA%\Roll\v2\roll.sqlite3`；显式 `--data-dir` 指定该文件所在的目录。

## 安装与启动

本机需安装 uv 和 Node.js（含 npm），推荐 Python 3.13。无参数运行 `scripts/start.ps1` 会准备前端依赖、从当前源码构建静态页面，并在同一个回环服务中提供网页与 API。脚本可从其他目录用绝对路径运行。启动后打开 [本机工作台](http://127.0.0.1:8010)，在启动窗口按 Ctrl+C 停止。

```powershell
uv sync --project backend --locked --python 3.13
.\scripts\start.ps1
```

网页由三个按需读取的页面组成。

- **今日晴雨表**显示交易日总分、四维覆盖、仓位上限、同档成熟样本与行情缺口。可以同步全部或指定类型、冻结日报，并下载 JSON 或 Markdown。
- **持仓与跟踪池**显示实际仓位、个股上限、可卖量、行业相对收益、ATR 和财报灯。记账先预览再确认，并用回执核对余额与数量。跟踪池在 `config/watchlist.yaml` 编辑，下一次同步生效。
- **回测与校准**按所选区间比较 510300.SH 双组合扣费曲线与成本，分别列出历史四档复算和实际冻结的前向预测。

也可运行 `scripts/start.ps1 serve --port 8020` 更换端口。依赖已安装且 `frontend/dist` 已构建时，直接执行 `uv run --project backend --locked roll serve` 即可启动。需要另一份本地账本时，在命令前指定 `--data-dir DIR`，如 `scripts/start.ps1 --data-dir D:\RollData serve`。

## 首笔账户与成交

`account draft` 从标准输入读取 UTF-8 JSON，返回预览及草稿 ID。首次设置 BASELINE 时填写券商核对的初始现金及持仓。空账户可从零元开始，再录 CASH_IN 和 FILL。命令的 `expected_account_version` 取自最近一次 `account show`。资金、数量和价格使用十进制字符串。

```powershell
$initial = @{
    kind = 'BASELINE'
    expected_account_version = 0
    payload = @{
        source = '手工核对初始空账户'
        effective_at = '2025-08-01T09:00:00+08:00'
        cash_balance = '0.00'
        broker_available = $null
        broker_frozen = $null
        withdrawable = $null
        positions = @()
        permission_profile = @()
    }
}
$OutputEncoding = [Text.UTF8Encoding]::new($false)
$draft = $initial | ConvertTo-Json -Depth 5 | uv run --project backend --locked roll account draft | ConvertFrom-Json
uv run --project backend --locked roll account confirm $draft.draft_id opening
```

`account import-csv FILE` 预览 Roll CSV v1–v3；`account confirm DRAFT_ID KEY` 确认后返回回执，重试使用原键。`account reconcile RECEIPT_ID` 核对该回执对应的余额、成交、持仓。

## 行情与日报

日常从工作台点「同步数据」，或不带日期运行 `scripts/roll-sync.ps1`。空库默认取约 180 个自然日的扶摇日线以预热个股 MA / ATR（只选「股票与指数日线」也一样；显式起止日期不受该默认范围限制）；已有数据时补近期缺口，不让旧历史拖住日常同步。辅助输入空库从近 5 个自然日开始，旧库回拉不超过近 30 个自然日。启动和读日报不要求晴雨表已预热。

历史研究另用独立数据目录，按最多 93 个自然日的窗口逐段补库，重试跳过已有辅助输入。例如：

```powershell
.\scripts\start.ps1 --data-dir "$env:TEMP\roll-research" sync --backfill --start 2025-01-01 --end 2025-03-31
.\scripts\start.ps1 --data-dir "$env:TEMP\roll-research" backtest --start 2025-01-01 --end 2025-03-31
```

默认补沪深 300 指数、宽基 ETF 原始行情/份额/净值、沪深 A 股成交额和两融，可用重复的 `--group` 选择辅助输入（如 `--group turnover`）；不改跟踪池，不请求个股与财报。广度接口仅有当日快照，不能用于历史补齐；估值可显式选 `--group valuation`。窗口是请求范围，不是可用性承诺：回测期前还需要连续预热数据（资金维度最多需要 270 个交易日）。按缺口重试，不以代理指数成交额或缺项当零替代。沪市 ETF 份额遇超时时，先缩短窗口、单选 `--group etf_shares` 再试。`RequestBudgetExpired` 表示请求尚未发出，不等于来源没有该日数据。

扶摇通过环境变量 `FUYAO_API_KEY` 或仓库根目录的 `.env` 取凭证。`ROLL_ENV_FILE` 可以指定另一份配置。同步按标的记录实际覆盖区间、最近成功时间及失败原因；重读已保存的数据可以离线执行。

```powershell
.\scripts\roll-sync.ps1 --start 2025-05-06 --end 2025-08-01
.\scripts\start.ps1 prices 600362.SH --start 2025-05-06 --end 2025-08-01 --adjustment forward
.\scripts\start.ps1 report freeze 2025-08-01
.\scripts\start.ps1 report read 2025-08-01 --format markdown
```

第一次显式生成交易日报即保存其内容和截止时间。反复读取、再次冻结、同步和后续记账均保留这份历史结果。

将页面下载的 Markdown 或 JSON 文件交给 WorkBuddy 即可离线读取。也可在 PowerShell 7 将 CLI 导出存成 UTF-8 文件。两种格式保留首次冻结的 `cutoff_at` 和同一组账户、行情与风险结果。

```powershell
.\scripts\start.ps1 report read 2025-08-01 --format markdown | Set-Content -Encoding utf8 roll-2025-08-01.md
.\scripts\start.ps1 report read 2025-08-01 --format json | Set-Content -Encoding utf8 roll-2025-08-01.json
```

## 单 ETF 控仓回测

`uv run --project backend --locked roll backtest --start 2020-01-01 --end 2026-11-24` 使用本库原始行情比较晴雨表控仓与 510300.SH 买入持有。省略截止日期时使用最近可得的已收盘 ETF 交易日。2020–2023 定权期、2024 起的样本外期各从 100,000 元现金独立起算，每次交易按 100 份整手。对照在各段首日开盘买入。策略在段内首个有效档位或换档后的下一交易日开盘调整，同档或晴雨表缺数时继续持有。

两组合用原设计的模拟费率：双边佣金万三、每笔最低 5 元，双边过户模型参数十万分之一，510300.SH ETF 卖出印花税为零，单边滑点 5 个基点。成交价四舍五入至 0.001 元，各费用分项四舍五入至分。这组参数用于比较模拟结果。收益口径为原始价格变化减模拟成本，未计现金分红。全天单一价格触及前收盘上下 10% 时，模拟该方向无法成交。需要开盘成交却缺价时，后续账户轨迹列为未知；持有期间缺收盘时，该日净值与依赖完整曲线的指标留空。

年化收益按 252 个交易日折算，最大回撤从期初资金开始计算。卡玛为年化收益除以最大回撤，零回撤时留空。换手为区间双边成交额之和除以日均净资产。输出同时列出有效档位天数、逐日净值、成交及缺失行情，另列各维有效日和最长连续缺口。整个区间没有有效档位时明确标记数据不足；持现曲线不能作为有效控仓结果。

## v0 归档与架构

v2 从空账本启动，保留 Decimal 账户事件、交易日历、整手与 T+1 规则和历史重建的时点边界。v2 废止 ADR 0003 的 G1–G7、资格审批与资金授权门禁。旧实现及其契约可在本地归档分支 `archive/v0-legacy` 的提交 `eefe2c57` 复查。

[代码组织方案](docs/design/roll_v2_1_code_organization.md) · [v2.1 评审决定](docs/design/roll_v2_1_refactoring_spec.md)
