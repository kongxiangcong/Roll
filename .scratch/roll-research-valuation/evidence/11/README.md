# 11 研究特征与增量验证协议验收

本票实现及只读验收完成，下一票12。公共接口见[API与语义合同](../../../../docs/research/company-feature-api.md)。四个候选为固定假设修订数量、已陈述失效条件数量、有源下一事件日历天数、当前市场权益相对所选研究情景的比例差；它们不是已验证风险事件或上涨概率。空假设/无日期/blocked估值保持null和原因，不能由缺口补成0。0只适用于有固定完整集合、按定义确实为0的项目。

导出绑定公司、原snapshot/input/core、原事实/假设/审核/报价版本及实际依赖available_at。HISTORICAL_PIT要求原packet历史可得证明；后来取得旧年报和后来生成假设不能倒灌。原材料可消费时间/年龄与披露时间/年龄分开，未知披露时间不补造。下一事件日按Asia/Shanghai，跨UTC午夜仍正确。追加导出和协议有规范JSON/hash/幂等，并发同key同请求只有一个结果。

补充协议只读取已有原实验/冻结模型元数据并固定其hash，不注册新family、不预留预算、不拟合。未绑定原量价模型时DRAFT_UNBOUND，coverage INCONCLUSIVE；协议中固定事件/期限继承、同样本/成本/风险与行业暴露、时间外与purge/embargo、Brier/log-loss/校准、成熟度和停止规则。既有预算、先前失败/中止、原截止日期继续有效。没有执行器/授权/成熟标签与冻结baseline预测绑定时不能拟合，也不声称基本面提升概率。

## 已运行验证

[regression08.txt](regression08.txt)：**11passed92.22秒**，7个本票公开service/API/备份测试，加4个既有不可变快照、报价恢复、报告文件恢复和旧财务特征防穿越回归。没有运行后端宽suite、前端构建或拟合；本票没有前端改动。具体红绿与夹具/环境故障见[commands.md](commands.md)。

覆盖的行为包括：真实0与未知分离；原引用/实际生成时间；后来假设对旧cutoff不可用；同季报两个快照只一份独立原件单位；blocked诊断估值不进入有效数值；概率/权重extra字段拒绝；补充协议与只读HTTP；重算档案/record hash仍拒绝错snapshot；四并发相同key只有一份结果；有源本地今日事件=0天。

## 真实固定资料与保护边界

[real02-receipt.json](real02-receipt.json)为最终源码的真实API-only8031实证。由10的公开Backups克隆新目录 `D:/dsh-proj/Roll/.scratch/rv11-real01`，不覆盖10/09/08或原生产目录。承德露露公司54abcc3d-67c2-453e-83b4-8fdc92b7a292，原snapshot7a430e8b-4172-4598-af21-6fe8600b6b93/core37b71966590cb1cb8d0c2898c4bace4c7ec1bc3b216018d2f941204f22dcac1d，原报告仍PARTIAL/current blocked/baseline conditional。

本次真实当前、旧2025观察与当前HISTORICAL_PIT三份导出分别保存于current-features02/early-features02/strict-features02.json。真实当前快照没有固定经营假设，count/日期均缺失，current gap因blocked缺失；**四项均null，不是零风险或零变化**。6个source roots只是原引用范围，不是6个有效独立成熟样本。coverage02显示3观察、0有效独立原件单位、0独立成熟结果样本，INCONCLUSIVE；protocol02为DRAFT_UNBOUND，原量价baseline未绑定，不伪造训练或改善结果。

实际POST创建导出/补充协议/只读coverage，GET原导出逐字相同，重复幂等返回同记录；额外概率字段422。protected-before02/protected-after02通过既有公共GET比对账户、旧protocol/attempt/model/预算元数据、旧feature计划/快照、能力grant/events；对象相同，摘要57d4a8dba1aad205777a6ef1fe3b93150c216f4eefc021fc517419368c23bbd9。该隔离副本的原协议/模型集合为空，不把空集合比较冒充原生产SEALED/模型内容审计；本票没有读取原生产目录或受保护分片，没有写原概率表/预算/账户权限。

实际公开Backups backup6f64e924-ac81-46dd-bf5d-1fe0db02ad40，7179037字节bundle，恢复到新 `D:/dsh-proj/Roll/.scratch/rv11-restored02`。三份原导出/协议/coverage相等，四规范archive SHA一致；原snapshot、report、delivery完整对象与10一致，account0。首次真实01/恢复fde3dd41及旧导出保留，最终02增加单位/原资料年龄并修本地日历，没有覆盖旧记录或重写旧报告。

真实新model/source-network/auth读取/SEALED读取/fit均0。loopback HTTP仅用于本地公开API。8031为显式当前PYTHONPATH/API-only，无worker/环境文件加载；最终launcher51196/listener23712，精确receipt/api02及模块路径见本目录。只在修源码后核验自身PID/启动时间/命令并重启一次，原07/08/09/10/生产服务未动。日志存在外部store，不将持续增长live日志加入Git。

## 未验证范围与后续

METHOD资料不是现实预测效果，来源/原模型/训练授权未就绪时不会自动创建。没有足够成熟结果、独立性、baseline预测及冻结窗口绑定，coverage不能给PASS。可用当前估值比例差的正向真实场景本票未观察到；真实露露CURRENT仍blocked。12联合A1–A10、真正完整正向报告及两个实际盘后周期仍未完成，不由本票只读导出代替。本票不触发调度、不增加盘后周期或正式资格。
