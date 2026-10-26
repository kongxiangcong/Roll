# 13 工程标准审查

- 边界：观察层只读事实/指标/解析表，无来源调用、无 LLM、无外部服务；API 走公开查询，浏览器只读。
- 一致性：金额/百分比沿用 Decimal 字符串，不由浮点反写；趋势与文字使用同一 `metrics` 输出。
- 持久化：`financial_observations` 以输入摘要唯一，INSERT 后重读，旧行不 UPDATE/DELETE；历史读取按 id。
- 失败隔离：无事实返回 MISSING 而非默认值；未知指标进入 gaps；禁用财务源不影响已保存观察。
- 前端：折叠区、语义状态 role=status、无 dangerouslySetInnerHTML；移动宽度验证。
- 审查修复：当前查询摘要含时间导致版本膨胀，已改哨兵；真实解析中断保留为 INTERRUPTED。
- 开放风险：120 天阈值需随披露季节复核；观察文本模板需避免被误读为投资建议（已固定免责声明）。
