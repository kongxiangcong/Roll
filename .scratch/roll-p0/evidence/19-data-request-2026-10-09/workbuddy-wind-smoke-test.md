# WorkBuddy／万得只读小测试

请使用你当前已经连接并授权的万得金融数据能力，做一次小范围数据测试，不训练模型、不计算收益标签、不访问SEALED、不购买或开通新服务。

对象：江西铜业 A 股 `600362.SH`（Roll记为`SSE:600362`）。范围：`2020-06-01`至`2020-06-05`。

最多执行一次日线查询和一次相关字段／历史版本说明查询，输出真实结果，不改用其他来源补齐：

1. 不复权RAW的开、高、低、收、成交量；报告原单位，若换算成股给出明确依据，不能猜。没有记录原样报告。
2. 实际使用的万得连接器／工具名称、请求参数（不含凭据）、错误码、返回字段、查询接收时刻；能保留真实原始响应则作为附件返回，并计算实际SHA256。工具不支持原始响应导出就明确说明，不用自己重写的JSON冒充原体。
3. 说明返回的是今天查询的历史数据，还是具有可核验历史版本／as-of时点的档案。若支持历史版本，提供对应接口／字段说明、版本ID、修订链和原件；若不知道则写UNKNOWN。交易日期不能当作历史首次公开或接收时间。

请返回一个UTF-8 JSON对象，字段如下，未知填null并列limitations：

```json
{
  "test": "WORKBUDDY_WIND_READ_ONLY_SMOKE",
  "status": "NOT_RUN",
  "instrument": "600362.SH",
  "requested_from": "2020-06-01",
  "requested_to": "2020-06-05",
  "connector": null,
  "tool": null,
  "request_parameters": null,
  "received_at": null,
  "provider_error_code": null,
  "rows": [],
  "original_response_attachment": null,
  "original_response_sha256": null,
  "historical_version_evidence": null,
  "evidence_class": "UNKNOWN",
  "limitations": [],
  "training_performed": false,
  "sealed_read": false
}
```

实际status使用`SUCCEEDED / PARTIAL / FAILED / CONNECTOR_NOT_AVAILABLE`。rows每条包含`trade_date, open, high, low, close, adjustment, currency, reported_volume, reported_volume_unit, volume_shares, volume_conversion_basis, completion_state, publication_time, historical_version_id`。数值用十进制字符串，时间带时区，未知null。CURRENT_QUERY_ONLY不等于历史PIT合格；这次小测试只检查接口和字段，不宣布ticket19可以训练。

如无万得能力，直接报告连接器未连接／权限不足或实际错误，不虚构查询结果。
