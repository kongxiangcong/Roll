# 08真实章节抽样语义核对（两条指定记录）

范围：只读root指定本地API8028的两个GET章节记录、preview-08.2/command-1.json与packet51facts/core，并读取首章已登记原始model-output文件。未触发新任务/模型，没有POST、服务启停、DB写或08源码编辑。首次沙盒两个GET均WinError10013，随后获准只读GET成功；这里只取得已有结果，不是新的来源/模型运行。

## 实际取得与样本边界

| 章节/记录 | 实际状态 | 取得回执与语义范围 |
|---|---|---|
| 1：e607d506-cae1-4cfa-ad54-16b79a47a608 | COMPLETE / REAL_MODEL_CHAPTER，model gpt-6.1-sol | 2026-10-26T22:32:30.319709+00:00；GET200；7566 bytes；response SHA256`56300332cd8ab480e95a7a92eb737716b9613e5cb92a2dcd9eac5b42c43924a1`。检查其6个原输出paragraphs及宿主rendered和gaps。 |
| 2：40ce7c77-40b8-43dc-b5bd-3ad8aa178f17 | **FAILED / REAL_MODEL_ATTEMPT** | 2026-10-26T22:32:30.345859+00:00；GET200；1903 bytes；SHA256`25ee92a966d423af721ec1ed968d403949aabf6a7d8d9d8f305116b10d681b0d`。正文仅失败占位，**本章语义审查留空**；不把候选gaps或保存原输出等于已完成写作。 |

本地审计副本同目录`rv08-sampled-section-<上述ID>.json`，回执`rv08-sampled-section-receipts.json`。首章input_sha=`bdb2252f4f9aab4d24dfbd8b98d17a50dc603c579ee3092bd5a9ea59c2b6a77e`；command archive SHA=`f2ef23e397b21877e089760bb14d74c0288ac4bd878e55d843e845359096f976`，与preview首章实际字节相同。9个reference_ids都在51facts里，未见未知引用。

首章原始JSON输出只读自`D:/dsh-proj/Roll/.scratch/rv08-real02/raw/884788af372232002368d357983ac9722825b9c9a380cb69ddf568b1084cb6ac.raw`，4871 bytes，实际SHA与登记匹配。未读取授权文件、账户或其他任务数据。section记录未含provider/tools实际运行详情；root另提供已核provider=openai/tools0，本次没有独立再查run或网络终点。

## 两处可定位问题/呈现风险

### 1. 宿主金额注入把内部unit直接给读者，未显示人民币币种/尺度

首章rendered在“盈利特征”段出现`802208126.13 unit`、`827121964.81 unit`、`1012283571.60 unit`及`255537261.40 unit`；“观察与质疑”段有`3123918306.63 unit`与`0 unit`。原模型仅用fact占位，**这个unit字面由宿主注入**。

对应Fact：

| Fact ID | 指标 | 冻结口径 |
|---|---|---|
| 234fdf0d-22b2-4385-a6c2-4e33023ce546 | core_profit_2025 | value802208126.13；unit=unit；currency=CNY；合并；DERIVED；原件p68–69 |
| 4d866f20-e882-4e5f-b95e-8c3f4c8258a1 | core_profit_2024 | value827121964.81；相同尺度与币种；DERIVED |
| 51bf4241-9eb3-41fc-8b34-15b591181b74 | cfo_2025 | value1012283571.60；unit=unit；currency=CNY；p71 |
| 2391133f-98ac-44d8-9928-027fe405eb55 | cash_recon_operating_payables_increase_2025 | value255537261.40；同上；p146 |
| 8385dee3-e572-4e09-8860-26e69108baa8 | cash_at_related_finance_company_2025 | value3123918306.63；同上；p119 |
| 943c4d34-ae46-4c17-8d37-d6f4f12d7ecb | restricted_cash_declared_2025 | value0；同上；p119 |

数值本身与冻结fact相同，未发现错乘万/亿；问题是读者正文缺CNY/元语义。当前`report_runtime.py.validate`数字替换拼接value+fact.unit，忽略currency，导致内部通用unit漏到报告。对于该包已经明确为whole CNY的金额，应在**不变更原数字/尺度的前提**下呈现可读币种与单位，并保留derived定义；不能让读者猜unit是元/万元。这里只报告问题，不改冻结源或运行版本。

### 2. 原paragraphs[3]将存货现金流调节项写成“报表口径变化”

位置：首章“周期位置”段，原JSON paragraph index3。其文字把`{{fact:71f77529-6e52-4808-8471-1165ac0ca616}}`（现金流补表存货减少20,243,434.06，CNY元，2025FY，p146）随后解释为“仅反映公司报表口径变化”。

该fact是现金流补充资料“存货的减少（增加以‘－’号填列）”，**不证明会计政策、统计范围或报表口径发生改变**。可以说“报表口径下存货变动对经营现金流的调节”，并保留“不能单独证明终端动销或行业库存见底”；原措辞容易引入未经来源支持的口径变化含义。不是发现该金额错误或已经证明真实经济原因。

## 所查范围内保留得当的限制

- 未把unincorporated2022/2023材料说成已完整阅读/形成新经营核心；首章明确长期回报/分红/行业时序不足。Q32026仅引用存在事实`1a171fae-762e-4905-aac1-9e3a781c6e2f`，不声称已提取其全部经营数字。
- 成熟价值/红利、国内定价权与周期位置都保留待验证，未写概率、正式评级、目标价或当前可用价格；结尾明确当前定价仍拒绝，未用baseline conditional替当前审核。
- “核心利润”引用的两个fact为明确DERIVED营业成本费用差额，正文没有将其称归母净利；CFO也没有直接叫正常化FCFF。关联财务公司存款未被当合并金融自营业务，受限现金0也没有被扩成交易对手无风险。
- 读者正文中有“结构化经营数据”等技术措辞；gaps尾部有“已复用年度财务事实，未进行新增网络核验”。这些是覆盖/获取局限说明，没有观察到冒称已执行模型复核、展示宿主脚本流程或把失败章伪装完成。是否进一步改成读者语言不在此作风格性finding。
- 一些“地区收入未知/下一步查年报”是**固定51facts的覆盖不足**，不能解读为公司原年报没有披露。我们已知年报p16有地区/产品表；但其数值未入本次固定51fact。该包局限应保持可追溯，不能为补正文悄悄消费未冻结新材料。

此为一条COMPLETE章节的抽样语义核对，不是全报告引用/财务事实背书，也不表示所有章节/闸门已通过。FAILED第二章没有纳入“语义通过”结论。

## 追加：第二章实际FAILED run错误证据

按root后续授权，仅GET `http://127.0.0.1:8028/api/company-research/report-runs/e07ab5bd-d2fb-42b8-ab07-9cd27c31231b`，HTTP200，actual取得2026-10-26T22:35:10.224330+00:00；17397 bytes；response SHA256`d35f732747eb27024ac0aecd8244f4715a0a98c1c38c0d9943d2fb7ae534334f`。原回执/响应保存同目录`rv08-sampled-failed-run-receipt.json` / `rv08-sampled-failed-run.json`。未POST、未启模型、未修改run。

- 实际status=FAILED；error.code=`UNBOUND_FINANCIAL_NUMBER`；type=HTTPException。
- context.paragraph_index=3（0-based）。offending_sample原样为：`为同规格产品的一罐，或规格固定的一箱。单位毛利应以该产品不含税、扣除折扣返利后的销售收入减对应销售成`。
- reason=`Chapter candidate contains an unbound number or active content; original output retained`。
- 该run实际model/resolved_model均gpt-6.1-sol、model_provider=openai、model_executed=true、tools=[]，有runtime_turn_id；命令SHA`f91852cb889a5ac376def00f4053623364042715efd4213eb4684db918e43319`匹配preview第二章。这是实际模型尝试后宿主校验失败，不是来源失败或“未调用模型”。

另只读该run登记的原始输出`raw/5a8e311b6d19e0cea8e08bf814b5ee1feafc30114bbaf7a4f6819a616b985d63.raw`对应paragraph3，SHA匹配。此处是建议最小观察单位为同规格一罐/固定规格一箱、说明单位毛利概念，并明确缺少规格、成交价、销量和成本归属，**单位售价/单位成本/单位贡献均未知**。因此本次具体命中是“一箱”这种概念性单位计数，静态上属于验证器把泛指观察单位当作未绑定财务数字的**过宽命中候选**；它不是凭空宣称公司实际一箱金额/规格/销量。不能由此推断整篇第二章候选全部合格，仍为FAILED未发布语义样本。

后续若修校验器应在新冻结版本/新attempt下验证，不能编辑既有输入/输出或把此失败记录改成成功。本笔记不实施修复、不恢复任务。


## 追加：第3–8章已生成原输出定向抽查

实际读取时刻：2026-10-26T22:48:07.703606+00:00。只读 `rv-ticket08/.scratch/roll-research-valuation/evidence/08/captured/cancelled-08.2/output-{3..8}.json`、preview-08.2/packet.json、command-3.json、冻结排雷清单及相关组装源码；未运行网络/模型/测试/估值，未写DB、未改实现/冻结输入/失败原件。6章共38段，每段事实ID均在固定51facts中，但ID存在不等于语义/来源全面核验。六份SHA此前与同目录manifest逐份核对相符。

|章|原输出SHA-256|段数|
|---|---|---:|
|3|135a2d62a0e4b8df118e46b0eafe4cbdd3883367ea683c826274094ac082d11a|7|
|4|a62b9a387e1ded0c5400e03666dcd450370f9d4425a4e85377cb17f97adeb47a|7|
|5|a2d7dc89634225c7a72f731ab4ea0ddb9dc34c33a4e852cb11953b69ee451640|6|
|6|2d19eea9d9db216eff28ffd14b08fc343d5f6bae91e8ce62aaf74cf5d44aa086|7|
|7|4539b708e1b107e0f042a9b1e5dadffccd0c819a17e26ff56d114b9974715667|6|
|8|272c5580e1e1c9a83992207c8937020b556bb32a2b068d82fa52e61e3ff129eb|5|

### 一个新增的具体组合报告矛盾：第3章把上下文未展示写成全报告未提供

输出：output-3.json，SHA `135a2d62a0e4b8df118e46b0eafe4cbdd3883367ea683c826274094ac082d11a`。

- paragraphs[0] 原文：`固定经营研究仍属有条件基线；逐项预测假设未获列示，因此不另设增长率或利润率。` 该段事实ID为 `741985a1-01b6-4cf5-ac1d-1f29dad6e0e4`（业务结构）、`234fdf0d-22b2-4385-a6c2-4e33023ce546`（DERIVED core_profit_2025）、`4d866f20-e882-4e5f-b95e-8c3f4c8258a1`（DERIVED core_profit_2024）。这些事实支持业务/历史利润定义，不证明固定模型没有预测假设。
- paragraphs[6] 缺口表原文：`固定经营假设及情景参数 | 已有年度事实与条件研究结论未列示逐项参数 | 取得原经营模型的假设清单与适用条件；须与原版本一致，不能另行替代`。该段只引用 `1a171fae-762e-4905-aac1-9e3a781c6e2f`（2026Q3披露存在），与模型参数是否提供无关。
- gaps[0] 原文：`固定经营模型的逐项预测假设及情景参数未提供，不能复述未见参数或生成新的量化情景。`

支持边界的实际核对：exact command-3 的 CORE.core.hypotheses=[]，原因是确定性ticket05沿用公开财务证据、没有新模型生成的假设集合；其 VALUATION 只有snapshot_id、economic_review_ids、valuation_ids、limitation，**确实未把fixed_operating_model和valuation_subsections送给章节写作者**。所以原输出不另造数字是合理限制，不能将此诊断为幻觉数值。

但完整冻结 packet 的 `valuation_binding.fixed_operating_model` 实际含 `assumptions`（1项复合研究假设）、2个 `drivers.scenarios`、2个 `cashflows` 情景、config/economic_basis/normalization/provenance，经营模型ID `dad3b6dd-1629-53db-b6fd-3c7aae32a5eb`。baseline年度路径已有量价增长、维持投资/折旧、WC等显式假设，正文9.3已经冻结逐年预测表、9.4有WACC与桥、9.5有两个条件情景。这与“原模型逐项参数未提供”的全报告断言冲突。两类对象必须区分：**共享CORE没有新经营假设集合**，不等于**固定条件估值模型没有研究假设/情景参数**。

本finding限于跨章资料覆盖陈述，不意味着这些经济假设已经正确/充分，也不要求补写新的情景数值。新host revision可将这段标作“章节当时未获得模型参数，不能据此评价已冻结模型”，或隔离该未被事实支持的断言；不能悄改既有原输出/输入、将旧attempt当作重跑后的模型回答。

### 其余定向核对中的实际边界（未新增认定错误）

- 第4章 paragraphs[2] 用存货现金流调节事实 `71f77529-6e52-4808-8471-1165ac0ca616` 只称“公司账面金额变化，不是行业实物去库存证据”，没有沿用首章“口径变化”表述；paragraphs[5] 引用 `e63eb52e-e053-409f-abd9-cff14f906be4`（2025年末无需要披露的重要承诺事项）并明确不能推出此后无扩产/资本开支。没有据此宣称零未来capex。
- 第5章 paragraphs[2]/[4] 核心利润为自定义DERIVED差额，明确不是毛利/净利；销售费用不能等同渠道商利润。产品结构、同业、定价权与护城河保留未知，没有将费用上升直接当作品牌回报或竞争力恶化。没有在本抽查发现具体数值超出51facts。
- 第6章 paragraphs[1] 明确应计利息 `cbcd489d-8096-4433-b359-2d9a2b8eca97` 不等于现金实收，且不能从已剔除金融项的core重复扣息；paragraphs[2] 将工程设备应付款 `017ee892-e81f-49d6-aa85-547d1009ff0f` 称“既定口径排除于经营营运资金并纳入债务桥接”，是现有DERIVED桥定义而非发行人法定有息债分类。paragraphs[3] 明确桥 `4f2772fd-fb3c-41b3-8331-ee16a83ff411` 包含银行/租赁/限制股回购/工程AP，不等于纯银行债。未在此将工程AP用于WACC有息负债。
- 第6章 paragraphs[3] 关联存款 `8385dee3-e572-4e09-8860-26e69108baa8` 与受限现金0 `943c4d34-ae46-4c17-8d37-d6f4f12d7ecb` 后明确“需要核实提款条件、期限与交易对手风险”“披露受限资金不能替代实际可支配性验证”；未断言关联存款可全额自由回收、没有重复相加余额。paragraphs[4] 限制股回购义务 `a2b06827-8a0b-4b90-9254-fc3df6c55108` 明确不是已实施市场回购。paragraphs[5] NCI为0 `e928d6b0-c483-4801-a8d9-e6c06bbb010f` 不等于母公司单体权益等于合并，边界得到保留。
- 第7章 paragraphs[0] 实际有“暂列黄灯观察”，同时说明财务信息质量未知、非完整核查、非绿灯。这是模型候选观察，与冻结landmine宿主UNKNOWN应分开呈现；本抽查不认可为正式评级。paragraphs[2] 对少数股东项写“未命中，仅限期末权益结构”，支持仅为期末NCI0；冻结规则关注“权益占比高但损益长期为负”，故**不能把此有限单时点判断覆盖成整个历史损益项目已核查通过**。其正文确有“不外推其他期间”，因此这里记录严格边界，不额外指控其宣称多年无风险。冻结 packet.landmines 对该项仍UNKNOWN，宿主应保留该状态。
- 第8章 paragraphs[1] 对近似市值 `a43c7e7e-e43c-47cd-81a7-ae0a21847ebb` 和股数 `6e02c4d0-a15a-488d-87b0-0c2f777952a4` 明确不足以充当经核验原始价格、不能确定历史高低点。paragraphs[2] 不把core利润或CFO当EPS/PE分母；paragraphs[3] 不把现在取得财务信息当历史先行信号。结尾当前用途继续拒绝，未拿baseline conditional替代当前可用价格或反向现价要求。

单位呈现的既有确定问题同样覆盖这些表格（详见 `rv08-unit-presentation-notes.md`），本次不重复认定为六个独立财务错误。诸如“未开展外部检索/结构化资料不足”属于固定包覆盖说明，不等于年报没有披露；特别地区/产品等年报表格未进51facts，不能把未知扩成公司不披露。未发现本六章冒称已完整纳入2022/23原件。

以上仅对38段的指定风险点作定向只读抽查，不能替代逐源事实核验、全报告审核、经济批准、评级或真实current-pricing可用性认定。原始失败与取消记录保留。
