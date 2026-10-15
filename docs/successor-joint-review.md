# 联合压力的版本化汇总

在已保存证据汇总内选择同前缀联合压力，保存一个新版本。原汇总及其来源、字段和重放不修改。新版本验证费用id、manifest/input、后继/协议和前缀完全相同，归档双方完整载荷，读取校验嵌套原件。

新版本以已绑定的12场景替代“联合压力未绑定”这一缺口，仍明确共同风险和独立区间未准入。原门槛硬FAIL不丢，联合候选硬FAIL保留到G5，默认候选绝对风险硬FAIL保留到G4，其余INCONCLUSIVE。完整冻结未授予，G6/G7仍属于启运后资格缺口，不能成为循环启动前置。

只重算保存结果的汇总，不重新运行模拟器、拟合或采集行情，不占确认性查看或SEALED额度。输入8MiB，方法和代码指纹保存，支持幂等/查询/重启/重放。API：`POST/GET /api/research/successor-evidence-reviews/{id}/joint-review`、`GET /api/research/successor-joint-reviews/{id}`、`POST /api/research/successor-joint-reviews/{id}/replay`。
