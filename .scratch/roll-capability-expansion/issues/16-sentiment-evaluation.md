# 16: 中文情绪组件与有限评测

**What to build:** 用户可在研究观察中查看可追溯的中文文本分类及其评测限制。

**Blocked by:** [15 · 新闻证券关联与转载去重](15-news-entity-dedup.md)

**Status:** needs-info

**Completion:** partial

**Execution:** PARTIAL — 受限研究组件已交付；2026-10-18接手修正拒判漏计FN的评测错误（合并负向召回0.200、二类macro-F1 0.563），并查实旧120/30时间范围重叠。FinBERT2情绪checkpoint仍未找到；中文FinBERT替代路线待用户选择，尚缺事件/时间隔离的新冻结评测。按验收第6条保持partial。

**Scope / inheritance:** FinBERT2为优先候选；无合适权重不能假称接入成功。

**User stories:** US-31、US-32；共同遵循US-53—58。

**References:** [规格](../spec.md)、[执行顺序与依赖](../ticket-plan.md)、[验收追踪](../acceptance-map.md)。

## Acceptance criteria

- [ ] 核对具体checkpoint、中文任务、标签、许可、下载来源、摘要和硬件资源；复用推理入口，不默认训练FinGPT或英文模型。
- [ ] 按ID-10登记至少120条中文有限评测计划和标签来源，事件组/时间隔离；查看结果前固定质量/拒判/速度门槛与评测方法。
- [ ] 二分类不能伪造中性概率；不相关/模糊/低支持返回明确拒判，记录实际标签集。
- [ ] 保存分类结果、对象、模型/输入版本与置信度，公开查询和研究页面可追溯；名称不出现收益概率或买卖建议。
- [ ] 记录真实语料每类支持、macro-F1/召回/混淆、拒判覆盖和延迟；非独立标签不宣称独立有效，未过门槛保持研究受限。
- [ ] 许可/模型缺失则该能力partial并给具体资源条件，不自动接受新服务/购买，不阻塞无依赖报告功能。
- [ ] 附本票适用的代码/依赖版本、公开行为验收、真实与METHOD边界、原失败及剩余条件；若继承另一会话成果，引用精确验收并核对当前版本。不得以仅写计划或仅实现拒绝路径替代所要求的正向能力。

## Implementation boundary

优先复用原服务和指定成熟组件；新增表、接口、页面与测试围绕本票用户路径增量实现，不横向重写整个模块。01交接票只做交接核对；08及23—25是真实运行操作。其他票的API/持久化/界面与测试应作为同一可演示切片交付。新组件不可写真实账本或自签资格；没有必要不新增测试入口或插件框架。

## Comments

2026-10-18 接手复核：现场HEAD b4fb440、379条既有dirty/untracked，上一实施会话notLoaded。公开元数据核查9个FinBERT2同名仓库，官方base/large是MLM，Riverise为环境主题分类且许可未明，未下载不适用权重。已确认Apache-2.0的yiyanghkust/finbert-tone-chinese三分类替代候选（不是FinBERT2），等待用户选择。纠正原评测漏计拒判FN/跨类FP并保留旧报告；现有150条合并负向召回6/30=0.200、二类macro-F1=0.563218。旧切分日期交叠、holdout无中性，不能声称时间隔离；下一候选须重新冻结分割。修改后pytest10通过、构建通过、Chrome1通过，真实旧模型10条副本运行正向2/拒判8/覆盖20%/账户0→0/网络0，旧包重放不变。见[本次验收](../evidence/16-sentiment/takeover-20261018/acceptance.md)。16仍partial；17/18/22/26依赖不解除。下文旧0.500/0.803指标为旧口径历史，由本次纠正报告取代当前指标依据。

2026-10-14：依据用户授权发布，尚未实施。完成状态与真实启动条件独立于分诊标签；先读01交接和任务计划，保留另一会话成果及原P0验收。


2026-10-18：只读核对 HuggingFace 组织与 GitHub README，未找到可直接推理的 FinBERT2 中文情绪权重；官方仅提供 base/large 预训练与 Fin-labeler/SC_2 训练数据+脚本。归档中文新闻仅10条/3正文，不足120条标签集。详见[诊断](../evidence/16-sentiment/model-and-corpus-diagnosis.md)。需要用户选择：提供许可明确的情绪 checkpoint，或授权自训+标注方案。未下载/未训练/未改依赖，17及后续保持阻塞。

2026-10-18：新增 SENTIMENT-CORPUS-01（3请求/150条唯一标题摘要/73KB/零重试，同上游），数量已够120但仅标题摘要且非独立来源；仍需冻结120条标签与阈值、确定许可明确的中文情绪权重。FinBERT2 仍无情绪 checkpoint。16 保持 needs-info。见[诊断](../evidence/16-sentiment/model-and-corpus-diagnosis.md)。

2026-10-18：SENTIMENT-CORPUS-02 取150条公司名标题摘要；冻结 labels-120（P45/N24/U18/I33）与门槛；下载 Erlangshen apache-2.0 权重（SHA a1d1328c…，409MB）离线推理。结果：二分类 macro-F1 0.853、P recall 1.0、N recall 0.625、低置信拒判9.2%、p95 0.26s；但51条中性/不相关仅3条被拒判（5.9%），48条被强判方向。能力保持 RESEARCH_LIMITED，16 partial。下一轮先冻结拒判规则再重跑，并接入API/页面；不得据本轮称通过。见[结果](../evidence/16-sentiment/eval-report.md)。

2026-10-18：冻结拒判层（R1—R5）后重跑，设计集 macro-F1 0.956/中性拒判0.804，但留出集 N recall 0.000、合并 macro-F1 0.803、N recall 0.500、总拒判覆盖0.540，未过门槛。能力仍 RESEARCH_LIMITED；下一差量为受限研究组件的持久化/API/页面与覆盖说明。见[第二轮结果](../evidence/16-sentiment/eval-reject-report.md)。

2026-10-18：受限情绪组件交付：隔离推理、reference 指纹、只追加存储、公开查询、页面限制、METHOD 1 passed、真实10条归档新闻运行（POSITIVE2/拒判8/覆盖20%/账户0）、Chrome 1 PASS、回归5 passed。替代模型合并 macro-F1 0.803、N recall 0.500、拒判覆盖0.540，未过门槛；FinBERT2 权重缺失。16 保持 partial，17 及后续继续阻塞。见[验收](../evidence/16-sentiment/acceptance.md)。
