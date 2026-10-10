# Choice 官方数据能力调研（2026-10-10）

## 判断范围与结论

按用户本轮明确更正评估：**寻找可补充 ticket 19 的旧 PIT 档案，而非评估现在向前积累**。本报告不修改票据、既有采集任务、实验预算或资格。

**Choice 已证实能提供丰富的历史业务数据、部分财报更正前版本和历史公告线索；尚未证实普通终端／EmQuantAPI 能提供 ticket 19 所需的旧日线／状态／权益的当时可得版本及完整修订链。因此可以作为补缺来源和历史数据库服务的询证对象，不能把“能查历史日期”当成“已满足旧 PIT”。** 需要厂商交付具体档案样本及时间／版本语义后再判断；研究窗口、训练／校准／冻结及资格另属 Roll 自身工作。

## 官方来源与取证

- [最新 Python HTML 使用手册](https://quantapi.eastmoney.com/Upload/EMQuantAPI_Python.html)：2026-09-24 发布的 2.7.7.0；本轮网页读取成功。公开 [命令生成入口](https://quantapi.eastmoney.com/Cmd/ChoiceSerialSection) 重定向至登录，不能仅依赖该入口判断“没有字段”。
- [官方安装说明](https://quantapi.eastmoney.com/AIGuide/Install?from=client) 明确链接到 [官方完整 Skill ZIP](https://mxapi.eastmoney.com/quantapi/doc/choice-quantapi-skill.zip)。web 工具读取 mxapi Markdown 失败，Python urllib 直接读取 ZIP 成功；只读文档，没有安装或执行包内代码。
- [官方 API 能力介绍](https://quantapi.eastmoney.com/AIGuide/PromotionPage?from=web) 明示开通量化接口权限需联系客户经理／官方客服。购买终端不应被推断为已具备全部 API 权限。
- [官方终端许可协议](https://choice.eastmoney.com/html/userprotocol/userprotocol.html) 的 2.4 指出其他服务可能另有条款。公开终端条款不能替代用户具体 API 合同的本地存储、派生研究、长期留存、导出、备份及共享权限证明。
- [官方数据库服务](https://choice.eastmoney.com/product/datacenter) 提供数据库交付、多种传输方式及个性化服务；这是向厂商询证历史原始档案、入库／修改日志或定制导出的合理产品入口，页面本身没有 PIT 完整性或历史修订链承诺。

原始 ZIP 保存在 `source/choice-quantapi-skill.zip`。复核下载完成 UTC：2026-10-10T06:00:54.167771+00:00；2,988,004 字节；SHA256：`0b7c98e71353ac776e5c50d1f6e1f5ed67bb531556fbb16a4fc6a7e45d54b569`；服务端 Last-Modified：2026-09-30 07:51:52 GMT；包内 VERSION：1.0.0。两次下载 SHA 相同。`source/manifest.json` 记录 URL、取证时间和所选字典文件哈希，`source/dictionary/` 是从原始 ZIP 按固定名单提取的官方文档原字节，不是模型生成的数据。

## 历史业务字段对应（不等于旧 PIT 已证明）

下列事实来自上述官方 ZIP，各路径均为包内 `choice-quantapi-skill/` 下的路径；本地对应位于 `source/dictionary/`。

| 输入 | 官方函数／字段 | 文档支持与仍需验证 |
| --- | --- | --- |
| 不复权已完成日线 | `csd`：`OPEN,CLOSE,HIGH,LOW,VOLUME,AMOUNT` | `references/indicators/csd/110001001001.md` 列出六字段；`AdjustFlag=1,Period=1,filldata=0`。必须显式日期、保留缺失；不得用 `ShowBlank=0` 把未知变成零。|
| 价量额单位 | `css` 日行情同名字段 | `references/indicators/css/101001005001.md` 明确 A 股价人民币、成交量默认股、成交额默认元；csd 字典本身单位列为空，接入前需同日期 css/csd 核对，不能仅凭同名直接宣称两个端点已验收。|
| 交易日历 | `tradedates` | 官方手册与 `references/functions/tradedates.md` 支持 SH/SZ 市场，使用显式市场；节假日修订仍保留版本，日历不是证券是否停牌证明。|
| 逐日交易状态 | `TRADESTATUS`；`css` 配 `TradeDate`；`csd` 序列也列出 | `css/101001005011.md` 列出正常、复牌、未上市、暂停／终止上市、连续／单日／盘中等停牌状态，并说明 2000 年以来可参考。还列出停牌理由、起止日期。缺响应样本，实际类型／编码与空值语义待验。|
| ST 与 *ST | `ISSTSTOCK,ISXSTSTOCK` | `css/101001001001.md` 的参数为 `EndDate`；csd 股票日行情也列出序列字段。需显式截止日期与实际枚举核对。空值或 ST 板块查无记录不证明正常。|
| 收盘涨跌停标记 | `css`：`MAXUPORDOWN`；另有 `ISSURGEDLIMIT,ISDECLINELIMIT` | `css/101001005001.md` 明确 `MAXUPORDOWN` 取 1／-1／0。收盘标记不直接证明开盘可成交或全天一字板。|
| 上下限价格 | `css`：`LIMITUPPRICE,LIMITDOWNPRICE` | 同上日行情字典。特别注意 csd 中 `HIGHLIMIT,LOWLIMIT` 中文释义为“是否涨停／是否跌停”，不能映射成价格。无涨跌幅限制日返回语义和价格舍入需样本核对。|
| 分红、送股、转增实施 | `ctr('DividendImplementationInfo',...)` | `ctr/000100180001.md`：现金每股派息、送股及转增比例、实施公告 `DIVIMPLANNCDATE`、登记 `DIVRECORDDATE`、除权 `DIVEXDATE`、派息 `DIVPAYDATE`、红股上市 `SHARELISTINGDATE`。日期筛选 `DateType=1` 实施公告／2 登记／3 报告期。勿默认按报告期作为获知时点。|
| 配股实施 | `ctr('AllotmentIPOStaticsInfo',...)` | `ctr/000100060007.md`：`RIGHTISSUEPRICE,RIGHTISSUERATIO,NOTICEDATE,RECORDDATE,EXRIGHTDATE,LISTINGDATE`；需要按证券筛选结果并核对比例单位。公开字典没有证明所有权益类型／所有撤销修订均完整。|
| 复权参考 | `TAFACTOR,FRONTTAFACTOR` | csd/css 字典列出，前者后复权、后者可指定基期；仅为辅助。不能以当前前复权历史替代旧当期 RAW、原始权益及其当时可得时间。|

## 旧版本能力：确有部分支持，仍不足以承诺通用 PIT

对原始 ZIP 的全部 1,971 个 Markdown 文件执行精确检索，结果保存在 `source/dictionary-search.json`。`as_of/asof`、`point-in-time/point in time`、`vintage` 无命中；独立 `PIT` 仅命中 REITs 利息及所得税科目的英文简称，并非时点数据库功能。关于“入库时间／修订时间／版本时间／历史版本”的检索未命中通用档案字段。**这是限定文档范围内未找到，不能推导 Choice 内部或定制服务绝对没有该能力。**

不能简单说“Choice 没有旧版本”：

- `references/indicators/css/101001011041001001.md` 的财务报表参数 `Type` 含 5 合并报表更正前、6 母公司报表更正前，并有正常／调整报表类型。这是具体财报口径的旧值选择线索，尚未证明保留每次更正中间版、对应发布时间、供应商首次可用时间，更不能推广成日线和状态的通用旧版查询。
- `references/indicators/css/101001011.md` 列有 `STMTACTDATE` 实际披露日、`STMTPLANDATEHISTORY` 预约披露变更历史、`CORRECTANNCDATE` 更正补充公告披露日和 `ITEMVALUECHANGEDATE` 财报科目变更披露日。`css/101001009007.md` 另有 `PERFORMANCEEXPRESSDATE/PERFORMANCEEXPRESSUPDATE` 的业绩快报首次／最新披露日。它们可帮助定位原公告和变更时间，但首次日期不能自动绑定当前返回数值为首版。
- 分红实施报表有实施公告日、登记／除息／支付等独立日期；停牌报表有历史停复牌日期。可取得的旧公告原件与披露时间经过单独核验后可能构成局部 PIT 证据。当前返回的结构化行、业务日期和修订后的事件数值仍不是过去某时点版本的证明。

对于本票已使用的四项透明特征，财报更正前字段未直接替代连续 RAW 日线回看、状态及权益缺口。它们说明产品有局部版本意识，不是该模型的历史数据准入已经通过。

## 自动采集、权限和额度

官方 Python 手册支持 `c.start()` 使用首次激活后的 `userInfo` 令牌，Windows/Linux/Mac SDK；默认账号并发多进程／多 IP 登录受限，正式账号可申请多点登录。手册说明激活令牌有效期一年，更换设备或密码需重新激活。`css/csd` 频次上限各 700 次／分钟，单请求最多 64 指标；具体套餐按函数、证券品种和周期计流量，`datastatistics` 可查阈值、已用和剩余量。不能把频次上限当每日免费额度或本账号授权。详见 [手册](https://quantapi.eastmoney.com/Upload/EMQuantAPI_Python.html) 与包内 `references/functions/datastatistics.md`。

若获得符合要求的历史交付，SDK 或数据库导出是可以验证的取数形态。本轮没有登录、查询真实行情、申请权限、购买、联系销售或改写现有采集设置。

## 历史 PIT 询证与最小样本验收

这些是调研与实现建议，不是已发生的服务承诺或已通过验收：

1. **档案类型与时间语义**：询证普通 API、历史数据库或单独定制交付是否保留当日原始发布／交易所文件／首次入库版，以及可查询的历史 `as_of` 或版本日志。必须区分交易日、公告披露时间、供应商首次入库时间、修改时间和本次取得时间；只有交易日加当前值不够。
2. **具体历史样本**：以本票江西铜业 `600362.SH` 和必要背景指数的固定日期窗口为范围，要求连续 RAW 日线、完整状态/ST/涨跌停和已知除息事件；选一处真实更正／迟到／状态变更，交付更正前后数值、各自可得时间和原件哈希。样本能被离线重放，且核对旧预测截止时不会纳入以后事实，才算可用的旧 PIT 补充。
3. **数据字典也需验证**：`css/101001005001.md` 的 CLOSE 释义仍包含旧收盘计算方式，并说明无成交可能沿前收；`filldata=0` 不能替代交易状态核验。需核对实际历史响应的单位、精度、缺失、停牌与上下限价格及长期口径变化。
4. **公告和权益局部补缺**：若不能交付通用 PIT，仍可索取真实旧公告原件和公告索引、原版与更正版、停复牌依据、分红登记／除息／支付和配股实施。每项单独证明覆盖和获知时点，不用年度股本未变或当前空事件结果推断逐日权益完整；供应商每股税后数不替代研究持有期税制计算。
5. **数据库服务合同**：确认历史档案实际保留起点、标的/字段/修订覆盖、导出格式、缺失处置与可验证来源链，并取得本地存储、长期留存与派生研究授权。公开页面没有价格、具体 PIT 套餐或本账号权限依据，不应先采购普通终端再假定解决该缺口。

截至本轮，达到的是 **公开官方文档＋原件哈希的能力评估**。历史业务字段与部分财报版本线索已核实；满足 ticket 19 的旧 PIT 档案仍 **未证实**。最有价值的下一步是向官方数据库／定制数据服务提出明确样本要求，不能凭历史查询功能宣布准入通过。
