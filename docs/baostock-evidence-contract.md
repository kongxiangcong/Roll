# BaoStock 原始依据与免费来源边界

## 接口与认证

票 19 通过现有 `POST /api/data/requests` / `retrieve` / 快照、原件、Parquet 和离线 replay 接入，无额外研究框架。范围仍受当前名单限制；本适配只查询沪深股票，不支持背景指数或全市场。

可指定 `daily_source=BAOSTOCK`、`status_source=BAOSTOCK`、`adjustment_source=BAOSTOCK`；新增 `CALENDAR` 事实组。请求 `DAILY` 与 BaoStock `STATUS` 时共享同一次日线查询。分红按起止年份逐年查询 `yearType=operate`，返回后按除权日裁剪；每个查询使用一个隔离进程，共用整次请求的总期限和调用/字节预算。

`baostock_auth_mode=API_KEY` 为默认：宿主从既有 `ROLL_ENV_FILE` / `.env` 加载 `BAOSTOCK_API_KEY`，官方 SDK `set_API_key` 后登录固定 `vip-api.baostock.com:10030`。缺密钥或登录/查询失败形成脱敏缺口，不自动换源、不重试。显式 `baostock_auth_mode=PUBLIC` 则使用官方匿名 `public-api.baostock.com:10030`；子进程移除所有 API key 等凭据，不接收 BaoStock 密钥。request、工具、原件均保留显式模式与来源地址。认证值不放到命令参数、请求档案、Prompt、日志或配置指纹中。两种访问方式不是历史时点或数据许可证明。

## 原件和运行限制

固定官方 PyPI `baostock==0.9.4`，SDK wheel SHA-256 `0bf71c6069ab5890ff3596632f9c3f8f1fbc6bfcac582c2f9d6a5c11ab2cfaf8`。以 BSD License 包依赖复用，未复制 SDK 源文件入生产代码；其 pandas 与 numpy 等依赖由 uv.lock 固定。SDK 许可证不构成证券数据商业再分发授权。

隔离子进程仅允许所选官方 host/10030，socket 调用包含登录和分页，无 SDK 自动重试；达到调用/接收字节/解压字节/总期限预算即失败。宿主检查取消并终止子进程，避免 SDK 阻塞。SDK 的全局连接不在宿主并发共享。运行记录保留实际 SDK、distribution 与 pandas 版本；实际服务接受性单独留证。

查询的实际 socket 接收字节以 `RAW_SOCKET_RESPONSE` 先于事实规范化归档；登录响应不归档，但其调用与接收字节计入预算。SDK 解码字段另存 `SDK_DECODED_RESPONSE`，通过 wire_hash / decoded_hash 关联，不能冒充原始 socket 响应。两份归档和适配代码均参与可追溯引用。接收时间为本次实际查询接收完成时间，不是原交易日的发布时间。任何原文、JSON 解码或压缩解码后的秘密反射在归档前拒绝。失败未能确认已完成的网络调用时，预算保守消耗剩余调用，明确 `CONSERVATIVE_FAILURE_UPPER_BOUND`，不把它当实际调用数。

## 字段和研究限制

- 日线明确 `frequency=d,adjustflag=3`，仅 RAW。价格和股数/人民币量额保留十进制原精度；核对对象、复权、重复日期、OHLC、均价范围和停牌非零量额。`preclose` 仅作供应商参考，除权时可能是除权参考价，不用于替代前一行 RAW close。当天完成状态仍未确认，不按计划 17:30 入库时间推定已完成。
- `tradestatus=1/0` 与 `isST=1/0` 原标记保留；STATUS 为 NORMAL_REPORTED / SUSPENDED_REPORTED / RISK_WARNING_REPORTED。它不证明全部交易限制、上市阶段、涨跌停价或当前除权状态，`historical_complete_status_verified=false`。历史日期状态不是当前实时状态，也不自动允许研究执行或正式交易。
- 日历按实际返回的自然日保留布尔 `is_trading_day`、DATE 精度。其范围是供应商 A 股日历，`official_exchange_calendar_verified=false`；不修改现有交易所规则与日历权威、不填历史规则有效版本。
- 分红保留实施公告、登记、除权、支付、红股上市日期、税前每股现金、每股送股和公积金转增比例；比例分列。日期仅 DATE，`published_at` 不强填午夜。登记日晚于除权日或支付日早于除权日拒绝规范化。没有披露分钟时点、完整配股条件或公司行为全集证明，空查询不是 CONFIRMED_NONE。税后描述仍在解码原件中，不解析成用户税款或到账事实。
- 所有来源保留 `PROVIDER_CURRENT_REVISION_NOT_PROVEN_POINT_IN_TIME`。当前下载不证明过去已知的版本，历史修订/as-of、完整特殊状态、公司行为全集、历史有效规则仍需另证。取数成功或一致性核对不会解除票 19 的 PIT、成熟标签、时间隔离、校准支持及封存独立性要求。

官方依据：[发行包](https://pypi.org/project/baostock/0.9.4/)、[日线](https://www.baostock.com/mainContent?file=stockKData.md)、[分红](https://www.baostock.com/mainContent?file=dividInfo.md)、[日历](https://www.baostock.com/mainContent?file=StockBasicInfoAPI.md)、[修订记录](https://www.baostock.com/mainContent?file=modifyRecord.md)、[免费平台说明](https://www.baostock.com/mainContent?file=home.md)。
