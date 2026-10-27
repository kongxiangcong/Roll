# 估值与投研开发执行索引

依据：[实施规格](../spec.md) v1.0。顺序：**01 → 02 → 03 → 04 → 05 → 06 → 07 → 08 → 09 → 10 → 11 → 12**。

所有票分诊为ready-for-agent，依赖通过才可执行。Completion独立记录完成状态，不新增分诊标签。当前下一票：**08**。01—07已完成，分别见[01证据](../evidence/01/README.md)、[02证据](../evidence/02/README.md)、[03证据](../evidence/03/README.md)、[04证据](../evidence/04/README.md)、[05证据](../evidence/05/README.md)、[06证据](../evidence/06/README.md)和[07证据](../evidence/07/README.md)。04原始结果保持unreviewed/usable_range=false；05另有宿主经营模型/经济审核及固定引用的共享子快照。06提供显式双快照三类比较、固定旧路径反推/有序模型对照、独立信息时效和不可变恢复；合成比较不冒充真实报价或市场因果。真实日期基准正向conditional、当前定价及江西铜业缺口blocked，不代表联合A6全链或整体功能完成。

| 顺序 | 任务 | 依赖 | Completion |
| --- | --- | --- | --- |
| 01 | [冻结双工作流合同与参考能力映射](01-contracts-and-source-map.md) | 无 | complete |
| 02 | [实现公司身份、共享证据与核查记录](02-shared-evidence-and-identity.md) | 01 | complete |
| 03 | [实现经营假设及共享分析快照](03-research-state-and-snapshots.md) | 02 | complete |
| 04 | [接入可复算条件估值计算器](04-conditional-valuation-engine.md) | 03 | complete |
| 05 | [连接经营驱动、正常化与经济审核](05-operating-drivers-and-review.md) | 04 | complete |
| 06 | [实现三类变化与信息状态比较](06-daily-change-decomposition.md) | 05 | complete |
| 07 | [将持续投研与估值融入每日使用](07-daily-research-integration.md) | 06 | complete |
| 08 | [实现投研与估值完整报告流水线](08-report-template-and-pipeline.md) | 07 | in-progress |
| 09 | [实现Markdown/PDF交付与版本恢复](09-report-artifacts-and-recovery.md) | 08 | not-started |
| 10 | [交付独立公司研报入口及共享联动](10-report-workflow-ui.md) | 09 | not-started |
| 11 | [提供研究特征快照与增量验证协议](11-probability-research-interface.md) | 10 | not-started |
| 12 | [完成双工作流真实联合验收与交接](12-integrated-real-acceptance.md) | 11 | not-started |

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

08当前恢复入口为[08.5检查点](../evidence/08/checkpoint05.md)：必要本地摘要/数值覆盖修复及49+14项工程检查已完成，四份特定payload外发授权仍待人类；未发布、未验收、不解除09依赖。
