# 05 联合压力汇总版本验收

基线d9ad670。方法先保存method-before-derivation.json。新版本独立保存源review和joint，不修改successor_evidence_review.py、successor_joint.py或任何旧冻结引擎。严格相同费用id、原件、后继协议和前缀，保留旧FAIL，联合候选硬FAIL到G5、默认绝对硬FAIL到G4，无门PASS。

公开红灯404失败1项/27.53s；实现后 **1 PASS/46.21s**（api-green.log）：旧汇总GET/重放在创建扩展前后及重启均完全相等；联合12场景已绑定且仅移除相应未绑定原因，其余独立/风险匹配/真实缺口保留。错前缀409，暴露硬FAIL保留G4/G5，嵌套joint input损坏使新版本GET/重放409并finally还原；账户不变，后来帧不改变旧版本。

Chrome **1 PASS/56.0s**（体35.9s，browser-green.log）：显式选择、保存联合新版本、重放后再次重放原汇总、刷新恢复及390px截图mobile.png无溢出。隔离profile `.scratch/r05xb`、8162/5262。TypeScript/Vite通过，双审查见对应review.md。15原脏文件0差异、12旧模型依赖不变。

完整冻结、真实/独立支持和资格未授予，G6/G7不作冻结前置；无新拟合、SEALED读取、行情请求或真实前向启动。此切片仅完成当前同源联合诊断的汇总接入，05保持partial。原汇总中的历史未绑定文字作为其保存时状态保留，不回写过去。
