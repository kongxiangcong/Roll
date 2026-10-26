# 03 状态文档尝试 STATUS-DOC-ATTEMPT-01

2026-10-18 独立登记、零隐含重试，仅取两份官方静态脚本（非行情查询）：

- [search_HQ_2021.js](https://www.sse.com.cn/xhtml/home/2021public/querySearch/search_HQ_2021.js)：160,211 字节，SHA256 `e2c944248245259c646f54014920795e8dff32b83ddf1d2b6f64dc465c243d96`。
- [sse_full.js](https://www.sse.com.cn/xhtml/js/sse_full.js?v=3.8.1_20260901)：377,125 字节，SHA256 `7a8a29c5c6a1074c60302109db9fb3a92eb3a67171b8beadd3e1ec87514c781c`。

核对结果：search_HQ 的公司页行情 select 含 `tradephase`、`fp_phase`，并调用 `kcbShowIconFlag`，但两份脚本都没有该函数与 `STATUS_A`/`getFpphaseText` 的定义。因此全状态枚举/风险子类型/生效时点仍无官方映射依据，不能据此扩充 03 的否定覆盖。

本次未调用行情端点、未生成来源回执、未重开任何 CLOSED 预算。下一文档线索为官方 `sse_menufun_2021.js` 或状态专用模块；需另登记固定计划。03 维持 partial。
