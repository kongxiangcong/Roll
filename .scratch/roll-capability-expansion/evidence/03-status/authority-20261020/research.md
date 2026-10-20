# 03 官方状态契约核实（2026-10-20）

结论：找到了并下载了官方客户端 `getFpphaseText` 的完整显示映射，以及当前 IS124 3.70 / IS120 0.63 原始接口规范。可据此新增**盘后阶段显示**；仍不足以将现有 `STATUS_A` / `tradephase` / `cpxxprodusta` 判成完整有效状态、风险子类型或否定覆盖。03 不应因此 complete。产品代码、旧冻结、旧 CLOSED 预算均未修改。

## 来源链与可复核定位

1. [600362 公司页](https://www.sse.com.cn/assortment/stock/list/info/company/index.shtml?COMPANY_CODE=600362)，`08.raw` SHA256 `d374164f4824cc4f9c1e97241934ff063099b10dd36431a9a6bc5ff472a2d90f`。第758行显式加载 search_HQ / search_stocksDepositoryReceipts，第962行 require 主模块 main_2021。
2. [main_2021.js](https://www.sse.com.cn/xhtml/js/app/main_2021.js)，`03.raw` SHA256 `c7c1438a3cb3405e9f431e4c745415b3c95c707dd502555bab6bc2c7ee45a0e6`，`searchCommon_path` 指向 `/xhtml/home/2021public/querySearch/search_common_2021`，并在页面模块前加载该依赖。
3. [search_common_2021.js](https://www.sse.com.cn/xhtml/home/2021public/querySearch/search_common_2021.js)，`04.raw` 63991字节，SHA256 `5e30aa03c402eecc759de04b4b683548355a144861bc8cc814018150c6a6070e`。
   - `kcbShowIconFlag` 第757—778行仅检查零基索引7的U、8的W、4的Y，分别拼接U/W/D简称后缀。函数未读取ST子类型、风险生效日、停复牌。`09.raw` 第6654行将 `data.STATUS_A` 传入此函数；不得把空后缀当作无风险。
   - `getTradephaseText` 第2258—2295行先去空白，再只取第一字符：S/C/D/T/B/E/P/M/N/U 对应开市前/集合竞价/集合竞价结束/连续竞价/午间休市/闭市/停牌/熔断(可恢复)/熔断(至闭市)/收盘集合竞价。此函数没有解释其余位置；未知字符原样返回，不能视作正常。
   - `getFpphaseText` 第2302—2309行仅取数组首位：I 开市前；A 集中撮合；H 连续交易；D 闭市；F 停牌；其他或无首位显示 `--`。这只是客户端阶段显示契约，不含复牌日期、生效区间、全状态或否定覆盖。
4. [search_stocksDepositoryReceipts_2021.js](https://www.sse.com.cn/xhtml/home/2021public/querySearch/search_stocksDepositoryReceipts_2021.js)，`09.raw` 277193字节 SHA256 `478fb2a72fc5a3725088adb208756e88171f79628956a9f5ca67c900d37def2f`，与既有冻结原件一致。公司 `getMarketIndex` exact select包含fp_phase，第3747—3748行取 `data[23]` 分字再调 getFpphaseText。所以该映射可绑定既有字段顺序，不能外推到别的接口。
5. 上次线索 [sse_menufun_2021.js](https://www.sse.com.cn/xhtml/js/app/sse_menufun_2021.js) 本次下载为 `02.raw` SHA256 `786579e2a73e0e4ffeed2fa04f9f84bc4bbf1a7048ea552ca17f44c0c5d5d999`，无上述三个函数定义；真正定义来自 main 的公共查询依赖。

## 下载的当前正式接口规范

[官方技术接口目录](https://www.sse.com.cn/services/tradingtech/data/) `05.raw` SHA256 `9aa03440db2a3da6490cfc795075b77ed2f8d6ea379c7e5c7f2ea0348cd50218` 第317和344行分别链接2026-09-18发布的两份规范：

- [IS124 3.70](https://www.sse.com.cn/services/tradingtech/data/c/10832592/files/98a374cfa623415181710783a1718c28.pdf)：`06.raw` 932600字节 SHA256 `fcf039131f1e70f0f6d29fe51cc4b55554c7c628f7ff96d039ae7d1c7d1e5fd5`。PDF物理14—18页（印刷7—11页）2.8定义 cpxx0201MMDD.txt：开市前发布，MDGW/ztDisk渠道，包含停牌产品、不含非交易信息和未发行上市产品；第17—18页产品状态20位含第1位首日上市、第2位除权、第3位除息、第4位D/S/P/T/U产品类别。PDF物理70—71页（印刷63—64页）定义 mktdt00 的 TradingPhaseCode：第2位可否正常交易、第3位上市、第4位接受订单，且闭市保持闭市前可交易状态、第4位仅交易时段有效。**这些定义属于文件渠道；没有找到将其等同到网站JSON字段的官方声明。**
- [IS120 STEP 0.63](https://www.sse.com.cn/services/tradingtech/data/c/10832589/files/5ea26a2949c943a7ae2c9838c4c252bf.pdf)：`07.raw` 485461字节 SHA256 `ff940e1c7ffce1ecea93438642f126d892c8f6790f8713c23674120578bac60b`。PDF物理30—32页（印刷24—26页）tag8538按SecurityType/MDStreamID分支定义，01/MD002—004与盘后MD102分别处理；物理35页（印刷29页）进一步说明盘后I/A/H/D/F与对应条目。该协议有登录、会话、消息长度及校验和，不能用下载到规范代替收到真实网关数据，也不能假定现有网站JSON已满足其完整性条件。

两份PDF均用既有 pypdfium2 5.14.0 环境逐页提取为 `06-text.txt` / `07-text.txt`，只是检索衍生件，原件字节单独保留。首次尝试fitz/pypdf未安装，未安装任何依赖；不影响原件真实性。

## 一次真实同证券观察

发出前已在 plan.md 固定原exact select。`10.raw` 是真实直接HTTP GET 200，不是夹具，也未调用产品采集器或伪造回执。

- URL和全部headers/开始结束时刻见 requests.json 第10条；收到时刻2026-10-20T00:11:26.484062+00:00（上海08:11:26）；原件404字节 SHA256 `6a96cead1b5f1f76d59149872218c874797117c48163f98221f66fb3193018aa`。
- code=600362，date=20261019，time=162901；24字段与固定select一致；tradephase原值 `E110    `；cpxxprodusta原值 `   D  F  N          `；fp_phase原值 `D0      `。
- 依据官方客户端**只解释fp_phase首位D→闭市显示**；剩余位0、产品能否使用盘后交易、风险警示/复牌/交易日整体正常均未由该显示函数证明。响应报告日期是前一日，不得伪造成2026-10-20实时或当日状态，也不得仅凭E/D推定行情完整。
- 该样本只覆盖D正向显示，I/A/H/F及未知/损坏边界只能由契约测试验证，不能称真实覆盖全枚举。HTTP响应与规范来自同一交易所，不构成独立交叉来源。

## 预算、失败和余缺

`requests.json`保留10条执行记录：第1条为沙箱套接字权限拒绝（0字节，未获HTTP响应），其后9条真实HTTP均200；累计记录墙钟45.80034秒，解码字节1867717。未重试真实HTTP请求，未重开旧预算，尚余预算主动封口不用。两次PDF已完整保存后控制台预览因GBK编码不能打印二进制替代符而exit1；requests.json与原件已经写成，SHA/长度复核通过，此失败不是下载失败，也未因此重取PDF。另一次UTF8记录读取默认GBK在请求前失败，修正读取编码后才发出请求。

仍缺：网站STATUS_A/cpxxprodusta/剩余tradephase位正式等价声明；完整风险子类型及实施/撤销时间；目标日期/对象范围完整覆盖声明；真正MDGW/ztDisk材料及适用授权或有同等明确契约的可公开原件；历史状态不可变版本链。空名单/目标未出现/日期未知/旧缓存/只见公司“上市”均不能填这些缺口。建议实施最小新增参考模块，仅输出官方阶段显示与原值、依据、接收时间、日期和未知边界；不要改旧冻结parser或把03标complete。

本次所有写入仅在本新目录。未联网下载市场全表，未触碰账户、训练、拟合、SEALED、正式资格或真实前向启动。
