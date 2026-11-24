# Roll v2.1 个人盘后工作台

Roll 在 Windows 上按需运行。记账、日线、冻结日报共用本机 SQLite。缺省数据库为 `%LOCALAPPDATA%\Roll\v2\roll.sqlite3`；显式 `--data-dir` 指定该文件所在的目录。

## 安装与启动

在仓库根目录运行以下 PowerShell 命令。需安装 uv，建议使用 Python 3.13。

```powershell
uv sync --project backend --locked --python 3.13
uv run --project backend --locked roll --help
.\scripts\start.ps1 account show
```

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

扶摇通过环境变量 `FUYAO_API_KEY` 或仓库根目录的 `.env` 取凭证。`ROLL_ENV_FILE` 可以指定另一份配置。同步按标的记录实际覆盖区间、最近成功时间及失败原因；重读已保存的数据可以离线执行。

```powershell
.\scripts\roll-sync.ps1 --start 2025-05-06 --end 2025-08-01
.\scripts\start.ps1 prices 600362.SH --start 2025-05-06 --end 2025-08-01 --adjustment forward
.\scripts\start.ps1 report freeze 2025-08-01
.\scripts\start.ps1 report read 2025-08-01 --format markdown
```

第一次显式生成交易日报即保存其内容和截止时间。反复读取、再次冻结、同步和后续记账均保留这份历史结果。

## 单 ETF 控仓回测

`uv run --project backend --locked roll backtest --start 2020-01-01 --end 2026-11-24` 使用本库原始行情比较晴雨表控仓与 510300.SH 买入持有。省略截止日期时使用最近可得的已收盘 ETF 交易日。2020–2023 定权期、2024 起的样本外期各从 100,000 元现金独立起算，每次交易按 100 份整手。对照在各段首日开盘买入。策略在段内首个有效档位或换档后的下一交易日开盘调整，同档或晴雨表缺数时继续持有。

两组合用原设计的模拟费率：双边佣金万三、每笔最低 5 元，双边过户模型参数十万分之一，卖出税费模型参数万分之五，单边滑点 5 个基点。成交价四舍五入至 0.001 元，各费用分项四舍五入至分。这组参数用于比较模拟结果。收益口径为原始价格变化减模拟成本，未计现金分红。全天单一价格触及前收盘上下 10% 时，模拟该方向无法成交。需要开盘成交却缺价时，后续账户轨迹列为未知；持有期间缺收盘时，该日净值与依赖完整曲线的指标留空。

年化收益按 252 个交易日折算，最大回撤从期初资金开始计算。卡玛为年化收益除以最大回撤，零回撤时留空。换手为区间双边成交额之和除以日均净资产。输出同时列出有效档位天数、逐日净值、成交及缺失行情，整个区间没有有效档位时注明策略保持现金。

## v0 归档与架构

v2 从空账本启动，保留 Decimal 账户事件、交易日历、整手与 T+1 规则和历史重建的时点边界。v2 废止 ADR 0003 的 G1–G7、资格审批与资金授权门禁。旧实现及其契约可在本地归档分支 `archive/v0-legacy` 的提交 `eefe2c57` 复查。

[代码组织方案](docs/design/roll_v2_1_code_organization.md) · [v2.1 评审决定](docs/design/roll_v2_1_refactoring_spec.md)
