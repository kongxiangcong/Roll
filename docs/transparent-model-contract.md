# 透明模型与研究预测（19）

`POST /api/research/protocols/{id}/models` 接受 `basis` 与 `purpose`（默认 RESEARCH；明确合成输入才能用 METHOD_VALIDATION）。固定PRICE_VOLUME_LOGIT_V1、四特征、λ=1、20交易日费用后事件；无模型搜索/LLM信心/客户端概率/参数调优入口。模型尝试先进入17的PRIMARY_FIT，失败和方法拟合均占五次谱系预算；CALIBRATION最多一次，包括失败。有限100步Newton求解、总60秒上限，计算不持有账户SQLite事务。模型自有两表不改变Ledger全局schema2。

宿主消费18同一 `execution-support` 及17真实允许DEV/CAL分片。只用成熟、可评分、标签可得的唯一观察日记录、原预登记NEXT_OPEN/100%成交/基础费用。跨标签窗、重复日期/情景、未知标签、缺日线/完成/单位/消费知识时点、历史PIT不明全部留下排除原因；校准前20日只提供特征上下文，绝不作为校准标签。21行回看须符合06已归档日历，不越缺行。没有标签不拟合、不保存中性概率，失败继续保留全attempt manifest。

四特征分别是RAW收盘5/20日回报、20日逐日RAW回报总体标准差、当前报告股数/之前20日平均股数的对数；价格与股数先按Decimal源字符串解析，特征是无量纲浮点数。开发窗独立拟合均值/总体标准差（恒定列scale1）、带非截距λ=1二范数的二项总负对数似然。代码规范LF的SHA、特征定义、标准化、权重、开发观察日期、原18执行输入SHA、协议/数据/分片指纹全部保存。

先归档开发模型和校准窗时间外原模型预测，再登记唯一截距校准。校准斜率固定1，不回写原预测；校准后使用同一校准窗的Brier/log loss、ROC和固定五箱只是拟合内描述，尚无独立校准验证。每类20、每个占用箱20、入选40、有效20日期限依赖块30的原条件保持。当前原CAL40最多20成熟标签，无法满足两类各20；不因数值拟合成功降低阈值。METHOD工件标记 METHOD_ARTIFACT_ONLY、NOT_GRANTED，不是实际研究模型或完整协议冻结。

`GET /protocols/{id}/models`、`GET /models/{id}` 保留原失败/工件。`POST /models/{id}/forecasts` 只接受固定CAL观察日及basis，失败409，非CAL（包括SEALED）403。只有方法工件可作本票工程预测，明确模拟完成时钟与实际归档/消费时刻不同，旧观察日不是当时曾发布的真实预测。ForecastBundle保存证券、事件20日、观察/消费知识截止、FeatureSnapshot原SHA、模型/校准/协议/数据/代码指纹、固定执行/成本/范围/支持/不确定性。开发收益上下界/中位是已知METHOD逐单费用后情景，非置信区间或未来财富分布。

CASH保持零暴露/零收益、事件概率空；START_HOLD显示开发事件基准频率和固定初始持有政策，MA5/20显示固定信号、不冒充校准概率。开发/校准逐机会候选和MA对照共用原18成本/执行SHA。重叠20日逐单收益不能串成连续NAV；连续初始持有、可比组合NAV/回撤和正式G3/G5证据尚未完成，20及真实支持不足分别保留。

`GET /forecasts/{id}` 与 `POST /forecasts/{id}/replay` 用原可靠档案/模型权重/校准器/过滤分片重新计算特征和预测，联网0、不训练或重新搜参、不读取最新市场或SEALED。原算法SHA不同409，原工件保留；所有原件SHA校验，附件下载/nosniff。METHOD和实际失败不会改真实账户、资格、正式版本、动作或前向起点；完整实验freeze仍由17拒绝，20/21各自后续。

校准方法的隔离原则和Brier不足以证明校准，参考[scikit-learn官方校准说明](https://scikit-learn.org/stable/modules/calibration.html)（本次读取1.9.1文档）。本票纯数学实现，无scikit-learn或新依赖。
