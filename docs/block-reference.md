# 区块统计数值参照

研究报告的“概率计算独立库核验”下，先选择或生成保存的概率核验，再展开“区块统计独立库核验”。显式运行会保存归档；查询和工件重放不需要 arch 环境，也不重新抽样。

仅在独立 Python 环境安装 `backend/requirements-arch-reference.lock`，将其可执行文件路径设置为 `ROLL_ARCH_PYTHON`。主业务环境不安装 arch。锁定 arch 8.0.0（NCSA）；原冻结 `research/statistics.py` 不修改。实际运行无网络、无拟合、无 SEALED 读取，30 秒超时、10,000 日历位置上限及 8 MiB 输出上限。

复用选定概率核验归档的同一截止、同一成熟事件和完整 CAL 日历。每个证券/日期的成对 Brier 改善为基率误差平方减候选误差平方。同日证券一起抽取。总体统计量为日期等权的同日均值，条件统计量为成员分数总和除以成员数总和（p≥0.60）；观察到的非成员日期为空组，未观察到成熟事件的日期为未知，二者不能互换。完整日历有任何未知时，区间保持不足，禁止压缩日期。

预登记方法见 `backend/src/roll/research/reference/block-reference-v1.json`。20/40 日非循环移动区块、2,000 次、seed 1701，尾块按原日历长度截断。下端点采用第 floor(.05×1999) 顺序统计量，上端点采用第 ceil(.95×1999) 个；每端为单侧 95%，合起来是中央 90%，不能标成双侧 95%。

arch 使用 NumPy default_rng/PCG64，冻结方法使用 Python MT19937；相同 seed 不保证相同抽样。每次 arch 实际生成的公开 `index` 用于重算原始日期组公式并核验到绝对容差 1e-12，同时记录全部索引序列 SHA、首个索引和端点差异。不同抽样端点仅作描述，不能以逐次不一致判断实现错误。人工常数样本还对照冻结方法的解析值；人工变化、多证券、空条件组样本单列 METHOD，绝不补入来源日历。

每份报告保存来源概率 manifest、原始日期组、预登记方法、冻结/参照代码指纹、实际库及数值依赖版本、结果 manifest。幂等键绑定命令；相同键不同内容拒绝。重放只核验原件哈希，假设、独立有效性、资格始终未授予。

API：`POST/GET /api/research/probability-references/{id}/block-reference`；`GET /api/research/block-references/{id}`；`POST /api/research/block-references/{id}/replay`。
