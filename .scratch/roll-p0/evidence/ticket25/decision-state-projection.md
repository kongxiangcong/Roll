# DEC-01 / ID10 显式状态投影

独立审阅在旧source `4fc2403`确认：不可变input_archive保留gate输入，但Decision行缺少五项显式状态。本次source `e3a4a56`只投影已经计算/核验的状态，不新增数据查询、provider、资格gate或交易行为。原1934文件及旧immutable evaluations保持不变，新source使用fresh METHOD proof与隔离runtime。

## 公开值形状与来源

| 字段 | 保存值与来源 | 限定语义 |
| --- | --- | --- |
| account_status | 对应 `inputs.new_risk_check` 或 `inputs.reduction_check` 的 `{purpose,state,fact_scope_state,allowed,reasons}` | BUY为NEW_RISK，独立风险为REDUCTION；保留通用state与本用途fact_scope_state差异。REDUCTION事实通过不能推定现金/新增风险或购买权限通过 |
| data_status | `{state,namespace,reasons}`：profit opportunity既有用途时点、quote/daily completion/current status、规则/日历、价格/费用及估值缺口；risk calculate已经检查的quote/calendar/rule/current-status缺口及同一required_as_of绑定 | COMPLETE_CURRENT表示本次已检查用途的数据条件通过。METHOD_ENGINEERING namespace始终同时保存，只证明受控METHOD用途，不是实际市场来源authority/PIT验证。缺口为RESTRICTED，未覆盖/未计算为NOT_EVALUATED；时间/期限保留在现有行与依赖字段 |
| model_status | PROFIT_MODEL匹配自身当前profit grant、complete_protocol以及已绑定冻结model/deployment依赖；无匹配依据UNQUALIFIED，期限/研究namespace不在正式政策适用范围OUT_OF_SCOPE，受控METHOD为METHOD_ENGINEERING，符合真实受控grant时才为QUALIFIED | RISK_POLICY固定NOT_APPLICABLE。独立风险通过不改变收益模型状态，不取全局选中的风险grant作为收益资格 |
| execution_eligibility | 已有BUY排序/联合预算、规则、价格/费用和数量检查；风险已确认sellable、rule、price window/stress和executable_quantity及cutoff绑定 | 产生的METHOD Decision为METHOD_ONLY，真实当前Decision才为ELIGIBLE；refusal/不可卖风险facts为BLOCKED。没有券商订单/成交/入账推断 |
| capability_status | 对自身grant_id匹配 `inputs.capabilities.grant_statuses`，保存 `{state,grant_id,allowed_actions,system_usable}` | 直接保留METHOD_GRANTED/GRANTED，不造ACTIVE。没有可绑定grant时按范围记录UNGRANTED或RESTRICTED、grant_id=null、allowed_actions=[]、system_usable=false；不借全局selected grant放行 |

现有refusals及已计算holding_risks同样投影这些状态，便于后续消费者分列原因；仍是REFUSE/事实记录，不创建HOLD、WAIT或伪Decision。无risk packet时的持仓事实注明NOT_EVALUATED/NOT_APPLICABLE/BLOCKED。无任何action packet的基础Observation/持仓fallback继续是原客观事实，未补造资格结论。

## TDD 原件

- [profit red](state-red-profit.log)：1 FAIL/7.87秒，公共200股Decision缺account_status；[green](state-green-profit.log)：1 PASS/6.97秒。五字段literal，同时证明有METHOD收益依据但另一条因联合现金不足为BLOCKED，GET/replay保存一致。
- [risk red](state-red-risk.log)：4 FAIL/26.90秒，有可卖量的Decision缺model_status，可卖0事实缺execution_eligibility；[green](state-green-risk.log)：4 PASS/24.21秒。NOT_OPEN/UNKNOWN购买权限下REDUCTION事实独立通过，risk model NOT_APPLICABLE；可卖0仍decisions=[]、facts BLOCKED、自己的METHOD grant状态保持。
- 原无用户资金/生产重开用例追加UNQUALIFIED/UNGRANTED/BLOCKED公开字段断言；既有六个数据/期限硬失败追加RESTRICTED或OUT_OF_SCOPE分列断言。最终受影响API及组合结果另见acceptance，不把上述不同source阶段相加成同一次suite。

旧浏览器后端source保持历史标记，前端字节未变；当前后端使用公共API/组合/性能检查。父代理独立31 PASS/201.74秒、旧fresh benchmark .4603298秒是修复前源码记录，不升级为本次修复结果。
