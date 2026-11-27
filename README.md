# Roll v3 个股研究与盘后工作台

Roll 使用本地 SQLite 保存行情版本、研究档案、实验、账户和计划。CLI 和网页使用同一应用。缺省数据库文件为 Linux/macOS 的 `~/.local/share/roll/roll-v3.sqlite3` 或 Windows 的 `%LOCALAPPDATA%\Roll\roll-v3.sqlite3`。用 `ROLL_DATA_DIR` 或位置靠前的 `roll --data-dir DIR` 选择独立目录。

## 运行

需要 Python 3.12 或以上及 uv。从仓库根目录执行。

```sh
uv sync --project backend --locked
uv run --project backend --locked roll --help
uv run --project backend --locked roll serve
```

浏览器打开本机回环地址。Windows 也可运行 `scripts/start.ps1`。 [本地工作台](http://127.0.0.1:8765)

下文的 `roll` 指项目环境中的命令。也可以用 `uv run --project backend --locked roll` 执行。

## 同步与研究

```sh
roll market sync 600362.SH 000300.SH 512400.SH --start 2020-01-02
roll research sync-industry --start 2020-01-02
roll market import config/research/600362.SH/dividends.json
roll market import config/research/600362.SH/2026q3-cashflow-observation.json
```

扶摇同步读取环境变量 `FUYAO_API_KEY`。可用 `ROLL_ENV_FILE` 指向本机配置文件。沪深 300 的扶摇缺口走公共指数补源，512400.SH 同步公共原价。已有行情日期默认复用本地版本，`--refresh` 用来采集来源修订。申万同步使用系统 HTTPS 证书链，也可用 `--ca-file` 指定有效的 CA 文件。

用 `roll market freeze` 指定证券、区间、序列和用途，输出快照标识。以 `roll research export 600362.SH --snapshot ID` 获取冻结的多周期指标与覆盖。三种用途分别支持严格历史时点、显式假设下的历史重建，以及包含实际取得时间约束的日常运行。已冻结输出可离线读取。

用 `roll research draft` 导入 Markdown 草稿，核对后用 `roll research publish` 显式发布。样例、字段和发布命令见[研究档案](config/research/README.md)。公开行情及证据导出与账户录入相互独立。

## 账户与策略

用 `roll account init --help` 查看基线字段。基线现金、券商可用现金、批次和预算由用户填入本地 JSON。建立独立模拟账本时在基线中设置 `"simulated": true`。资金预算用 `roll account budget` 登记，仓位比例使用 0 至 1。用 `roll account fill` 和 `roll account correct` 记录已核对的券商成交及更正，重复提交保留原流水标识。每个账本由 `--book-id` 独立标识。

`roll strategy freeze` 登记江西铜业 20/60 日频趋势协议及冻结策略版本。协议规定开发与样本外区间、全现金和已有持仓的双基准口径、模拟费用及独立验收标准。运行 `roll experiment run VERSION SNAPSHOT` 保存实验。用 `roll experiment show RUN_ID --trace` 查看完整逐日账本，用 `roll experiment verify RUN_ID` 离线重建并核对结果标识。

用 `roll experiment robustness RUN_ID --parameters 15 60 --parameters 20 80` 在冻结实验的开发窗口比较参数、双倍可控成本和市场状态。结果引用原实验，保留其既有样本外验收和准入记录。

## 盘后计划与预留

`roll plan` 根据当前已取得的行情、已发布的研究、策略注册状态及账户预算，冻结下一交易日的唯一方案。用 `--preview` 先看候选及 P0–P4 理由，用 `--plan-id ID` 重读任意已发布版本。

`roll commitments show` 核对剩余预留和当前可分配现金。单日预留到目标交易日收盘自动释放。用 `roll commitments condition` 登记跨日条件，用 `roll commitments order` 登记券商未决、撤单或失效。成交金额以 `roll account fill` 录入的实际含费值为准。已从券商可用余额扣除的本笔冻结款填入 `broker_frozen`，并录入券商确认的可用余额。后续成交可用 `broker_order_id` 关联委托。

## 前向复盘

盘后用 `roll review register` 在同一次登记中冻结正式方案和独立影子方案。可用 `--strategy-version VERSION --price-only` 指定已冻结的量价候选供影子账户运行。用 `roll review settle REGISTRATION_ID` 结算已到期的影子方案，随后用 `roll review show REGISTRATION_ID` 对照原计划、模拟结果及实际执行。

实际确认、拒绝和未执行原因通过 `roll review outcome` 追加。已成交时输入券商核对的流水，可用 `--plan-id` 指定同一交易时段的计划版本。带证据的偏差可用 `roll review finding` 提交复核，并将已触发的证伪条件关联到当时档案。

为真实前向的开盘撮合准备 `daily_open` 行情观察。以 `market import` 录入原始开盘、参考昨收、交易状态、来源、实际取得时间及可得证据。使用开盘后才取得的历史日线投影时，应选择重建用途。缺少及时的开盘证据会留下具体的未成交原因。用 `review list --start DATE --end DATE` 检查按交易所日历漏登的日期，`--mode rehearsal` 和 `--mode reconstructed` 的记录单独留存。

[工程验收与实测记录](.scratch/roll-v3-trading-pipeline/acceptance.md)

`roll forward-window audit` 按交易所日历核对连续 20 个真实盘后登记日，列出待执行、已结算及异常。可以传入 `--start DATE --end DATE` 核对指定区间。窗口齐备后用 `roll forward-window signoff` 冻结验收回执，并用 `roll forward-window show SIGNOFF_ID` 重读。

策略的独立前向评估用 `roll strategy forward-result VERSION SIGNOFF_ID VERDICT` 登记，要求该版本的真实影子结果已结算。历史验收及前向评估均通过后，用 `roll strategy admit VERSION` 显式发布准入。
