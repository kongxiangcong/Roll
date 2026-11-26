# Roll v3 个股研究与盘后工作台

Roll 使用本地 SQLite 保存行情版本、研究档案、实验、账户和计划。CLI 和网页使用同一应用。缺省数据库文件为 Linux/macOS 的 `~/.local/share/roll/roll-v3.sqlite3` 或 Windows 的 `%LOCALAPPDATA%\Roll\roll-v3.sqlite3`。用 `ROLL_DATA_DIR` 或位置靠前的 `roll --data-dir DIR` 选择独立目录。

## 运行

需要 Python 3.12 或以上及 uv。从仓库根目录执行。

```sh
uv sync --project backend --locked
uv run --project backend --locked roll --help
uv run --project backend --locked roll serve
```

下文的 `roll` 指项目环境中的命令。也可以用 `uv run --project backend --locked roll` 执行。

## 同步与研究

```sh
roll market sync 600362.SH 000300.SH --start 2020-01-02
roll research sync-industry --start 2020-01-02
roll market import config/research/600362.SH/dividends.json
```

扶摇同步读取环境变量 `FUYAO_API_KEY`。可用 `ROLL_ENV_FILE` 指向本机配置文件。沪深 300 的扶摇缺口走公共指数补源。已有行情日期默认复用本地版本，`--refresh` 用来采集来源修订。申万同步使用系统 HTTPS 证书链，也可用 `--ca-file` 指定有效的 CA 文件。

用 `roll market freeze` 指定证券、区间、序列和用途，输出快照标识。以 `roll research export 600362.SH --snapshot ID` 获取冻结的多周期指标与覆盖。三种用途分别支持严格历史时点、显式假设下的历史重建，以及包含实际取得时间约束的日常运行。已冻结输出可离线读取。

用 `roll research draft` 导入 Markdown 草稿，核对后用 `roll research publish` 显式发布。样例、字段和发布命令见[研究档案](config/research/README.md)。公开行情及证据导出与账户录入相互独立。

## 账户与策略

用 `roll account init --help` 查看基线字段。基线现金、券商可用现金、批次和预算由用户填入本地 JSON。资金预算用 `roll account budget` 登记，仓位比例使用 0 至 1。用 `roll account fill` 和 `roll account correct` 记录已核对的券商成交及更正，重复提交保留原流水标识。每个账本由 `--book-id` 独立标识。

`roll strategy freeze` 登记江西铜业 20/60 日频趋势协议及冻结策略版本。协议规定开发与样本外区间、全现金和已有持仓的双基准口径、模拟费用及独立验收标准。结果保留实验与策略注册状态。
