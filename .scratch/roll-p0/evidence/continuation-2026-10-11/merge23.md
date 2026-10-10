# Ticket 23 独立合并验收（2026-10-11）

结论：本地工程范围独立验收 **PASS**；ticket23 的 Completion 保持 **partial**。两个真实 provider 审阅尚未执行，AT-51 未闭合，24 的依赖继续阻断。METHOD worker、SDK loopback 与本地导出均不构成真实模型审阅、真实研究结项或正式能力。

实现提交 `09a5b7959c6fe6b292f4ec5712015180106de5fc` 基于 `d789870117d59b240e4bb2540e66a2c36461c440`；在20/21工作树清理证据提交 `0aaff2abfdf4ef809770aa9149ee27737fa2e94d` 后，经授权本地 no-ff 合入 `676b5fff2126714c981399ef7d95410de5cd5ffd`。没有推送、清理23待审packet或修改原19、SEALED、个人凭据。既有受保护未跟踪内容保留。

## 工程证据

实现者最终公共API/真实SQLite定向回归 **39 passed / 345.47s / exit 0**，浏览器 **1 passed / 56.6s**，TypeScript/Vite **58 modules / 2.00s / exit 0**。其中9项新增审阅测试覆盖固定材料、引用与复现拒绝、risk_policy独立材料、完成的FAIL/INCONCLUSIVE工程例、取消/超时/共享并发、重启及导出。证据与逐项红绿见[23验收](../23/acceptance.md)。沿用同一轮既有backend/Codex/DeepSeek取证回归，不将多次运行的测试数相加。

另一全新隔离目录运行[独立公共API脚本](independent23.py)，真实SQLite与归档持久化，进程 **exit 0**；[结构化结果](independent23-results.json)为PASS：

- 伪造宿主复现SHA被判为INVALID_OUTPUT，不能产生有效ReviewRecord。正确重试保存完整记录，绑定原材料、模型、配置、源码/工具及复现结果，只提供已列明材料读取和宿主复现两个工具。
- 固定worker提交空异议仍不能消除宿主G7缺口；记录COMPLETE、阻断异议未完成、冻结实验交付INCOMPLETE、初步结论及NOT_GRANTED独立保存。原验证记录没有被审阅改写；人工独立复核为false，账户版本0、前向未启动。
- 完成终点与检查的METHOD FAIL和INCONCLUSIVE均可保存审阅并完成本地导出；失败或不确定结论不会被模型意见改成PASS，也不授予能力。
- 审阅与acquisition共享并发槽；占用时两个公共入口均拒绝第二任务。之后切换后端不改变已冻结的CODEX任务；取消、无可用DeepSeek配置的关联重试及超时分别保存CANCELLED、UNAVAILABLE、TIMED_OUT，终止进程清单为空。
- 重启后原ReviewRun、当前交付状态和两个尝试保持一致；完整ZIP包含相关registry源码及冻结输入的forecasts。损坏自己的材料归档时读取与导出均409；恢复字节后再次读取一致。
- METHOD工厂在生产环境创建应用时拒绝；生产加载既有METHOD宿主材料也409。原审阅记录仍显式标为 `METHOD_CASE_TECHNICAL_REVIEW`。独立过程仅使用自有synthetic配置与本地固定worker，外部传输0，真实provider调用false。

最终截图 `../23/technical-review.png` 已检查，审阅进度、阻断问题、真实交付未完成、NOT_GRANTED及“未经人工独立复核”可读。截图局部显示CODEX/gpt-6.1-sol不能单独证明真实provider调用；通过[只读浏览器记录核对](merge23-browser-boundary.json)确认该固定worker记录显式METHOD边界及工程局限。risk_policy材料绑定自己的evaluation/input/dependency和五门槛复现，相关工程测试见实现者回执；未借profit审阅签发权限，funding.py/risk_policy.py未修改。

## 保全与源码核对

[静态校验脚本](verify23-assets.py)仅做文件与只读SQLite核对，不启动应用或provider。[合并前](merge23-assets-before.json)与[合并后](merge23-assets-after.json)均PASS：

- 已停止的浏览器METHOD源/根保全640文件、36,711,341字节，审批预览源/根保全13文件、1,979,209字节，逐件SHA与长度一致。synthetic auth明确排除；保全中历史building备份件不被当作完整备份证明。
- 最终源码快照与集成内容相符；12个19 model-code依赖原长度/SHA不变。待审批models/execution/shadow/statistics/validation五份源码与packet内容/指纹相同。
- 永久审批清单位于 `D:\dsh-proj\Roll\.roll-data\implementation-evidence\23\provider-approval\provider-material-manifest.json`，与待审预览字节相同，SHA256为 `c2cfc640530d008b3aca3e18a32154be43550bd136fa59c129b9009169994204`；材料指纹 `35e42b0da239e415e2b7e3f3f0c9243d4e32a3e3bc02ceac92a92b17559ac9da`。
- 根23实际一致副本只读查询 `actual_review_runs=0`。未打开原19，未新增拟合、预算、SEALED消费或实际前向。当前实际诊断仍G4/G5 FAIL，其余INCONCLUSIVE。

新的独立METHOD目录436文件、25,684,265字节保存[逐件清单](independent23-profile-manifest.json)，进程已停止，synthetic-auth.json排除；运行件留在根 `.roll-data/implementation-evidence/23/independent-method-profile`。完整材料与运行数据库不提交源码仓库。

## 未完成边界

此前自动审批审查拒绝实际材料分别发送至OpenAI Codex及DeepSeek，原因是没有获得这批材料向这两个具体目的地外发的明确授权。拒绝发生在启动前，父代理已提出材料与目的地审批；本次没有执行 `actual-review.py`、重试外发或运行真实provider。实际审阅数和外发数均为0，待用户明确批准后另行执行并记录两后端证据。

本提交只追加合并与独立验收证据，不修改tracker进度。20/21/22已完成工程范围；23保持partial，24链仍blocked，30按其独立工程证据收口且未启动真实producer。工程审阅完成不能补足真实终点、必需检查、G1—G7或正式资格。
