# 06 验收：有限名单、交易日与规则范围

日期：2026-10-07。本票完成 AT-17/AT-18 的名单、规则与状态查询边界；不签发模型资格、不生成新动作/意向。分诊保持 ready-for-agent，Completion 单独记录 complete。25/26 的账户交易权限联合门禁仍归各自责任票。

## 实际环境与结果

Windows、Python3.13.12、01已锁定的 FastAPI0.141.1 / Uvicorn0.52.4 / pytest9.0.2 / httpx0.28.1，SQLite为Python自带本地库，WAL与synchronous=FULL。前端React19.2.4 / TypeScript5.9.3 / Vite7.3.1 / Playwright1.58.2，使用实际Chrome。无新增运行依赖、无证券全市场采集框架。

- FastAPI/真实SQLite完整回归：29 passed（22个01基线/真实进程恢复案例 + 7个06应用案例）。原始输出 [backend-test.txt](backend-test.txt)；httpx与新版Starlette有已知弃用提示，测试实际通过，本票没有为消除提示引入另一套HTTP库。
- TypeScript与Vite生产构建通过：[frontend-build.txt](frontend-build.txt)。
- API8026 / Web5186，独立临时ROLL_DATA_DIR，实际Chrome核心流程2 passed（01 + 06），输出 [browser-test.txt](browser-test.txt)、[JSON结果](browser-result.json)、[页面截图](market-watch-history-calendar.png)。
- 另外启动独立同端口的进程/数据库，以21只BSE实际持仓作为初始确认输入，Chrome1 passed：[JSON结果](overflow-browser-result.json)、[21只资产截图](market-21-holdings.png)。单独配置的原因是已确认初始账户不能为另一测试覆盖重置，不引入测试专用账户写入后门。
- [固定来源回放](fixed-rule-calendar-replay.json) 保存8项实际公共查询结果。它是应用对真实归档原件的确定性回放，不是盘中实时行情/停牌获取或真实前向档案。

## 输入、预期与实际

| 场景 | 输入和预期 | 实际/证据 |
|---|---|---|
| 自动持仓、增删关注、重启 | BSE:920001实际持仓100，新增SSE:600519；取消持仓关注不删资产；重建应用后旧版本原值可查 | FastAPI案例通过，SQLite重开后成员/旧快照相同；Chrome确认300股存量并增删关注后仍显示持仓 |
| 20只上限与21只资产 | 21只BSE持仓自动并集，所有资产显示，新增第22个成员409 WATCH_LIMIT | 应用与Chrome均完整显示21只，末只920020可见，新增关注受限且无隐藏 |
| 名单范围与指数 | 名单外研究/观察403；当前名单允许获取范围但仍NOT_GRANTED/NONE；固定指数不能加关注或取得个股研究/普通股票身份 | 公共FastAPI案例及Chrome外部研究请求403；背景列表无交易能力 |
| 身份明确与分离权限 | 600519代码不自动推定板块。明确SSE/MAIN/STOCK、名称与券商详情依据才记录用户核对；规则支持不证明permission OPEN | 未核对时UNKNOWN/UNSUPPORTED；核对后ADAPTED但权限UNKNOWN，持仓仍保留。Chrome600000主板已适配、账户NOT_OPEN明确可见；确认OPEN也仍受限于当前状态未知/模型资格未授予 |
| 成员历史与知识时间 | 两次账户确认期间未查询名单；后确认身份不得改写原身份知识 | 账户版本1/2/3均在成员历史保留，原confirmed_at与实际materialized_at分开；当时身份仍null。后续快照和历史关注成员原值可查；没有补写StageSnapshot、行情或覆盖 |
| 休市及调休边界 | SSE/SZSE 10月7休市，下次10月8；10月10政府调休仍为交易所周末休市 | 两个交易所实际原件与应用案例通过；Chrome休市/下一交易日可見 |
| 时区与阶段 | UTC04:00转上海12:00午休；15:10为盘后固定价格；无时区拒绝；规则7月6前时段不冒用 | 固定来源回放/公共查询案例通过，原件含2026阶段规则 |
| 数量、价格与可卖日期 | STAR200股起、1股增量、限价10万/市价5万，CHINEXT100股倍数、限价30万/市价15万，tick0.01；9月30买入最早10月8可卖 | 原件条款与应用案例相符；规则JSON含版本、生效/适配范围、来源、必需当前状态与用途限制；未知2027日历不猜12月31后可卖日 |
| 未适配资产与未知状态 | BSE、未知板块、其他类型、2027或7月6前规则未知/未适配；当前停牌/风险警示/上市阶段/除权尚未取得 | API和页面明确范围/未知/限制；BSE原页访问403或抓取策略循环，没有伪造日历。持仓与规则/权限信息仍可查 |

## 实际来源与覆盖

官方原件、发布页及逐字节指纹见 [sources.json](../../../../backend/src/roll/market/reference/sources.json)，接口及具体条款见 [市场契约](../../../../docs/market-contract.md)。实际请求取得沪深2026全年休市页、2026-07-06生效规则正文、SSE暂缓条款附件及补充T+1说明。取得时间2026-10-07T14:54—15:07Z（北京时间22:54—23:07），不是证券当前行情时点。

规则实际覆盖：普通人民币现金账户A股，沪主板/科创板、深主板/创业板，2026-07-06至2026-12-31基本数量/价格/日期规则。日历实际覆盖：SSE/SZSE2026年度安排。每次启动将原件SHA核对后复制至隔离运行目录raw，并登记同一SQLite；归档下载API的原字节与元数据SHA一致。

明确未验证/未适配：BSE规则与日历、其他年份/证券类型、证券当前特殊状态、临时停市实时源、精细竞价执行、实际券商佣金/最低收费与税费估计。费用未知不作零费。年度日历不证明盘中未临时停市；当前证券状态UNKNOWN不虚构数据来源，也不禁止展示已知实际资产。新增关注不授予模型资格，scope成功不授予资金或账户权限。

## 复现与职责

在backend运行 `.venv/Scripts/python.exe -m pytest -q --basetemp .roll-data/pytest-06`。在frontend设置ROLL_TEST_API_PORT=8026、ROLL_TEST_WEB_PORT=5186、ROLL_BROWSER_CHANNEL=chrome，运行 `npm run build` 和 `npm run test:e2e`；21只独立样例运行 `npx playwright test --config playwright.overflow.config.ts`。每次Playwright运行清理test-results，先保存证据再运行下一独立样例。

新增两项业务实现文件、实际使用的归档原件、一个页面/样式与公用API路由；市场表只幂等创建，不竞争02全局user_version=2。Ledger仅追加公开只读versions查询。没有预造07取证、研究、资格或动作模块。07在单证券获取前消费check_scope，并另取得当前证券状态；15/18处理已定义观察/样本时序；25/26联验新动作及执行意向的权限边界。
