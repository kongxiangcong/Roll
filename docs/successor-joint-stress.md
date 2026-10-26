# 同场景候选与原基准压力

在保存费用诊断下，选择同前缀的原基准与入场压力记录，运行12个固定配对场景：六入场、六费用，每个同时报告候选及CASH、START_HOLD、MA5_MA20。严格核对费用id、manifest/input、后继/协议及适配行情hash；不重拟合或搜索场景。

原基准仍调用未改的shadow引擎：START_HOLD不自动退出，MA期限从观察算起；候选采用已保存v2结果，新lot期限从实际入场算起。行情不改字段或移日期，完整声明位置不压缩。MA无前置上下文、未知/拒绝执行支持和基准风险越界均明确使比较不合格；不裁热身，也不将基准越界制造为候选统计失败。

完整窗口可计算且支持可准入时仅显示描述性收益差值。共享场景不等于共同风险或独立区间，risk_matched=false；保留候选已知硬失败，否则G5 INCONCLUSIVE，无PASS。费用场景缺完整暴露历史、早退/到期压力等局限保留。

原件、输入、方法和代码指纹不可变保存；禁网worker30秒、输入/输出8MiB、最多200声明跨度。嵌套原件损坏拒绝，后来帧不改变旧重放。API：`POST/GET /api/research/successor-cost-stresses/{id}/joint-stress`、`GET /api/research/successor-joint-stresses/{id}`、`POST /api/research/successor-joint-stresses/{id}/replay`。
