# Fuyao 实际来源补充与19边界

基于3b12daf，在用户提供 root `.env` 两项凭据后按implement-spec/TDD继续。主接缝沿已确认FastAPI、真实SQLite/隔离raw+Parquet；无新依赖、SDK复制或泛化框架。只读内部使用密钥，从未输出/复制/归档 `.env`。

**Fuyao来源工程完成；19仍partial/needs-info，20未解锁。** 实际可用量价/金额与原始公司行为增加覆盖，不能补历史无修订/PIT、历史状态/完整行为/以前规则。保持原协议、失败与封存UNPROVEN，原CAL40最多20成熟仍不能满足每类20；没有实际模型、校准、概率、后继协议或前向起点。

## 实际范围

[最终真实API/SQLite/重启证据](real-acceptance.json)：600519在2023-01-01—2026-09-30取得908 RAW/908当前前复权、7原始公司行为及1报价；2026各181股票日线量额可用，较早1454 RAW/qfq行日历未适配。三个固定背景各181行；指数点位不与总成交额作个股VWAP比较，不能进入股票模型。股票运行PARTIAL（逐证券报价时点/当前状态未知），背景完成仅表示获取处理完成。原件/Parquet逐SHA一致、两次进程生命周期GET相等、离线重放0联网、账户version0事实不变；只增加显式watch成员。

[原初真实源记录](real-acceptance-initial.json)保留指数VWAP误用的规范化错误；[规范化SHARE前记录](real-acceptance-before-share-unit.json)保留初单位名称。新样本不覆盖旧事实。量价输入适配与公开查询造成与旧封存元数据交叠，已按17记录[输入暴露](input-exposure.json)，未训练、算封存标签或读最终策略结果；独立性不恢复。[官方文档SHA](documentation-manifest.json)及原件留在运行目录。

## 工程与浏览器

TDD公开切片：daily_source拒绝422→RAW/qfq/股数/CNY与原档案回放；adjustment_source422→DATE除权/现金/未知披露；quote_source422→逐证券时点null；null时间消费者FAILED→明确MONITORING_UNAVAILABLE/估值资产未知；指数点位误VWAP→正确背景局限；实际视觉检查除权待核误称公告/遗漏除权日→原始事项文案与已知除权日。固定权限/限流HTTP200业务失败、缺凭据0外部调用、反射密钥归档前拒绝、错对象、失效/范围/单位/时点门禁一同验证。METHOD只证明工程，不成为实际统计数据。

[相关66案例](backend-related.txt)64passed/2failed（164.47s）。失败均是既有固定08:30/10:00消费截止早于实际收到时间，已在[原root代码同两例](backend-baseline-comparison.txt)复现2failed/12deselected（6.65s）；本分支不修改既有时间断言或生产时点门禁。后续最终专项及视觉修复/构建证据单列；不能将其相加称整仓全绿。父root另有完整baseline验证，按父记录保留。

首次Chrome使用root `.venv` 的editable源码而未设置worktree PYTHONPATH，页面已呈现新控制但后端422不支持Fuyao；[原报告](browser-initial-results.json)、[页面](browser-initial-context.md)留存，属于启动接缝错误。改为明确worktree源码再验真实Chrome，不改产品断言；[文案修复前1passed报告](browser-before-event-message-results.json)与[原图](browser-before-event-message.png)保留，最终图/报告另列。第一次实取API smoke误将watch200预期201，只发生watchADD后停止，未取数；改正harness后完整取得证据。

## 保全与下一步

全部自有实际/方法SQLite、原件/Parquet、过程stdout、文档和截图保持原目录，最后逐文件bytes/SHA/原路径见runtime-preservation.json；密钥及用户 `.env` 不在保全或源码范围。任务07/08/18/19只追加事实，不改变原结论；execution-status由父维护。后继协议必须在真实必需输入支持成立后才可登记，不能靠更长当前修订日线、缩域或降低统计阈值把原失败变成通过。


最终同源码：Fuyao9项及既有市场15项共[24passed](backend-final24.txt)51.73s。实际安装Chrome[1passed](browser-final.txt)14.5s，已核对来源三个控制、canonical SHARE股数/金额展示、已知除权DATE与原始事项文案、逐证券报价时点未证实、原件回放0联网及账户version0不变；[最终报告](browser-final-results.json)、[实际运行](browser-final-actual.json)、[截图](browser-final.png)。TypeScript/Vite53模块构建通过，最终构建输出另留。


父定向检查发现信封code可携任意文本：新增string/bool code公开测试2红后，typed int且拒绝bool的稳定错误通过，11项专项通过（24.68s）。随后另验证JSON转义反射密钥：固定escaped回显红→归档前同时检查原bytes和JSON解码值，最终12项专项结果另列。实际各成功原件code均为数值0，不修改量价映射或旧原件；这两项边界修复属于源安全输入验证。


最终边界专项[12passed](backend-final12.txt)26.09s；原24项/64+2及Chrome/构建证据分别留存，不相加为一个HEAD完整suite。


合最新integration23e6556（12真实接入及rootbaseline记录）得3916c0f，新增来源12项与环境加载3项合计[15passed](backend-merged15.txt)38.10s。使用ROLL_ENV=test和隔离真实SQLite，确认测试宿主不隐式读取root凭据；工作树不新增个人.env副本。已提交源31f5f12；此证据只更新merge后结果，不重写原运行指纹。
