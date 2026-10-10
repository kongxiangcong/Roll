# Ticket 19 江西铜业公开数据研究（2026-10-09）

范围仅 SSE:600362。阅读了领域术语、ADR 0001—0003、研究协议、日线执行、透明模型和取证公共契约。没有读取旧封存区，没有训练、计算标签、比较收益或查看最终测试；没有调用 Fuyao/BaoStock。HTTP 读取原件只在内存解析；本研究唯一写入物为本文件，可靠原件归档和宿主集成由主进程负责。

## 结论与可执行范围

主动收集能补足大量原价、公司行为和规则证据，但本轮取得的当前历史版本不能证明历史观察日的可得版本。`received_at/available_at` 必须保持实际取得时点；公告页面日期和 CNINFO `announcementTime` 不能直接伪装成本地历史接收时刻。既有 CAL 每类 20、占用概率箱各 20、入选成熟 40、20 日有效依赖块 30 的门槛保持；更多行数不自动通过这些门槛，更不解除历史 PIT 和封存独立性缺口。

本轮找到 CNINFO 官方检索的 14 份年度/半年度现金实施原件，覆盖实施年份 2013—2025 每一年及 2025 半年分红；逐份实际下载成功并用 pypdf 阅读，身份均为 600362。发现 2013 支付日不能用第三方除息日代替；发现 2024/2025 差异化分红需要区分账户实派与除息参考；发现 2016 停复牌以及 2017 发行终止，不能统一默认普通状态或把融资预案当实施事实。

这证明了具体公告集合的覆盖，不证明全部公司行为/历史状态已经穷尽。完整性仍需官方全公告分页索引、各年股本/分配附注和交易状态逐日核对。

## CNINFO 官方索引的精确请求

`POST https://www.cninfo.com.cn/new/hisAnnouncement/query`，`Content-Type: application/x-www-form-urlencoded`，表单：

```text
pageNum=1
pageSize=30
column=sse
tabName=fulltext
stock=600362,gssh0600362
seDate=2013-01-01~2025-12-31
searchkey=实施公告
sortName=time
sortType=asc
isHLtitle=true
```

证券映射来自实际 [CNINFO 股票索引](https://www.cninfo.com.cn/new/data/szse_stock.json)：`code=600362, orgId=gssh0600362, category=A股, zwjc=江西铜业`。该 JSON 名称包含 szse，但实际含该上交所证券；不能凭文件名猜所属交易所。

响应字段 `announcements[].secCode/secName/announcementTitle/announcementTime/adjunctUrl`，计数 `totalAnnouncement/totalRecordNum/totalpages/hasMore`。标题含 `<em>` 高亮，应去标签而不改源字节。`announcementTime` 为供应商索引时钟，不是证明过的原始披露精确时刻。实际 `searchkey=实施公告` 返回 18 条，其中下表 14 条为分配实施；另有股东增持/回购/发行价调整，不混成现金分配。无关键词时返回 `totalAnnouncement=1005`；实际单页 30，传 100 未得到 100 条，因此必须真实分页并核数量，不能宣称一页已全取。

其他实际检索：回购股份 7 条；停牌 2 条；复牌 1 条；非公开发行 40 条（两页 30+10）；增发 0 条；风险警示 0 条。后两项不能作为无事件/无 ST 的完整性证明。

## 公司现金实施原件表

现金单位为税前人民币元/股。日期为公告原件的 DATE，不填午夜。表中送转栏“现金方案未列送转”表示该实施公告未列股份分配，不能代替所有其他公告的无事件结论。2017—2023 明示“差异化分红送转：否”；更早模板没有同名字段，保持未明示。

| 实施公告日期 | 分配所属期 | 登记日 | 除息日 | 现金发放日 | 现金/股 | 差异化 | 送转范围 | 官方原件 |
|---|---|---|---|---|---:|---|---|---|
| 2013-07-18 | 2012年度末期 | 2013-07-23 | 2013-07-24 | **2013-07-30** | 0.50 | 未明示 | 现金方案未列送转 | [62845175.PDF](https://static.cninfo.com.cn/finalpage/2013-07-18/62845175.PDF) |
| 2014-07-24 | 2013年度末期 | 2014-07-30 | 2014-07-31 | 2014-07-31 | 0.50 | 未明示 | 现金方案未列送转 | [1200074589.PDF](https://static.cninfo.com.cn/finalpage/2014-07-24/1200074589.PDF) |
| 2015-07-10 | 2014年度 | 2015-07-16 | 2015-07-17 | 2015-07-17 | 0.20 | 未明示 | 现金方案未列送转 | [1201268396.PDF](https://static.cninfo.com.cn/finalpage/2015-07-10/1201268396.PDF) |
| 2016-08-05 | 2015年度 | 2016-08-11 | 2016-08-12 | 2016-08-12 | 0.10 | 未明示 | 现金方案未列送转 | [1202538463.PDF](https://static.cninfo.com.cn/finalpage/2016-08-05/1202538463.PDF) |
| 2017-07-06 | 2016年度 | 2017-07-11 | 2017-07-12 | 2017-07-12 | 0.15 | 否 | 现金方案未列送转 | [1203684386.PDF](https://static.cninfo.com.cn/finalpage/2017-07-06/1203684386.PDF) |
| 2018-07-19 | 2017年度 | 2018-07-24 | 2018-07-25 | 2018-07-25 | 0.20 | 否 | 现金方案未列送转 | [1205195306.PDF](https://static.cninfo.com.cn/finalpage/2018-07-19/1205195306.PDF) |
| 2019-07-22 | 2018年度 | 2019-07-25 | 2019-07-26 | 2019-07-26 | 0.20 | 否 | 现金方案未列送转 | [1206466159.PDF](https://static.cninfo.com.cn/finalpage/2019-07-22/1206466159.PDF) |
| 2020-07-09 | 2019年度 | 2020-07-15 | 2020-07-16 | 2020-07-16 | 0.10 | 否 | 现金方案未列送转 | [1208016044.PDF](https://static.cninfo.com.cn/finalpage/2020-07-09/1208016044.PDF) |
| 2021-07-13 | 2020年度 | 2021-07-19 | 2021-07-20 | 2021-07-20 | 0.10 | 否 | 现金方案未列送转 | [1210467038.PDF](https://static.cninfo.com.cn/finalpage/2021-07-13/1210467038.PDF) |
| 2022-07-15 | 2021年度 | 2022-07-22 | 2022-07-25 | 2022-07-25 | 0.50 | 否 | 现金方案未列送转 | [1214041661.PDF](https://static.cninfo.com.cn/finalpage/2022-07-15/1214041661.PDF) |
| 2023-07-14 | 2022年度 | 2023-07-20 | 2023-07-21 | 2023-07-21 | 0.50 | 否 | 现金方案未列送转 | [1217292605.PDF](https://static.cninfo.com.cn/finalpage/2023-07-14/1217292605.PDF) |
| 2024-07-18 | 2023年度 | 2024-07-23 | 2024-07-24 | 2024-07-24 | 0.60 | 是 | 明示不送股、不转增 | [1220664065.PDF](https://static.cninfo.com.cn/finalpage/2024-07-18/1220664065.PDF) |
| 2025-07-15 | 2024年度 | 2025-07-21 | 2025-07-22 | 2025-07-22 | 0.70 | 是 | 明示不送股、不转增 | [1224163682.PDF](https://static.cninfo.com.cn/finalpage/2025-07-15/1224163682.PDF) |
| 2025-11-21 | 2025半年度 | 2025-11-27 | 2025-11-28 | 2025-11-28 | 0.40 | 是 | 明示不送股、不转增 | [1224816852.PDF](https://static.cninfo.com.cn/finalpage/2025-11-21/1224816852.PDF) |

上交所 2025 年公告地址为 [600362_20250715_NW0M.pdf](https://static.sse.com.cn/disclosure/listedinfo/announcement/c/new/2025-07-15/600362_20250715_NW0M.pdf)。本次实际 HTTP 200 但得到同一 gzip HTML 拦截页，不能以扩展名或 HTTP 200 认作 PDF；上表 CNINFO 同公告原件实际 `%PDF` 成功。2026 年实施公告精确地址 [600362_20260710_BV2J.pdf](https://static.sse.com.cn/disclosure/listedinfo/announcement/c/new/2026-07-10/600362_20260710_BV2J.pdf) 同样被拦，本表范围截至 2025，不据此写入 2026 事实。

### 必须分离的现金与复权字段

2024/2025 三份实施原件给出 A 股总数 2,075,247,405，回购专户 10,441,768，实参分派 2,064,805,637。除息参考对总股本摊薄：

| 除息日 | 个人持有合格普通股税前实派/股 | 交易所参考扣减/股 | 流通股份变动 |
|---|---:|---:|---:|
| 2024-07-24 | 0.60 | 0.5970 | 0 |
| 2025-07-22 | 0.70 | 0.6965 | 0 |
| 2025-11-28 | 0.40 | 0.3980 | 0 |

前者用于模拟现金权益及持股税处理，后者用于原价除息参考、涨跌停计算；不能一个 `cash_dividend` 字段兼用。不能用当前 qfq 当完整总收益。按实际股份/现金日期/持股期限追踪连续 NAV，除息日的应收权益与发放日可用现金分别保存；发放前不能用未到账现金买入。未知券商事实不自动写入真实账本。

2015 原公告个人初扣 5%，其适用税制不同于 2016 以后。2016 及后续原公告个人持有一年以内分派时暂不扣，卖出后按持有期限补税：一月内 20%、一月至一年 10%、超过一年免；因此“分派时未扣”不能作为最终无税口径。原 20 日事件可能涉及不同自然月边界，需按公历持股期限和批次规则处理，不能硬写每份权益净现金相同。

## 其他公司行为和状态原件

| 对象 | 精确官方原件 | 本次实际核到的内容与范围 |
|---|---|---|
| 2016停牌 | [1201981143.PDF](https://static.cninfo.com.cn/finalpage/2016-02-16/1201981143.PDF) | 本公司股票 2016-02-16 起停牌，筹划非公开发行；不是零量推定 |
| 2016停牌进展 | [1201991135.PDF](https://static.cninfo.com.cn/finalpage/2016-02-23/1201991135.PDF) | 停牌进展原件；与首/末事件连成区间 |
| 2016复牌 | [1202000598.PDF](https://static.cninfo.com.cn/finalpage/2016-02-26/1202000598.PDF) | A股 2016-02-26 起复牌；停牌区间 `[2016-02-16,2016-02-26)`，交易日由官方日历确定 |
| 2016发行预案 | [1202000600.PDF](https://static.cninfo.com.cn/finalpage/2016-02-26/1202000600.PDF) | 预案，不代表发行完成/新增股份/每股权益变化 |
| 2017发行终止 | [1203689481.PDF](https://static.cninfo.com.cn/finalpage/2017-07-08/1203689481.PDF) | 官方索引题名明确终止非公开发行A/H股，需可靠归档核原件后给终止事实 |
| 2024回购报告书 | [1219145939.PDF](https://static.cninfo.com.cn/finalpage/2024-02-22/1219145939.PDF) | 回购计划及后续处理约束；不能当实成交汇总 |
| 2024首次/进展 | [1219408422.PDF](https://static.cninfo.com.cn/finalpage/2024-03-27/1219408422.PDF)、[1219501865.PDF](https://static.cninfo.com.cn/finalpage/2024-04-03/1219501865.PDF)、[1219983533.PDF](https://static.cninfo.com.cn/finalpage/2024-05-07/1219983533.PDF) | 每阶段来源版本，不用完成公告回填更早获知时刻 |
| 2024回购完成 | [1220109130.PDF](https://static.cninfo.com.cn/finalpage/2024-05-21/1220109130.PDF) | 2024-05-17 完成；10,441,768股放回购专户；公告股份总数前后均3,462,729,405，不把回购立即当注销；后续出售/未出售注销另有约束 |

完整性界限：CNINFO“风险警示”零结果不能推出全部日期 `is_st=false`；搜索“停牌”两条也不能排除盘中临停、其他公告题名或未命中记录。需官方全部公告索引/逐年报告/交易所状态档案联合核验，再按已证明区间形成状态，其他日期保留 UNKNOWN。送转/配股/发行没有命中也不补零；尤其不能把 H 股股东/子公司恒邦的变化混作 600362 A 股行为。

## 原价历史行情的当前可达来源

实际 GET 成功：

```text
https://q.stock.sohu.com/hisHq?code=cn_600362&start=20130101&end=20241231&stat=1&order=D&period=d
```

响应 `application/x-javascript; charset=gbk`，262197字节，SHA256 `2df60861c546aa85f0e62b17401bdbc638a3b98ade11ff4821f78559ca333858`；JSON 结构 `[ {status:0, code, hq, stat} ]`，`hq` 实际2883行，2013-01-04—2024-12-31，降序，每行10项。只检查元数据/结构，未输出价格/收益/标签。该接口为搜狐第三方当前历史行情，非交易所一手历史版本，响应没有历史版本修订证明、ST/停牌/完整公司行为/PIT。

候选字段为日期、开盘、收盘、涨跌额、涨跌幅、最低、最高、成交量、成交额、换手率，单位和 RAW 口径必须由宿主实际网页字段及独立原价交叉验证后登记，不能仅凭常见接口记忆确认。不要把 `stat` 全窗涨跌统计作为研究依据；不要计算/挑选标签后再定分窗。

腾讯既有宿主有适配，研究阶段应使用 RAW `day` 而非当前 `qfqday`。本研究手工参数 `param=sh600362,day,2023-01-01,2024-12-31,640` 返回 `code=1,msg=bad params`，不报告为取得数据；复用现有宿主的精确参数，不能“返回200”就认定成功。腾讯/Sohu一致也不意味着独立一手或历史无修订。

## 交易规则与官方日历来源

已定位可下载/阅读的官方材料：

| 范围 | 官方来源 | 可支持与限制 |
|---|---|---|
| 2013全年 | [2013全年休市通知](https://www.sse.com.cn/aboutus/mediacenter/hotandd/c/c_20150912_3988635.shtml) | 原公告披露2012-12-26、年度首个交易日2013-01-04。迁移URL的20150912不是原生效日；原文晚/早时钟分开 |
| 2024全年 | [2024休市安排](https://www.sse.com.cn/disclosure/dealinstruc/closed/c/c_20231226_5733941.shtml) | 具体年度原文；周末调休工作日仍休市 |
| 2025全年 | [2025休市安排](https://www.sse.com.cn/disclosure/dealinstruc/closed/c/c_20241223_10767110.shtml) | 2024-12-23披露；2025-10-01—10-08休市、10-09开市 |
| 2026全年 | [当前年度休市](https://www.sse.com.cn/disclosure/dealinstruc/closed/) | 当前网页可阅读，须当前原件归档；不能未来年份外推 |
| 年度/补充通知索引 | [休市公告列表](https://www.sse.com.cn/disclosure/dealinstruc/closed/list/) | 历史分页/临时变更均须核，2020延长春节等不能只用最初年度表 |
| 2026规则及前版沿革 | [交易规则2026](https://www.sse.com.cn/lawandrules/sselawsrules2025/stocks/exchange/c/c_20260424_10816482.shtml) | 发布2026-04-24、生效2026-07-06；2023版同时废止。3.1.4交收前不得卖、2.4.1交易日、2.4.2竞价时段、4.3除息、风险警示特规等，旧年必须旧版 |
| 历史废止版本 | [废止规则文本](https://www.sse.com.cn/lawandrules/sselawsrules/repeal/rules/) | 规则引用时须定位精确旧版及施行/暂缓条文，不能用现行规则回填2013—2025 |
| 规则汇编索引 | [2025规则汇编PDF](https://www.sse.com.cn/lawandrules/sselawsrules2025/overview/c/10778726/files/ddfc82e93a85496bb075175d9a8d811d.pdf) | 官方汇编可帮助找2023旧版条目，汇编不是历史当日无修订证明 |

注意上交所2026-07-06起主板风险警示涨跌幅从5%改10%，不能把当前普通/风险规则统一外推旧年；见[官方修订说明](https://star.sse.com.cn/aboutus/mediacenter/hotandd/c/c_20260424_10816474.shtml)。2013—2025其余年度休市原文和更早交易规则精确下载尚未穷尽；不得宣称完整历史规则覆盖。本次研究没有用政府调休表/周一至周五机械替代交易所日历，也没有推断缺bar就是休市。

## 保持原门槛的最小后继预登记建议

1. 先将本轮所有实际获取及既有失败/工程暴露关联原家族，保存数据/原件/检索请求/代码指纹，不换协议名复活五次拟合或一次校准预算。候选、四特征、λ1、20交易日、阈值0.60和既有成本/支持/压力条件不变。此步骤不训练。
2. 截至2025的历史重构研究可预先登记较长DEV/CAL窗口和20日隔离，长窗只是设计上使原CAL每类20/依赖块30具备可能性。在历史PIT、状态、权益或规则没有可核证明前，`eligible_for_training=false`，不生成假概率、模型或占位校准器。不能把这标为19完整研究验收或20解锁。
3. 真实PIT最小可执行路径是从实际当前取得时点开始，保存每次已完成日线原件及接收时钟/修订版本/公告/状态/日历，固定消费截止和缺失政策。每日真实快照可以服务日后的真正当时可得特征；历史20日特征上下文仍须明确当前重构与未来观察的区别。当前没有可回溯的官方历史接收档案时，等待未来数据成熟是客观条件，不能补造。
4. 冻结前DEV/CAL真实可评分支持达到原条件且独立校准验证可用；若失效/预算用尽，结束为FAILED/INCONCLUSIVE并保留全部尝试，不能反复加窗看到通过才停。未使用最终窗须与先前公开/已获取历史窗分开登记；旧SEALED始终UNPROVEN，不看结果。
5. 只在19真实训练/校准/冻结判据满足后进入20。无法即刻取得历史PIT时，继续完成可验的采集/解析/状态/权益/规则工程与证据，对19保持partial/needs-info；原正式能力和未来三自然月前向硬终点不被采集成功改变。

这是依据当前契约的设计推断，未把设计当实施/统计通过。更长窗口本身不保证正负类别、概率箱或选中子集支持，任何真实研究必须先检查而不得下降门槛。

## 后续补齐：2013—2025年度日历及特殊更正

以下每个年度通知均找到上交所官方原文（2013、2024、2025地址见前表），仅保存索引，具体日期/版本需主进程归档后逐年解析。URL迁移时间与原发布日期分开。

| 年度 | 原发布日期 | 官方原文 |
|---|---|---|
| 2013 | 2012-12-26 | [3988635](https://www.sse.com.cn/aboutus/mediacenter/hotandd/c/c_20150912_3988635.shtml) |
| 2014 | 2013-12-25 | [3988725](https://www.sse.com.cn/aboutus/mediacenter/hotandd/c/c_20150912_3988725.shtml) |
| 2015 | 2014-12-24 | [3979217](https://www.sse.com.cn/disclosure/dealinstruc/closed/list/c/c_20160104_3979217.shtml) |
| 2016 | 2015-12-24 | [4028872](https://www.sse.com.cn/disclosure/dealinstruc/closed/list/c/c_20160104_4028872.shtml) |
| 2017 | 2016-12-22 | [4218613](https://www.sse.com.cn/disclosure/announcement/general/c/c_20161222_4218613.shtml) |
| 2018 | 2017-12-22 | [4438363](https://www.sse.com.cn/disclosure/announcement/general/c/c_20171222_4438363.shtml) |
| 2019 | 2018-12-20 | [4696473](https://www.sse.com.cn/disclosure/announcement/general/c/c_20181220_4696473.shtml) |
| 2020 | 2019-12-20 | [4969627](https://www.sse.com.cn/disclosure/announcement/general/c/c_20191220_4969627.shtml) |
| 2021 | 2020-12-24 | [5286949](https://www.sse.com.cn/disclosure/announcement/general/c/c_20201224_5286949.shtml) |
| 2022 | 2021-12-20 | [5662606](https://www.sse.com.cn/disclosure/announcement/general/c/c_20211220_5662606.shtml) |
| 2023 | 2022-12-27 | [5714458](https://www.sse.com.cn/disclosure/announcement/general/c/c_20221227_5714458.shtml) |
| 2024 | 2023-12-26 | [5733941](https://www.sse.com.cn/disclosure/dealinstruc/closed/c/c_20231226_5733941.shtml) |
| 2025 | 2024-12-23 | [10767110](https://www.sse.com.cn/disclosure/dealinstruc/closed/c/c_20241223_10767110.shtml) |

至少以下三个特殊修订必须合并：

- [2015纪念日公告](https://www.sse.com.cn/disclosure/dealinstruc/closed/list/c/c_20160104_3979337.shtml)，2015-07-21公布，2015-09-03—09-05休市，09-06周末休市，09-07开市；不能只读原2015年度表。
- [2019劳动节调整公告](https://www.sse.com.cn/disclosure/announcement/general/c/c_20190418_4771364.shtml)，2019-04-18公布，改为05-01—05-04休市、05-06开市。原2018-12-20通知写05-02开市，原件继续保留但受后修订覆盖。
- [2020春节延长公告](https://www.sse.com.cn/disclosure/announcement/general/c/c_20200127_4991582.shtml)，2020-01-27公布，春节延长至02-02，02-03开市；及[业务衔接通知](https://www.sse.com.cn/aboutus/mediacenter/hotandd/c/c_20200202_4991648.shtml)，原接口日期可能仍写01-31，不能据接口DATE断言已交易。

这补足年度通知索引与已知重要更正，不是全部临时停市/熔断穷尽声明。2016-01-04/01-07市场熔断导致提前停止交易，不能用这些日期15:00作为未经证明的完成时点。见[官方2016市场回顾](https://www.sse.com.cn/aboutus/publication/factbook/documents/c/10170565/files/42dc9278c7a14ff9b2d887ff0fbf4dfb.pdf)记录2016-01-08起暂停指数熔断，仍需对应日原通知补精确时刻。

## 后续补齐：2023旧版规则及历史切换

[上交所2023旧版现存页面](https://www.sse.com.cn/lawandrules/sselawsrules2025/repeal/rules/c/c_20250612_10824490.shtml)，原 `/lawandrules/sselawsrules/stocks/exchange/c/c_20230216_5716380.shtml` 实际404，不以转载页面的“现行有效”判断效力。

官方附件地址均在 `/lawandrules/sselawsrules2025/repeal/rules/c/10824490/files/`：

- [交易规则2023 DOCX](https://www.sse.com.cn/lawandrules/sselawsrules2025/repeal/rules/c/10824490/files/dcbe58edb194451d93f19b1f7dd8fb4c.docx)，本次实际51948字节，PK/ZIP与word/document.xml验证成功，SHA256 `7aa2319f6dcf597be1e86b3b69d7c2ad0e6acb2a5d0cc6be48a01af602fded40`。
- [起草说明](https://www.sse.com.cn/lawandrules/sselawsrules2025/repeal/rules/c/10824490/files/0e769c598d024441a2300f7d4c8f8093.docx)。
- [同步废止清单](https://www.sse.com.cn/lawandrules/sselawsrules2025/repeal/rules/c/10824490/files/2dd188e159c243a384004b3dc48167a8.docx)。
- [暂缓实施条文](https://www.sse.com.cn/lawandrules/sselawsrules2025/repeal/rules/c/10824490/files/3f0cc77bae0543c795a42731398bc8e0.docx)。

实际读取正文定位：2.4.1周一至周五及公告休市；2.4.2普通竞价时段；3.1.4交收前禁卖；3.3.8买入100股整数倍及卖出零余一次性申报；3.3.11 A股0.01元报价单位；3.3.13一般10%及例外；3.3.17涨跌幅价格四舍五入到报价单位；4.3.2现金/配股/流通变化除权参考公式；4.4.10风险警示5%。这些是交易规则事实，不证明600362每一天属于普通或风险警示状态。

页面结构元数据写生效2023-02-17，但正文要求首只注册制主板上市首日起施行。依[官方衔接问答](https://www.sse.com.cn/aboutus/mediacenter/hotandd/c/c_20230217_5716420.shtml)、[上市安排问答](https://english.sse.com.cn/news/newsrelease/c/5719418.shtml)和[落地回顾](https://www.sse.com.cn/aboutus/mediacenter/hotandd/c/c_20230810_5725020.shtml)，该切换为2023-04-10；应将正文/实施证据优先于页面自动metadata并保存冲突。

更早规则已找到：[2020第二次修订通知](https://www.sse.com.cn/lawandrules/sselawsrules2025/repeal/rules/c/c_20200313_10785127.shtml)明示2020-03-13施行、旧2018及2020-01修改同步废止；[2018修订旧通知](https://www.sse.com.cn/lawandrules/sselawsrules/repeal/rules/c/c_20210531_5478087.shtml)及[官方收盘机制实施说明](https://www.sse.com.cn/aboutus/mediacenter/hotandd/c/c_20180806_4607055.shtml)明确2018-08-20实施14:57—15:00集合竞价。因此2013—2018-08-17不能无条件沿用现代收盘集合竞价时段。2013/2014/2015/2017精确旧版全文及暂缓/熔断仍为未穷尽项。
