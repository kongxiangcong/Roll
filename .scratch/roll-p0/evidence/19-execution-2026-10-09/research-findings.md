# Ticket 19 历史时点取证续推

## 实际取得与界限

本轮固定江西铜业600362，只检索既有公开研究范围2013—2025，不读取实际研究分片、运行数据库或SEALED，不计算标签。初始主机attempt-manifest再次核验同一家族两个FAILED PRIMARY_FIT，剩余主拟合／邻域3次、校准1次；原失败未改类、未删除、未重置。见`initial-state.json`。

6个精确Internet Archive索引均HTTP200，取消旧按月collapse后，主quote URL62条、query变体2条、搜狐历史页7条；两个固定日K URL及klc精确URL均为本次查询零命中。所有结果低于5000截断上限。只证明这些明确URL查询结果，不能推断全部档案无数据。索引是捕获元数据，不能当作行情正文。

在复用旧40份quote正文的基础上，对未取到的31个capture请求实际正文，取得5份摘要吻合的新quote，覆盖3个新增业务日；其余26个请求断连，逐目标仅一次重试仍断连。没有follow-redirect或live fallback。5份包括2016-02-19零OHLC/零量且capture在两天后的报价、2017-08-11和2019-09-27收盘钟点但capture较晚的报价、2018-10-23两份相隔3秒的盘中版本。它们各自保留capture、业务钟点和2026实际接收钟点，`original_publication_at`仍null。

首个payload阶段因host白名单遗漏明确`:80`URL而中止，部分原体保留但完整尝试次数未知；没有宣称一次完美收集。修正为解析hostname及默认端口后，每目标即时保存独立receipt，完整31目标阶段与重试另记；见`payload-initial-abort.json`。不覆写旧失败。

旧40＋新5份报价合计43业务日；日历原件SHA、假日及修订核对后最长连续序列2日。**2<固定特征需要的21行**，且盘中、停牌、晚捕获、schema与完整状态问题没有被日期连续性解决。没有合格训练行、DEV/CAL标签、真实模型或校准工件。`coverage-and-integrity.json`核验63个明确公共引用、61唯一SHA，长度／哈希差异0；包含复用quote及官方日历，不是61份新资料。

## 独立渠道调查

根据[Common Crawl官方取数说明](https://commoncrawl.org/get-started)和[索引格式](https://commoncrawl.org/cdxj-index)，另取得collection catalog，按结果查看前的固定规则选择2023和2025各第一期collection，对quote、搜狐历史页和新浪证券页3个精确URL查询，共6次索引请求，返回3次503及3次504。失败原体归档；没有得到可下载WARC定位信息，未抓取或伪造市场正文。这些失败不证明对应collection无capture。

另检查声称每日更新的[ihQuant源说明](https://github.com/huzpsb/ihQuant)及其[ihq_bin仓库](https://github.com/huzpsb/ihq_bin)：官方GitHub API按`path=ihq.bin, until=2025-12-31`返回空提交列表；当前README只是更新机制说明，不是2025历史发布链。未下载当前二进制再冒充历史版本，也未使用第三方proxy。9项该阶段请求的原体、状态与接收钟点在`alternative-metadata-receipts.json`。

后续可从已明确的7个搜狐capture及26个未取得payload继续核验网络恢复后的原体，或在其他具体Common Crawl collection查到记录后按官方WARC范围读取；只有真实正文提供合格连续原价OHLCV和完整时点／状态依据才进入准入。不得先拟合／计算标签再换窗口。上证信息历史数据渠道提供快照、日K和证券基本信息的[官方产品说明](https://www.sseinfo.com/services/assortment/historical/)，但尚无实际数据交付、历史版本链承诺或申请；购买、签约或联系外部人员需另行授权。

## 内部实现与外部资料分开

已确认的内部缺口仍包括：真实源准入与预登记分窗、非METHOD特征时点验证、真实训练标签资格、RESEARCH模型生成及独立模型冻结。此次不能把它们全部归咎于外部档案不足。实施切片将分别留验收及明确未完成项，不把已完成的额度保护、来源原件核验或已知现金权益计算描述为完整真实训练能力。

真实公开来源、控制性测试、研究模拟lot和用户真实账户分别标识。模型冻结不需要19提前证明SEALED独立性或G3/G7；但是合格DEV/CAL未产生时，19保持partial，20不解锁。
