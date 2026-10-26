# 05 经营驱动、正常化与受控经济审核

日期：2026-10-27（Asia/Shanghai）。仅实施05；06及以后未实施。最终受影响回归94 passed、5 subtests passed（412.24s）；真实隔离恢复及离线重放PASS。开始时工作树为`D:/dsh-proj/Roll/.scratch/worktrees/rv-ticket05`，分支`codex/rv-ticket05`，基点为集成`c04b6ed824eceec577a1e87291491d48768dc63e`。原工作区生产源码和03真实store未修改。

## 交付与公共边界

- [入口/数据形状/数学及时序限定](../../../../docs/research/company-economic-review.md)：经营收入→EBIT→税→NOPAT→折旧/维持和扩张投资/营运资金→FCFF；逐数值来源和假设审核；不可变正常化、模型、policy source、审核及共享子快照。
- 原04结果永远保持unreviewed/usable_range=false；新review由宿主生成四态，不能接受requested_status或模型自签。所有假设缺逐项相关数值来源/经济理由则blocked；有据但有明确限制则conditional，全项检查完成且无遗留限制才reviewed。reviewed不是收益验证或正式资格。
- 终值检查再投资率×ROIC与g、末年ROIC和维护投资；首版限定稳定资本周转、年末投资支持下年初资本，不能把当年销售增长普遍等同当年再投资。12月31日锚点配下一完整年度，不插入未经支持stub。
- 金融NOT_APPLICABLE不执行FCFF、无valuation记录；周期/复杂集团缺资料保留blocked研究/诊断。分类使用业务/口径事实且继承冻结父链，不能把旧口径事实省略后改普通企业绕过。
- child snapshot复制03冻结核心并固定valuation/review/model引用，双用途一致；当前用途按真实读取时点及之后取得的财务披露另行阻断旧价格，不混入旧现金流或改写历史报告。

测试只在用户已确认的研究服务/API、计算器/备份恢复公共边界进行。实际CODEX模型、浏览器/报告/PDF、两个实际盘后周期不属于本票验收；本票不调用新模型或变更账户/ForecastBundle/Decision/CapabilityGrant/ExecutionIntent、原预算/SEALED。

## 真实正向案例：有日期边界的承德露露条件测算

[来源研究](source-research.md)、[逐数值/原件](source-data/)、[最终输入](real-lulu-command.json)、[经营底稿](real-lulu-operating-model.json)、[回执与双用途读取](real-lulu-receipt.json)分开保存。只按资料充分性选择这一家饮料制造企业，不按收益吸引力挑样本，没有全市场扫描。数据原件/事实/代理与研究假设保持区分；未知不补为事实。

最终合格记录由`run_real_cases.py`第08次新store运行产生；`real-case-command08.txt`为实际命令结果。2025年度报告SHA256为`8c620b0b2a555f37552f3310731dff808f11d43d150f3e7bb28264c65995306b`，2024报告为`2d6755a2dc375b190eb9afd1c800e4b98c3ec068c77beb6b19c70ca9703c2c40`。Q3发行人镜像PDF/指定媒体交叉核对、实际取得UTC及其余原件hash见source-data回执；不是历史PIT，也不把镜像说成已核同字节的巨潮原件。

- **估值锚点2025-12-31；完整现金流2026–2030。** 当前知识截止为2026-10-26 UTC（上海2026-10-27，精确带时区值见回执/快照），不是2025年已知资料。WACC输入观察期另列：2025国债/市值/借款、2026年1月作者ERP/行业beta，事后取得并使用的条件测算不声称当时公允价值。
- 合并收入3,173,554,539.83元，报表营业利润832,768,950.67元，派生core profit802,208,126.13元（收入−成本−税附−销管研，排除财务、其他收益及减值）。显式正常化到2024同定义margin或22%研究压力情景；保存每年调整前/后/差额/公式/理由。没有将集团利润除局部吨数。
- 稳态假设：量/价/组合平基准；税25%；维护及资本化租赁续期投资=完整D&A47,326,934.25元；增长投资和Δ经营NWC均0。实际capex184,906,387.79元和CFO1,012,283,571.60元保留比较；2025营运资金现金释放276,916,417.60元不被永续化。两情景年度FCFF分别598,878,150.9892349和523,636,499.07194996元，均为附条件宿主推算，不是披露预测。
- 现金4,032,137,003.56元中关联财务公司存款3,123,918,306.63元。仅加回扣除季度经营费用代理保留额后的假定可收回超额现金；该代理含非现金费用，不能称实际现金成本。利息收益已从经营利润剔除，关联存款不在其他资产重复加回。现金回收和保留额为有据但未独立信用评估的条件。
- WACC有息D=银行+租赁592,328,455.05元；E为provider舍入约86.7亿元，wE≈0.9360497247、wD≈0.0639502753。行业现金校正unlevered beta0.54按`0.54*(1+0.75*D/E)`重加杠杆为0.5676693223，不称公司实测beta。RF采用2025-12-31中债10Y国债1.8473%基准代理；China totalERP5.14%已含country0.91%，不重复加；历史保证借款2.99%、25%税盾代理，WACC≈4.60379805%。跨市场行业代理、政府债风险率约定、共同country暴露、舍入E和账面D局限逐路径保存，不以公司经验事实冒充。
- 权益桥另扣回购义务44,520,000和已确认工程应付81,382,374.46元，不将它们放入WACC有息债或经营NWC，不再扣库存股/净股数。NCI由时点归母/全部权益差额推算0；非现金投资账面残差与联营全减值有原件，保守不加回经济恢复值仍是研究假设。p155明确无需要披露重要承诺；不据此宣称未来投资为0，也不用预算−CIP伪造合同义务。

**最终经济审核为conditional，仅BASELINE_RESEARCH可展示条件测算。CURRENT_PRICING为blocked且scenarios为空。** 已取得的2026Q3现金、新金融资产、YTD CFO、项目与后续注销股数，使2025现金/股份桥不能称当前；未完成当前银行/租赁拆分、投资资产与资本计划等调节，缺口不通过宽泛conditional消除。05通过的是A6的有据日期基准估值部分；完整报告、当前定价链和联合A6/A7/A8仍留后票，不能拿本票替代。

## 江西铜业负例

[实际回执](real-jcc-negative.json)使用03已归档2025中国准则HKEX原件，SHA256`4493c7646001766896e6d4e3b97c702e9ee69423a86f8932df79e29bb75d5303`；只读03store的原件字节，另建本票store。准确复用10项原文口径，不重新调用模型。

数值输入明确是**symbolic METHOD gate test，不是江西铜业财务数字/预测/真实估值**。即使调用者写普通非金融且算术可完成，实际铜/LME/工业/贸易/金融/权益产量口径证据仍触发周期/分部闸门；两个检查均BLOCKED、无可用价格，不能把两年均值当完整周期。不能把这一拒绝用例当正向真实财务估值；正向另由露露独立验收。

## 红绿、失败与修正

`redNN.txt/greenNN.txt`保留真实输出，后续增强另留review/scope记录。各轮先观察公共行为缺失/失败再实现；已实现边界的补充回归没有冒称red。

| 切片 | 观察与结果 |
| --- | --- |
| 01 | red缺OperatingValuationCommand；green首次暴露规范归档元字段遗漏，green01b通过 |
| 02 | red正常化被忽略；green02三项通过，保留before/delta/after和重复目标拒绝 |
| 03 | red经济ID伪装重复和terminal ROIC不匹配仍conditional；green03通过 |
| 04 | red普通标签/字符串cycle/segment误放行；green04通过，后来独立scope事实/省略父事实另做回归 |
| 05 | sandbox TestClient无输出挂起，CIM仅定位并停止两个确认的rv05-red05进程；相同边界sandbox外red05b404，green05 API/恢复通过。未把空日志当结果 |
| 06 | red原始unreviewed值缺safe view；green06隐藏价格并拒绝调用者自签 |
| 07 | red量价growth路径单位不识别；green07年末投资50→下年资本550→收入1100→FCFF110、独立手算EV1000通过 |
| 08 | red无时间依据仍作当前可用价格；green08拒绝并保留研究 |
| 09 | red金融分类仍产生FCFF valuation；green09只保留NOT_APPLICABLE方法/研究 |
| 10 | red业务文本被当数值折现率来源；green10逐值匹配RF/debt/tax与日期 |
| 11 | red缺逐项假设理由仍conditional；green11阻断，相关数值来源角色+逐路径理由/限制成为必要门 |
| 12 | red旧metadata日期错误保鲜；green12按实际read-time及新披露阻断；旧snapshot不变。原scope测试因冲突头补入本已拒绝，随后改成独立事实序列验证祖先上下文，记录scope-regression，不伪称它是red12失败项 |
| 13 | red缺价值锚点还可用；green13缺时间依据只能blocked诊断，股份/桥/基准收入日期须匹配来源期末 |

第01–03次真实脚本分别暴露缺content参数、超过03的96KiB上限、股数来源时点不匹配，失败日志完整保留；仅修正脚本/缩小所选事实/匹配真实口径，没有放宽03/04规则。第04/05次开发结果错误地将未完成逐项经济审核放为conditional；`attempt05-incomplete-audit/`明确保留为缺陷证据，绝非合格正向案例。新policy2与新store/记录重新验收，旧记录未改写；safe view拒绝旧policy1价格。第06/07为逐步完成来源/时点元数据的受限正向开发记录，最终第08记录绑定最终方法source hash。

## 重放和恢复

[实际隔离恢复](real-recovery.json)验证最终real model/review/snapshot全部引用/hash、DAILY/REPORT一致、原04离线算术重放、policy原文hash、账户version0，以及legacy错误conditional的价格被隐藏；network/model均0。首次验证脚本Ledger未将str转Path，失败保留为`real-recovery-command.txt`，修正后`real-recovery-command02.txt`通过。

从本工作树根目录，以现有Python或兼容解释器执行（每次用新空目录）：

```powershell
$env:PYTHONPATH='backend/src'
& D:/dsh-proj/Roll/backend/.venv/Scripts/python.exe .scratch/roll-research-valuation/evidence/05/run_real_cases.py --data-directory <new-real-store> --output .scratch/roll-research-valuation/evidence/05/real-lulu-receipt.json
& D:/dsh-proj/Roll/backend/.venv/Scripts/python.exe .scratch/roll-research-valuation/evidence/05/run_jcc_negative.py --data-directory <new-negative-store> --source-data-directory <02-or-03-store-or-restored-backup> --output <negative-receipt.json>
& D:/dsh-proj/Roll/backend/.venv/Scripts/python.exe .scratch/roll-research-valuation/evidence/05/verify_saved_cases.py --restore-directory <new-restore-store> --output <recovery-receipt.json>
```

正向资料均已冻结在repo，生产不依赖开发者外部研究目录；负例原件从02/03公共归档或其恢复副本读取。新建记录是新版本，不伪装旧ID重现；旧计算通过原04 replay确定性重放。

最终方法policy SHA256为`36482c5b98acbcfa8fb36b88ed42cd97bf9e69106b662e1b73fa401bb854a09f`，经济policy为2，原始/适配04算法与MIT来源冻结未修改。10份实际公开原件hash检查、01的27文件/94闸门冻结检查、compileall及Git blob核验分别记账，不把它们当真实模型/浏览器/预测提升证据。

最终回归命令：`python -m pytest -c backend/pyproject.toml backend/tests/company_research backend/tests/application/test_backups.py backend/tests/test_assistance.py -q --basetemp=<new-isolated-directory>`；实际原输出见`final-regression.txt`。01冻结27/94 PASS；compileall退出0；git diff --check通过。没有运行整仓测试、真实新CODEX、浏览器/PDF或实际盘后周期；没有将这些未运行项写成通过。

10份原件已在stage后通过Git blob重新核验，见`git-source-blob-verification.json`，不是只检查工作区文件。原件/失败输出精确-text属性已限定05路径，现有.gitattributes原字节保留。05 Completion complete；整体spec仍in-progress，下一票06。

首次staged diff检查发现下载HTML自带space-before-tab和新说明的CRLF；原HTML未改字节，仅精确关闭该原件路径的对应whitespace提示；仅新写说明规范LF后重检。
