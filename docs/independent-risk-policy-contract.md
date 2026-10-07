# 独立风险政策与资格边界

22 注册一个 `AUTHORIZED_EXPOSURE_CAP_V1`，使用17协议、全部确定性检查尝试及独立审计。政策冻结具体依据、ACCOUNT适用域、已有10资金授权版本/起点、明确证券身份、06规则来源与版本、数量算法、恢复限制、代码及计算依赖指纹。先可靠归档原件，再通过SQLite短事务引用；不写账户、意向、正式动作或CapabilityGrant。注册和检查成功不表示门槛PASS。

## 公开接口

- `POST/GET /api/research/protocols/{id}/risk-policies`：登记/列出不可变政策。请求仅`basis`，不要求新用户金额或统计参数。
- `GET /api/research/risk-policies/{id}`：冻结依据和原件SHA。
- `POST/GET /api/research/risk-policies/{id}/evaluations`：新增/列出检查；请求`basis`、带时区且不晚于现在的`required_as_of`，可选同账户版本/同截止09 `valuation_id`。
- `GET /api/research/risk-evaluations/{id}`：原检查结果；`POST /.../{id}/replay`：校验原输入及QUOTE原件SHA，0联网重算并登记一致性，不替换历史检查。
- `GET /api/research/risk-policies/{id}/validation`：独立DATA、RULE_QUANTITY、AUTHORIZATION、STRESS_EXECUTION、ONLINE_CONSISTENCY门槛。原检查只保存当时结果，重放门槛另由同检查ID/输入SHA审计产生；账户或授权版本改变会限制当前结论。

价格采用同沪深交易日已完成15:00原价收盘/CNY报价，原`available_at`不晚于检查自己的`consumer_knowledge_cutoff`，源时点不晚于观察截止。今天取得的历史收盘仅ACCOUNT_CONDITIONAL研究诊断，不能当过去已知或当前可执行价格。未读取完整封存日线、标签或策略结果；SQLite备份及opaque原件复制只是工程保全。

## 触发与数量

单票和总暴露分别取冻结授权与当前授权`single_exposure`/`total_exposure`的较小值；不会把单笔损失预算当单票上限。按明确证券标识排序，在已知组合市值时结合其它已知市值，寻找降到授权边界的最小数量。研究可行减量向上取100股，再与新鲜明确可卖量相交；受限可卖量只能完整100股，整笔小于100股余量按已归档规则处理。确认数量和可卖量来自账本，不用T+1猜可卖量。部分可卖导致残余风险，页面和结果明确显示。

适用范围仅明确身份的SSE/SZSE MAIN普通A股，当前适配规则ID必须与冻结版本相同、日历明确开市、证券状态明确NORMAL。不将普通案例外推STAR/创业板/北交所、特殊状态或未知规则。持仓在政策范围外仍可见，不产生该政策数量。总市值缺失时只允许独立已知单票上限分支，总暴露分支留未知；其余未知不补0。

现金/费用待核形成总体UPDATE_PENDING/RECONCILE，不阻断已独立确认、新鲜的数量/可卖量REDUCTION事实；未决成交、数量变化、权益事项或数量声明不足仍阻断。这是ACC14的具体事实边界，不能绕过所需亏损事实。09损失只能消费严格同范围/版本/截止的可信LossFacts，保留历史峰值/暂停；缺基线或组成字段仍RESTRICTED。已知损失暂停没有本政策的默认清仓算法，未知损失也不变持有/观望/全卖。

## 压力及恢复

参考原价上下按适用普通日幅度和价格刻度计算跳空边界；剩余市值可能重新超额。跌停不成交、停牌、再延迟一交易日均保存0成交/风险未释放；未来价格及市值未知而非0。另保存50%数量按合法整手取值的压力。它们是确定性压力方向，不是未来成交或最大亏损保证。

工程PASS表示当前研究数量能计算；实际验证必须独立满足全部门槛，已知撤权为FAIL，缺项为INCONCLUSIVE。METHOD报价/合成账户授权不会升级真实DATA/AUTH门槛，重启也保持METHOD；实际当前没有用户授权，仍INCONCLUSIVE。收益模型停用不自动撤销独立政策证据，但22未签资格，24需受控复核指纹、范围、当前事实及失效条件，25才验正式正向动作链。旧检查可以离线重放，不能当现在可执行；政策或依赖代码版本不同拒绝冒充原版本重放。反弹、扩大授权及旧重放不自动恢复资格，27负责受控恢复。收益G3/G4/G7不因政策工程结果获豁免。

原规则来源沿用[06契约](market-contract.md)及06沪深2026规则/日历归档，资金与损失口径分别沿[10](funding-contract.md)和[09](valuation-contract.md)。本票没有额外模型调用或依赖。[验收及保全](../.scratch/roll-p0/evidence/22/acceptance.md)分开列实际不足和METHOD证据。
