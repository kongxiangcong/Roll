# 后续 tickets 双轴审查

完整范围从 `eabc7a3ae3462821bedc80c2d6c8b2a88d04b19c` 到集成修复 `25d9b9ae48b94ea4603cc36ab3dbacc8200be248`。两轴并行、只读，统一修复者提交 `581aa21ff3f78e36d8912a89c72714225ea7af4a`，再由独立 merger 合入。

| 轴 | 原发现 | 最终未解决代码问题 | 证据 |
| --- | --- | --- | --- |
| Standards | 0 硬性违例、0 可执行设计问题 | 0 | [独立报告](standards-review.md) |
| Spec | 3 个 P2 | 0 | [独立报告](spec-review.md) |

三个问题分别为登记日卖出后仍获分红权益、同截止时点新增样本污染历史评估重放、关闭后结算延伸原成熟边界。现在按实际当日成交后持仓登记权益，评估保存原消费样本身份，结算固定原关闭时点/自然月期限。旧冻结档案保留，方法变化时公开入口拒绝继续计算并要求关联后继实验。

[修复验收](review-fixes/acceptance.md)保留逐项业务红/绿、环境失败及旧版本隔离证据。最后单轮组合 **44 passed / 458.10s，exit 0**，包括财务、技术审阅、验证、前向及真实进程恢复。14 个列明源文件在最终运行及 evidence-only merge 前后相同；12 个原模型依赖 SHA/长度未变。先前 460 项回归是本轮初始源码基线，不称为最终修复版全量回归，也不把分轮通过数相加。

原19 `reconstructed19-v1/roll.sqlite3` 在根复核时 SHA256 仍为 `ec46257c4420f69c245791778c49079355700615cc3ed7b94d8027bd4dcf66c4`；没有启动或写入该原件。工作树清理和根依赖逐件保全另见 [20/21](cleanup20-21.md)、[23/30](cleanup23-30.md)。

审查通过不解除真实验收条件：23仍缺获准的实际双后端审阅，30仍缺经核验当前状态/公司行为输入及Host装配闭环；METHOD不能代替这些证据。23/30保持 partial，其依赖票继续 pending；实际前向计时未启动，能力 NOT_GRANTED，未推送。

独立 merger 在同产品源码下验证三项公共API边界及四项财务字面预期，exit 0，见 [独立结果](review-fixes/independent-fixed-boundaries-results.json)。修复后的实际研究一致副本追加关联后继实验，沿用原模型、三份历史预测与四份拟合/校准尝试；新DIAGNOSTIC仍G4/G5 FAIL，其余INCONCLUSIVE，影子/验证重放均匹配、0联网。旧记录与3841原档案不变，未重新拟合、消费CONFIRM/SEALED、启动真实前向或外发。见 [后继结果](review-fixes/actual-corrected-successor-results.json)。

新审阅材料 `b27b0047-d0ef-4c39-8d8d-46ad20becc74`，指纹 `95ddbd52fa7f4e2df78b97556f36c6c675da75603eb290ec5ecab260abfbfba1`，7份正文179889字节。root已展示[新清单](D:/dsh-proj/Roll/.roll-data/implementation-evidence/continuation-review-fixes/provider-approval-current/provider-material-manifest.json)并请求分别向OpenAI Codex与DeepSeek Responses执行一次真实审阅的明确批准。旧23包及旧actual-review.py仅为历史，不能用于修复后接续。新helper仅静态编译；当前外发/真实审阅均0。精简正文含parent protocol/全部原attempt，旧freeze/model具体ID关联仅在本地完整材料中绑定，这项上下文局限已展示并保留。
