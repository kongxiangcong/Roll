# 搜狐历史日线契约

`daily_source=SOHU` 是显式公共来源，不需要凭据，不调用扶摇或 BaoStock。仅发出一个证券、一个日期区间的 `GET https://q.stock.sohu.com/hisHq`，固定 `code=cn_<code>&start=YYYYMMDD&end=YYYYMMDD&stat=1&order=D&period=d`。沿用 DataRequest 账户/名单范围检查、调用/响应大小/时间限制、可靠原件先归档、Parquet/SQLite 发布、重启和零联网重放；不自动换源、分页、复权或补值。背景指数不适配，BSE保留明确缺口。

2026-10-09 核对[供应商历史页](https://q.stock.sohu.com/cn/600362/lshq.shtml)与其[历史查询脚本](https://static.k.sohu.com/static/finance/pc/qstock/v0.0.10/js/main/hq_sec-1.4.min.js?202607090945)。GBK脚本调用上述参数，将 `hq` 各列直接放入同序表格；页面标签依次为日期、开盘、收盘、涨跌额、涨跌幅、最低、最高、成交量(手)、成交金额(万)、换手率，可选盘后量(手)。页面SHA256 `2bb1545bebd5b5fd6b42ca188c01f102288e4d548c083ab9120535c4335202f4`，脚本SHA256 `8c57fcfd2fda59415f77a0bdfb683c68c3f568fb33eb6392bddaaf4b004ead35`。

量额按Decimal保留原字符串；成交金额万元 ×10000，并保留供应商100元精度。仅已确认SSE MAIN普通STOCK将成交手数 ×100转股，其他身份保留报告手数/UNKNOWN股数。金额/股数须与RAW高低范围核对，允许供应商金额舍入误差（100元/股数）及一分价格精度。异常OHLC、占位、缺失、量额不一致、未知日历和当日未确认均限制模型日线输入。零报告不推定停牌。行宽、对象、业务状态、日期边界/重复及数字语法/长度在外部结果边界校验；异常原文仍归档，指令文本不执行。

保存当前供应商RAW历史版本，不请求或派生前复权，不声称原件无修订。实际 received_at/available_at 不回填历史，原cutoff的PIT检查保留。只新增DAILY，不能由价格/无行推断正常交易、完整公司行为或完整日历。历史页显示每次最多100条，但实际单请求返回3126行；覆盖使用实际返回数量/首末日期，不承诺全历史完整性，也不将缺行填作正常交易。

宿主研究登记仍为HISTORICAL、窗口NOT_PREREGISTERED、历史PIT/公司行为/状态/规则/封存独立性不足；禁止计算封存标签或签发资格。真实现场归档数量、原件与重启/重放证据由19实际验收分别记录。公开可达不证明商业再分发许可。
