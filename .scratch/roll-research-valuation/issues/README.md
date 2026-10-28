# 估值与投研开发执行索引

依据：[实施规格](../spec.md) v1.0。顺序：**01 → 02 → 03 → 04 → 05 → 06 → 07 → 08 → 09 → 10 → 11 → 12**。

所有票分诊为ready-for-agent，依赖通过才可执行。Completion独立记录完成状态，不新增分诊标签。当前下一票：**12**。01—11已完成，分别见[01证据](../evidence/01/README.md)、[02证据](../evidence/02/README.md)、[03证据](../evidence/03/README.md)、[04证据](../evidence/04/README.md)、[05证据](../evidence/05/README.md)、[06证据](../evidence/06/README.md)和[07证据](../evidence/07/README.md)。04原始结果保持unreviewed/usable_range=false；05另有宿主经营模型/经济审核及固定引用的共享子快照。06提供显式双快照三类比较、固定旧路径反推/有序模型对照、独立信息时效和不可变恢复；合成比较不冒充真实报价或市场因果。真实日期基准正向conditional、当前定价及江西铜业缺口blocked，不代表联合A6全链或整体功能完成。

| 顺序 | 任务 | 依赖 | Completion |
| --- | --- | --- | --- |
| 01 | [冻结双工作流合同与参考能力映射](01-contracts-and-source-map.md) | 无 | complete |
| 02 | [实现公司身份、共享证据与核查记录](02-shared-evidence-and-identity.md) | 01 | complete |
| 03 | [实现经营假设及共享分析快照](03-research-state-and-snapshots.md) | 02 | complete |
| 04 | [接入可复算条件估值计算器](04-conditional-valuation-engine.md) | 03 | complete |
| 05 | [连接经营驱动、正常化与经济审核](05-operating-drivers-and-review.md) | 04 | complete |
| 06 | [实现三类变化与信息状态比较](06-daily-change-decomposition.md) | 05 | complete |
| 07 | [将持续投研与估值融入每日使用](07-daily-research-integration.md) | 06 | complete |
| 08 | [实现投研与估值完整报告流水线](08-report-template-and-pipeline.md) | 07 | complete |
| 09 | [实现Markdown/PDF交付与版本恢复](09-report-artifacts-and-recovery.md) | 08 | complete |
| 10 | [交付独立公司研报入口及共享联动](10-report-workflow-ui.md) | 09 | complete |
| 11 | [提供研究特征快照与增量验证协议](11-probability-research-interface.md) | 10 | complete |
| 12 | [完成双工作流真实联合验收与交接](12-integrated-real-acceptance.md) | 11 | blocked |

## 执行规则

1. 阅读项目AGENTS.md、本spec、当前票和前票验收。不要从UI按钮或复制脚本跳过共享数据与合同。
2. 更新当前票Completion为in-progress。保持已确认业务边界，完成本票实现及验证。
3. 将证据写入 `../evidence/NN/`；只有验收成立才标complete，同步本索引并将下一票改为执行入口。
4. 遇阻写blocked、原因、已完成工作、缺口和解除条件；不得把失败写成通过或擅自跳到依赖票。
5. 变更依赖或验收须明确修订spec/票并留理由；普通实现选择无需反复询问。
6. 12票完成后才关闭整体功能。研究结论为负、估值局部blocked可以是正确业务结果，但不能替代要求的真实正向完整链验收。

## 阶段成果

- 01—06：共享公司研究、条件估值与变化比较基础。
- 07：日常分析可用切片。
- 08—10：独立完整研报可用切片。
- 11：概率研究输入和协议，不自动训练或改概率。
- 12：真实联合交付与恢复验证。

07已交付[每日切片与完整证据](../evidence/07/README.md)：真实JCC共享经营/量价同屏，多公司历史隔离，原worker存档/来源状态、规范财务字段适配与失败重试，实际浏览器/恢复均已验收。当前JCC估值缺口与05当前用途限制保留；宽回归失败和修复后的36项窄回归分列，不称全部宽回归全绿。两个真实盘后周期留12，整体仍in-progress，08正在实施与真实部分报告验收；失败和追加修订分账见08证据，未完成前不进入09。

08此前待授权恢复入口为[08.5检查点](../evidence/08/checkpoint05.md)：必要本地摘要/数值覆盖修复及49+14项工程检查已完成，四份特定payload外发授权仍待人类；未发布、未验收、不解除09依赖。

08已通过[最终真实PARTIAL实现验收](../evidence/08/final05.md)：四新CODEX完成、12host章节、固定core、94逐项规则、实际发布与32源码/12wire隔离恢复。真实资料缺口仍保留，未声称FULL或A6/A7联合真实链完成。09现可按依赖启动；09–12仍not-started，整体功能未完成。

09已完成[文件层交付与恢复](../evidence/09/README.md)：固定08 PARTIAL报告45页中文PDF，三个交付版本不改原件，6文件实际HTTP下载与新目录恢复SHA一致，8项受影响回归通过。最终45页与8页METHOD视觉检查分列。10网页工作流与12联合验收尚未完成。

10已完成独立公司页面、任务控制、安全预览/下载/历史与固定快照只读联动，真实复用及新任务控制分账见[10证据](../evidence/10/README.md)。11为下一票，整体未完成。

11已交付只读研究特征与原实验补充协议，真实缺失/blocked隔离、迟到与同季去重、保护对象及隔离恢复通过，见[11证据](../evidence/11/README.md)。0成熟样本和未绑定baseline保持DRAFT_UNBOUND/INCONCLUSIVE，没有拟合或改变原概率/旧预算/账户/SEALED。当前进入12，不据本票宣称完整正向链或实际盘后周期完成。

12已实施实际联合验收检查点但未完成，见[覆盖矩阵](../evidence/12/coverage.md)。新增官方半年报/真实网页无auth任务/原文件下载/重启与隔离恢复均留真实证据；新PARTIAL不代替完整CODEX链，A6/A7/A8仍NOT_PASSED、当前自然周期0/2。最终review自动估值编排修复并入后继续按同合同验收，整体未关闭。

12本地资本准备05已保存同原件完整diff与未执行新候选preview，见[证据](../evidence/12/capital-prep05/README.md)。不是新估值成功；原预算2/16及A6/A7/A8未通过不变。
