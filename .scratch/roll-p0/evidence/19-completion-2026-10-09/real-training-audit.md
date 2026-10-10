# Ticket 19 真实训练路径只读审计

日期：2026-10-09。范围：仓库规格、票 17—21、领域文档、公开契约、研究源码及应用测试、脱敏验收回执。未访问实际数据库或任何 `.roll-data`，未读取封存事实/收益、未计算标签、未训练、未取新数据、未修改生产文件。以下是实现设计与证据边界，不是实际完成验收。

## 结论

1. **真实训练路径确实尚未实现**，并非仅缺供应商凭据或更多行情行数。来源覆盖登记恒为 BLOCKED / NOT_PREREGISTERED；特征函数非 METHOD 恒拒绝；执行器即使算出真实成熟结果，也从未将 `eligible_for_training` 改为 true；模型入口非 METHOD 恒失败；预测与重放只支持 METHOD。
2. **票 19 可冻结真实模型和校准器，同时保留 `sealed_independence=UNPROVEN`。** 票 19 第三项明确只访问获准开发/校准，完整实验要由票 20 补齐政策再冻结、票 21 才做确认性检验。封存独立性不足不应阻止一个有真实合格 DEV/CAL 证据的模型工件进入冻结实验区；它仍必须阻止确认性 PASS 与正式资格。不能因此消费旧封存、宣布 G3/G7 通过或把当前预测写成历史实际发布。
3. “独立校准”在本票首先是**校准样本独立于模型训练**，不是在 19 先消费最终封存验证校准质量。先冻结开发模型，再归档校准窗的时间外原模型预测，最后拟合一次截距校准。校准后的同窗评分必须继续写 `FIT_IN_SAMPLE / NO_INDEPENDENT_CALIBRATED_TEST`；模型冻结不要求已经证明概率可靠或盈利。
4. 目前能依据脱敏实际回执确认**江西铜业至少两次来源预检已计 PRIMARY_FIT**，不是五次已用尽。五次边界测试和旧 600519 家族不能直接作为当前 600362 家族的真实剩余预算。需主进程通过只返回家族尝试元数据的受控入口确认，再决定是否可执行一次真实拟合。旧失败预算不得清空、改类或删除。
5. 公开原件哈希正确、资料有官方出处、当前两供应商价格一致，都不自动等于历史时点版本已证明。若不能补齐日线历史版本/公告版本、状态和权益的机器可验证依据，本轮可以把真实训练能力实现并验证，但不得把尚不合格的真实源转为票 19 完整完成。

## 已检查的主要依据

- `GLOSSARY.md`：成熟结果、实验协议、验证结论、验证交付、工程交付。
- `docs/adr/0001-default-engineering-route.md`、`0002-on-demand-analysis-and-coverage.md`、`0003-automated-validation-review.md`。
- `.scratch/roll-p0/spec.md`：ID-06、10、14、16、21；票 17、18、19、20、21。
- `backend/src/roll/research/{datasets,design,registry,execution,models}.py` 与 `backend/src/roll/app.py` 公开研究路由。
- `backend/tests/application/{test_transparent_models,test_research_acquisition_import,test_research_protocol,test_research_lifecycle,test_execution_labels}.py`。
- `docs/{research-protocol,transparent-model,daily-execution}-contract.md`；`evidence/19/{acceptance,baostock-acceptance}.md`；脱敏 `actual-http*.json`、`baostock-real-acquisition*.json` 的模型/协议/尝试元数据，未输出其中样本内容。

## 三种时间必须区分

| 字段/时间 | 意义 | 消费规则 |
| --- | --- | --- |
| `received_at` / 现有源 `available_at` | 今天宿主真正收到并可用的档案时间 | 今日研究进程的 `consumer_knowledge_cutoff` 不能早于它；不得回填为过去交易日 |
| `published_at` 或经证明的历史版本公开可得时间 | 特定版本何时公开，而非财报期末、今天文件修改时间或公司行为生效时间 | 历史重构使用该版本时，须证明其公开时间不晚于历史观察截止；日期粒度不得伪造时分 |
| `observation_cutoff` | 该历史预测设定使用何时以前的完整信息 | 特征禁止读取晚于它的日线/版本；回看完结与版本可得证明均要满足 |

今天取得 2017 年原版年报，不意味着 2017 年没人能知道该年报；但还需原版文件与官方公告索引/日期精度绑定，证明当时公布的是该版本。保留原版和修订版，历史观察不取后来修订值。今天接口返回 2013 年 RAW 日线，只能证明今天返回了这些数据；每日完成时间或交易所收盘时间并不证明今天返回的每个历史值就是当时公开的版本。

可以在现有事实旁新增**单独的证据衍生历史可得记录**，例如版本 SHA、公开时点/精度、发布依据原件 SHA、完成时点依据、适用观察区间及修订关系。宿主从归档原件和固定解析规则验证记录；不能接受用户/客户端提交 `historical_point_in_time_proven=true`、`eligible_for_training=true` 或任意可信发布时间。新记录不改写源 `available_at`。日期精度材料只能按预登记保守消费边界使用，例如下一明确交易日，不能默补 15:05。

历史模拟输入可以使用今天已获的历史原版，条件是同时满足“今日研究知识已得到该原件”和“该版本在模拟观察截止已公开”的两套检查。此路径是 HISTORICAL reconstruction，不是过去实际归档的前向预测。

## 真实训练最小实现切片

### A. 可验证证据准入与登记窗口

`datasets.import_acquisition` 保留原版本，增加宿主验证的来源组合/资格子记录。只绑定现有已归档材料标识：RAW 日线原件、状态证据、权益事件及完整性依据、历史规则/日历、版本可得依据。验证原件 SHA/长度、事实到原件关联、证券/日期/单位/版本范围、冲突处理。输出每项 VERIFIED / UNKNOWN / CONFLICT 及明细，不加人工 proved 开关。

新增最小受控用例，例如 `POST /api/research/datasets/{id}/design`，命令只引用已归档设计/取证标识及 predecessor/basis；或扩展协议登记引用同等的设计标识。不能直接把外部传来的窗口、阈值或 PIT 标志当成资格。窗口必须在读取标签/拟合前由实施代理依据覆盖元数据提出，并保存 immutable design artifact。新分片引用合格证据、归档筛选代码 SHA、准确标签/上下文界限。

设计须保留现有候选/四特征、20 日事件、λ=1、0.60、基础成本和全部统计条件。不能沿用固定 80/40/21；也不能看标签后移动边界。新长范围只依据信息增量与覆盖确定窗口，原 CAL40 支持不足结论不改判。开发/校准间的 label embargo 和上下文不能混淆：前置 20 行只供校准特征，不能拟合其标签；拟合标签的成熟日期必须在本 partition 内。

`partition` 从资格子记录给出准确的历史可得依据，仍验证实际 `available_at <= consumer_knowledge_cutoff`。普通 SEALED 路由保持 403，DEV/CAL 只读本片，不先读取全档再在模型中滤掉 SEALED。未预登记、资格 UNKNOWN/CONFLICT 必须维持拒绝和具体缺口。

### B. 历史规则/状态/权益在执行器真正使用

`DailyExecutions.create` 固定观察日、未来执行期、对应逐日期规则与税费版本；不能把现行证券交易税费回填 2013 年。原 3 bp 佣金/5 bp 滑点仍明确是研究假设，未知实际券商费用不当 0；法定税费须按对应时期和原协议处理。

`evaluate` 对每个需要的交易日检查状态、版本/完成、证券规则与权益。它目前仅接受 `company_actions=CONFIRMED_NONE` 或单个全现金终结，**没有真实现金分红/送转/配股处理**。最小加入已确认权益事件路径：权益基准持股、现金到账、股份变化、税款/持有期/卖出扣税和终结结算有各自原件及日期；影响 entry/exit 的价窗、股数、现金和费用必须可重放。遇到未证实/冲突事件仍 UNSCORABLE 或协议预登记区间，不能将没检索到事件改成 CONFIRMED_NONE。

分红数据本身不证明公司行为全集完整；年度股份未变化不证明期间不存在停复牌/ST 或现金权益。只可对证明覆盖的区间推导事件状态。避开某些权益窗口必须事先设计并说明按信息条件筛选，不能看到输赢后排除不利标签或使原协议翻正。

只有真实来源、完整输入验证通过、成熟且可评分、分片隔离通过，才派生 `eligible_for_training=true`；METHOD 始终 false。该值在宿主结果内计算，客户端不能授予。`label_available_at` 仍是今天真正计算并归档的时间，`label_matures_at` 是历史事件成熟界限；二者不同。复评留子记录，旧结果和老引擎版本保留。

### C. 真实模型与截距校准

`models.features` 保留 METHOD 分支，非 METHOD 改为消费 A 的已验证历史可得依据，检查 21 行、单位、RAW、完整性、交易日连续性及观察截止，不以 `not method` 无条件拒绝。RAW 公司行为跳变是否可以进入现有固定四特征必须由 M0/真实可得权益处理明确；不得临时改为最新前复权价且沿用原特征指纹。

`TransparentModels.create` 仍先计 PRIMARY_FIT，失败占预算；预检/支持不足没有中性模型或概率。验证 DEV/CAL 时间隔离、唯一观察日、基础执行情景、结果到原始执行 SHA、现行代码/数据/协议绑定。去掉仅以非 METHOD 为理由拒绝的硬编码，替换成宿主证据检查。未满足源准入、真实每类支持和时间隔离时仍 FAILED。

复用现有确定性有限 Newton/L2 logit、DEV-only 标准化、100 步/总 60 秒，模型工件写实际证据类型，不是 METHOD_CASE。冻结/归档 DEV 模型与 CAL 时间外未校准预测**在**开始唯一 CALIBRATION 尝试之前；校准成功后归档截距、固定斜率、输入预测 SHA、代码版本和统计限制。不能通过失败后重试/新后继重复用同一 family 唯一校准额度。

新增可辨识终态，例如 `RESEARCH_MODEL_FROZEN`，其含义仅“真实开发模型和校准工件不可变且可复放”，`complete_experiment_frozen=false`、`validation_verdict=null`、`capability=NOT_GRANTED`。压力或输入支持失败仍不发布正式版本；模型工件有数值不等于通过压力/统计资格。新 freeze receipt 绑定全部已结束家族 attempt manifest，不能只列成功模型。

### D. Forecast / replay / 基线与研究视图

`forecast` / `replay` 对真实冻结工件使用正确 source evidence kind 与真实可得校验，不再强制 `features(..., True, ...)` 或写 METHOD_CASE。19 中仍只允许获准 CAL 开发诊断范围，不开放 SEALED/正式调用。归档 FeatureSnapshot、模型/校准/执行/成本/规则/协议/data/code SHA、观察截止/消费截止、限制和经验收益情景。旧日期预测是今天的历史重构，`formal_forward_prediction=false`，不写前向起点。

代码指纹不能只覆盖 models.py：至少绑定 features/fit/calibrate、18 执行器、数据资格/分片规则、所使用历史规则/税费、特征定义和环境版本。可用一个小且明确的 canonical-LF 文件 SHA 字典，不需新框架。重放原档案+原工件，0 联网、不再训练、不读取当前源。旧模型来源/算法版本不一致继续拒绝。

必要基线 CASH、START_HOLD、MA5/20 要有可比较的定义及结果。现有 CASH/MA 逐机会 sanity check 不等于连续 START_HOLD；代码把后者显示 NOT_EVALUATED。本轮不能用措辞把未实现结果写为基线已完成。最小完成可为获准开发/校准窗生成同资金、同费用、同起点的历史 START_HOLD 比较与固定 MA 结果，明确资产路径与逐机会概率指标的不同；票 20 再实现完整冻结政策和连续 ShadowAccount，票 21 对匹配 NAV/尾部/回撤/覆盖做 G4 验证。若暂未提供基线实际比较，应保留票 19 第一/第五项未完整满足。

页面分列 METHOD 和真实研究、旧失败、新模型工件、原模型 CAL held-out 预测、校准 fit-in-sample 描述、未完成独立验证、支持和 sealed independence。保留没有正式资格状态，不因 Brier 改善/更高胜率把候选发布。

## 校准/支持条件：不降低阈值，也不把验证条件倒置为冻结前提

- `minimum_calibration_examples_per_class=20`：至少 40 个真实、唯一观察日且完整成熟可评分的 CAL 标签，并且实际两类均至少 20。CAL 至少 60 个交易日才有理论上界 40（20 日成熟尾巴不评分）；60 只是上界，不保证两类达到支持。不能先看标签再加长/缩短 CAL。
- DEV 需 21 行回看、两类、时间隔离；特征标准化/权重只拟合 DEV。所有训练标签成熟不得越窗；CAL 仅用过去 20 行特征上下文且不能用那些上下文标签。
- 固定五等宽可靠性箱，每个占用箱 20；入选成熟样本 40；20 日依赖有效块 30；统计预登记包含 20/40 块敏感性、同日多股联合与重叠期限。保留所有数值及不足。`len(labels)//20` 仅上界，不是实测独立样本数。
- 30 个有效 20 日块理论至少需要 600 个成熟时间点；重叠/非平稳和实际筛选可使有效支持更低。它是概率/确认性统计支持条件，不等于已有 600 行便通过，也不能成为可忽略 PIT 的理由。
- 票 19 可以归档校准工件和不足诊断，不能给 calibrated-test PASS。经过 CAL 拟合再在同 CAL 评分只能描述拟合内表现。真正独立校准效果测试由完整冻结后的独立历史/前向区间做，属 21/32，票 19 禁止读取 SEALED 来提前满足。

## 家族预算与后继的可执行路径

`registry.register` 对同证券且覆盖日期有交叠的既有协议要求 predecessor；`family` 从共同根收齐后继和分叉；`start_attempt` 在 BEGIN IMMEDIATE 中统计全 family 的 PRIMARY_FIT/G5_NEIGHBOR，五次含失败/中止/中断，CALIBRATION 只一次。来源预检也已被 `models.create` 记作 PRIMARY_FIT。现有规则不区分“预检没算权重”和“实际拟合失败”，不能事后剔除预检来释放额度。

脱敏证据可确认：

| 记录 | 已证事实 | 不能据此推断 |
| --- | --- | --- |
| `19/acceptance.md` 的 EVAL-09 行 + `test_transparent_models.py` | 工程验证五次失败计数，第六拒绝 | 不等于当前实际 600362 已五次用尽 |
| `19/actual-http.json` 与 final 的实际模型元数据 | 旧同一实际协议有两个不同 FAILED attempt ID，600519 工程研究另有 METHOD 模型记录 | 未检查 family manifest，不能把各独立运行/证券合成一个预算 |
| `baostock-real-acquisition-partial-utf8.json`、repaired/json | 两个不同 FAILED preflight attempt ID；repaired 与 json 是同一次回执副本，不能重复计 | 不证明后来又登记了三次，也不证明当前私有运行 DB 只有这些记录 |
| `baostock-acceptance.md` + continuation-live.py | 两个江西铜业预检按 predecessor 关联为同一 family；Fuyao 来源只有 dataset，没有额外拟合 | 不可将两个不同源码回执视为四次，或把 BaoStock 数据行数视为新拟合预算 |
| `continuation-2026-10-09/public-host-live-v3.json` | 公共搜狐归档验收声明 models_fitted=0、labels_computed=false | 无法独立证明其他主机/外部未登记尝试不存在 |

据已有回执，**若当前 600362 family 没有更多登记尝试**，候选仍有三次 PRIMARY/G5 和一次 CAL 额度。这允许保留旧两次预检，取得真实合格来源并合法登记后继窗口，执行一次固定主拟合和一次截距校准。但报告不能把这个条件句当作已核验剩余额度。

主进程应先调用公开 attempt-manifest，只归档 protocol/family ID、category、status、configuration SHA、owner/终态元数据及来源回执，不读取样本；计数包含全 family。窗口登记在新的 successor design，旧数据/协议/尝试/暴露保持不变。新长历史范围若复用当前证券重叠范围必须关联，不新开根绕过。仅因为换供应商、改 code SHA、更多旧行情或换名称不产生新预算。

若确认已有五次或 CAL 已用尽，按现有冻结协议 **该 family 无可执行训练/校准路径**。不能为了 close 改计数、改变技术上限、伪造新根或改进版继承独立性。新的真实不同研究能否有预算必须形成明确的新信息/假设、受允许协议规则管理并保留旧家族关联和历史，不在本只读审计中擅自授权。无合法额度时真实工件验收仍不足。

未来可把“只看准入缺口”的公开只读 preflight 与模型实际 attempt 分开以免误耗后续额度，但这只影响未来调用，不可改写已经被协议计数的两次失败。调用 `/models` 就必须按原规则计数。

## 硬编码门禁分类

| 位置 | 正确保留的控制 | 当前未实现应替换的部分 |
| --- | --- | --- |
| datasets.import_acquisition | 原件/Parquet一致、请求/run/snapshot关联、RAW单位、限定单股、客户端不传资格 | 所有真实来源恒 BLOCKED，三窗恒 NOT_PREREGISTERED；没有取证验证/设计用例 |
| datasets.partition | SEALED普通入口403、明确分窗、原 available_at 检查 | historical_point_in_time_proven 恒false；只有老固定工程分片 |
| models.features | 21行完整RAW/SHARE、最新观察日、可得性、日历连续 | 非 METHOD 恒抛 PIT；真实分支没有历史版本/完成时点证明消费 |
| execution.evaluate | 未成熟/未知状态/缺行/权益不足不可评分；日线不推测盘中路径；边界purge | eligible_for_training全路径false；现金分红/股份等处理未实现；历史法定费用版本未消费 |
| models.create | 尝试先登记、失败计预算、唯一日期/成熟/真实资格、CAL每类20、先预测后校准、有限拟合 | 非 METHOD恒追加real-not-frozen并抛错；工件source/status恒METHOD；不存在真实模型 freeze receipt |
| models.forecast/replay | 仅获准范围、原模型/输入SHA、代码不同拒绝、离线重放 | 仅METHOD status、features method=True、bundle恒METHOD |
| registry.freeze/checkpoint | manifest完整、无RUNNING、完整政策/方法缺口、未完整禁止confirmatory | freeze恒拒绝属票20所有权；19需独立 model-freeze 记录，不能在19把完整freeze突然授予PASS |

`REAL_MODEL_AND_CALIBRATOR_NOT_FROZEN` 是真实模型 create 中的循环前提：入口正要生成工件，却因为尚无工件永拒绝。应检查“数据/设计/支持是否足以拟合”，成功后生成模型冻结状态；不能要求已经有相同待生成工件。PIT/status/actions 未证实时的失败则是正确数据门禁，不能当作同样的循环前提删除。

## 建议应用验收（非真实结果替代）

1. 固定响应工程用例：真实路径解析器成功/缺发布精度/修订冲突/证券或日期不符/损坏SHA。客户端 proved/eligibility/timestamp任意字段422；当前修订源保持BLOCKED。
2. 主用例通过 FastAPI：登记经宿主固定原件解析的设计 → 只读 DEV/CAL → 18成熟执行 → 固定真实路径拟合与CAL预测归档 → 唯一校准 → model freeze receipt → forecast/replay → 重启一致；明确工程输入不是实际研究验收。
3. labels跨窗、上下文标签、重复日期/情景、unknown权益、历史税费边界、ST/停牌/熔断、缺失行、未完成日线，均不给真实训练资格；不得按结果删除。
4. 家族两旧失败+一次新fit，manifest保留；第五/第六与兄弟后继仍按原规则；cal一次含失败；不允许独立根重用旧证券区间；不得为了fixture释放预算。
5. 无SEALED调用/label计算/confirmatory look；model frozen但protocol incomplete、seal UNPROVEN、grant UNGRANTED、账户不变、forward null。模型冻结和完整协议冻结状态分别展示。
6. 数值模型/校准输入出错、超时/中断保留失败；未知/0支持无占位概率；归档原输入/权重重放0联网，依赖code/data/rules变化拒绝。
7. 在工程检查通过后，主进程用**实际已合格的 DEV/CAL 来源与合法家族预算**单独执行，记录原件/设计/窗口、真实成熟支持、排除原因、fit/calibration工件、基线、时间外预测/限制和HTTP/SQLite/页面验收。固定响应工程绿色不能代替这一步。

## 建议先后顺序

先核验实际家族剩余预算，再并行完成真实证据可得/状态/权益与历史规则的机器取证设计；没有合格源不要再调用会耗预算的 `/models`。实现 A/B 的固定应用拒绝及可验分支，继而 C/D 的真实工件冻结/重放，最后用合法真实 DEV/CAL 执行一次固定候选及唯一校准。是否完整完成票 19 必须按实际样本与工件/基线证据判断；不能以“源码不再恒拒绝”或“下载更多PDF”关闭票。
