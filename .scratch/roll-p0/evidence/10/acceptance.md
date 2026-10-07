# 10 验收记录

日期：2026-10-07。**10 自身切片通过，Completion: complete。** 合成账户/固定方法样例不是用户真实亏损或正式资格证据。

环境：Windows 11、Python 3.13.12 / SQLite 3.50.4、Node 25.8.1 / npm 11.11.0；沿用 01 的实际锁文件 FastAPI/React/Vite/Playwright 依赖，无新增依赖。工作树 `codex/roll-p0-10` 从已验收 17ca07d 开始；实施提交84ed421后已合入最新集成tip7caa9a5，合并提交3b37f56无冲突，只带入父代理的执行状态与缓存忽略规则，没有代码/依赖变化，无需重复相同测试。

| 验收层次 | 实际命令 | 结果/证据 |
|---|---|---|
| FastAPI＋真实 SQLite＋既有真实恢复进程 | backend `.venv/Scripts/python -X utf8 -m pytest -q` | 60 passed，18.80s；其中 10 的 38 案例，既有 01 的 22 案例。保留一个已知 Starlette/httpx 弃用提醒。[输出](backend-test.txt) |
| 真实 Chrome 与 Uvicorn/Vite、临时 SQLite | frontend `ROLL_BROWSER_CHANNEL=chrome ROLL_TEST_API_PORT=8030 ROLL_TEST_WEB_PORT=5194 npm run test:e2e` | 2 passed，11.0s；既有基线＋资金路径。[输出](browser-test.txt)、[报告](browser-result.json)、[紧凑三状态截图](funding-three-states.png) |
| 前端构建 | frontend `npm run build` | TypeScript/Vite成功，36 modules，1.80s。[输出](frontend-build.txt) |

## 主要场景

- AT-32：已建账户并确认资金后，技术状态仍 UNGRANTED；模式 FORMAL / LLM confidence 0.99 请求 BUY、ADD、HOLD、REDUCE、EXIT、判断型 WAIT，各返回 403 TECHNICAL_CAPABILITY_UNGRANTED；资金/部署不授资格。
- AT-33：LLM probability 0.90、origin LLM 不能写正式概率，403；实际账户事实查询与原事件逐项一致。无用观察文案生成判断的路径。
- AT-60：未合格的 HOLD/REDUCE/EXIT/判断型 WAIT 与 BUY/ADD 共用服务端资格拒绝；今天无持有/卖出/判断型等待输出，未以“风险”绕过。浏览器另外请求 HOLD 验证403且仍可查看账本。通知尚不存在，由28实际出口联验，不能把此页面验收算作通知通过。
- 三状态：资金、技术资格和健康独立查询，今天分别显示已确认资金、技术资格未授予和账户服务在线；未配置模型/市场不影响账户事实。浏览器用本人输入字段（合成验收资金100000/总暴露60000/单票20000/保留40000/阈值5000）保存后刷新/导航可查，暂停追加版本、旧版本仍显示原确认。未要求统计参数、投资人格或报告。
- 同键4线程重试只得同一 receipt_id；不同键两页面旧版并发一200一409。后续版本推进后原幂等命令仍返原版本；同键异内容409，版本及原历史保持。当前查询已采用缩小暴露/撤回状态；扩大金额和重启不解除资金暂停，不改 origin/baseline。
- 公式、字段语义和独立手算预期见 [冻结契约](../../../../docs/funding-contract.md)。出入金排除收益；收入/待结算转换、实现/未实现、费用前价格损益与买费只扣一次、阈值前/等于/超过、最大18位整数的0.01分差、缩小阈值均通过。未知费用/估值陈旧/不守恒返回RESTRICTED，实际剩余额度不猜零。
- 样例10月6日恰达阈值5000后，重新创建应用/数据库连接，10月7日反弹且扩大金额/阈值，历史H=5000/已触发暂停保持。后来缺基线返回受限同时保留已知基线和触发。不同scope/基线/SHADOW或浮点材料拒绝且无样例入账。
- 生产无 `/api/testing/funding-loss-samples`（404）。测试环境样例只写独立方法历史，ACCOUNT_CONDITIONAL / UNTRUSTED_SAMPLE / METHOD_VALIDATION；不更新 ACTUAL 账户、资金实际损失或资格。正式资金始终 PENDING_FACTS/剩余null。

TDD：首条资金GET红（缺version）→持久化路径绿；六种正式动作红404→门禁403绿；方法接口红404→公式绿；跨重启反弹红H归零→SQLite样例历史绿；后续缺基线红409→受限并保留历史绿。UI先红缺资金区，实施后定位器宽匹配失败，改精确可访问名称后两流程绿。新增已建账户的门禁测试曾错误期待空事件，修为与确认前原事件逐项一致后通过。失败未计作通过。

结构：只新增 decisions/funding、实际复用的FundingStatus、设置页与一份样式；未新增依赖、grant/action表、自动恢复、后台或通用框架。资金表用组件迁移标记，不占用02的账户PRAGMA版本。

## 留给后续责任票

09 提供带版本的实际范围估值/现金流（费用前PnL与费用后成本区别须按契约适配）；20 影子保持隔离；25 将当前资金、09事实和技术资格取交集；27 实际阈值触发、缩权、按原因恢复以及真实动作/资格限制原子联验。24/28 检查真实资格签发/通知出口。固定方法样例并未证明这些尚不存在的生产出口。上述联验不是10隐含前置；追踪整条需求保持部分。
