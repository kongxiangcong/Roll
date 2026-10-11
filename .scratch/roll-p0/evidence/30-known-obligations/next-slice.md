# 下一最小可执行slice：SSE当前指定日期停牌观察receipt与消费

本轮不执行新HTTP或追加源实现。下面入口和请求字段来自已固定[SSE manifest](../../../../backend/src/roll/market/reference/sse-history/sources.json)，只证明既有官方schema线索；下一轮必须验证当前返回，不承诺永久可用或完整覆盖。

**具体入口**：`https://query.sse.com.cn/sseQuery/commonQuery.do`，既有`sqlId=COMMON_SSE_XXPL_JYTS_TFPXX_L`、`SEARCH_DATE`、`isPagination`和`pageHelp.pageSize/pageNo/beginPage/endPage/cacheSize`；同入口官方客户端`https://www.sse.com.cn/xhtml/home/2021public/querySearch/search_tradeTip_2021.js`固定SHA `32fc98ea41e599f457609247ba68defb82e6d855aa2551da6923dbf7e44153a7`。已有2016-02-16回包78/78原件及有限parser，适合接一个有界source assessment caller，而不是泛化provider。

**所需语义**：实际Host本次指定日期请求/returned/total/page bounds原件，逐事件证券ID、reported停牌开始/结束字段及精度、原received_at、normalized_known_at、HTTP状态/失败receipt与raw SHA；只对明确返回且日期吻合的停牌事实绑定field evidence。reported结束不冒充实际复牌。未返回、0total、截断、early-empty或日期过滤含义未证时，absence/normal/fullstatus仍UNKNOWN。风险/listing/ex-rights不是该来源已证明维度，不挪用。

**有限验收**：复用单worker/raw-first archive，最多一个有界assessment（例如不超过2页，达到预算保留partial），不预测/fit/SEALED/授权/真实起点。先固定现78/78原件供public API red→green；如父任务继续允许有限匿名公开评估，再把实际新原件固定SHA后接同parser，真实日期不回填旧预测。PostClosePackets inputs/query/packet/replay同轮消费source-bound事件/失败/缺口，旧packet固定receipt IDs；损坏raw/原JS、分页截断/0total、错误日期/证券与同cutoff追加均拒绝或保留UNKNOWN。仅证明一个当前source observation维度，complete_status_verified仍false。

另四项仍需分别推进，不应改成统一外部等待：

- 当前公司行动范围：已存`https://www.cninfo.com.cn/new/hisAnnouncement/query`的stock `600362,gssh0600362`、column `sse`、seDate/pageNum/pageSize等字段可接有限current requested-interval receipt。全类别/空searchkey/totalpages语义必须实证，不先宣称全行动coverage；具体内部caller尚未实现。
- 修订原ID：既有CNINFO候选保存原announcementId/associateAnnouncement/adjunctUrl；官方本体入口为`https://static.cninfo.com.cn/`加原adjunctUrl。先精确指名关联ID/PDF并固定SHA，再有字段/文本定位地关联旧原义务；关联ID、title或新日期本身不证明取代/取消，first-availability未知不补造。
- listing/relisting、风险子类型、ex-rights：当前缺该维度明确官方返回schema/覆盖与parser/caller。下一次来源评估从SSE官方证券资料/交易提示客户端与CNINFO精确公告定位开始，先固定确切入口/字段语义再实现；不把旧历史JS/名称线索说成当前权威清单。本文件未推测未知sqlId。
- yunhq单位适用：现`http://yunhq.sse.com.cn:32041/v1/sh1/list/exchange/equity`本身reporter已适配；要查该endpoint对应官方客户端/资料的volume/amount/成交范围定义并绑定实际版本和SHA。旧`search_stocksDepositoryReceipts_2021.js`只支持另一历史query endpoint，不能直接授权单位转换。

只有合法未来检查点的真实完整组合与独立资格闭合，才能另执行实际forward；本计划不授权当前能力PASS或降低门禁。
