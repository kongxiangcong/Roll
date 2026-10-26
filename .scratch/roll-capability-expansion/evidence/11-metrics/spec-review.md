# Ticket 11 — Spec review

相对 `9910bcd`，只读审查财务指标、共享 listing/joined 增量与 API/UI/测试；未运行测试或联网。依据 [ticket 11](../../issues/11-financial-metrics.md) 与 [spec ID-07](../../spec.md)，定向复核后开放 0 项。

**P2 已关闭：营业收入口径。** 毛利率及净利率现专用已存 `OPERATE_INCOME`，新增 operating_revenue 指标及出处，不再用 TOTAL_OPERATE_INCOME 兜底。营业收入缺失或与当前发行人已核验收入锚冲突时保守 UNKNOWN；原总营收指标保持独立。`margin-red.log` 保留原失败，`margin-green.log` 4 PASS/32.43s；新增公开回归覆盖营业收入缺失/冲突，以及母公司金额或万元金额未获语义证明时不生成可比指标。本复核只读代码和结果，未重跑。

其他已检查行为符合边界：季度保留同年累计差分、缺前期未知，TTM要求四连续可比季度；同比负/零基期不算比例而保留绝对变化。集团经营现金匹配集团净利润，零负分母拒绝。来源事实ID、版本与原件引用可展开；截至时间选择不可变旧事实，不倒填后修订。

joined 已统一 known_by，并仅当前查询保留补充采集 active IDs，未把历史查询变为当前活动视图。先前 `api-final.log` 为6 PASS/45.91s；浏览器因定位多处公式的失败与最终修正结果须分别保留，不预称最新源码浏览器已通过。11消费10已保存 REAL 工件，不要求新增HTTP；METHOD反例证明未验证母公司/万元输入拒算，不外推为已接通新的真实母公司报表或单位换算来源。

最终日志已只读核对：`browser-final.log` 1 PASS/13.4s，默认真实应用读取10既有归档，0 collect，验证公式/源版本链接、刷新与390px；`zero-final.log` 1 PASS/11.02s 补零同比基期及旧截止不变；`build-final.log` TypeScript/Vite通过。`acceptance.md` 明确保留原浏览器定位失败、各批次成功范围、母公司/万元仅拒绝证明，以及非历史PIT/非资格边界。最终开放0，无需再取数；未运行任何测试。
