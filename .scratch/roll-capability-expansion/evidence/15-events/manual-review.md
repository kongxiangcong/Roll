# 15 小样本手工核查（真实归档新闻）

核查对象：14 票实际归档的 10 条东方财富新闻（`real-association.json`，数据来自 `.scratch/r14real` 的隔离副本 `.scratch/r15real`）。核查方式：代理逐条阅读标题、列表摘要、已抽取正文（仅有 1 篇，其余未取正文）与命中位置，对照规则输出的分类和依据。这是**代理手工核查**，不是独立人工标注，也不构成情绪或收益结论。

- 核查日期：2026-10-18
- 关联规则版本：ASSOCIATION_VERSION=1（注册身份优先；名称与代码、标题与正文分别记录；行业/概念标记只用于查询词命中时的区分）
- 注册身份：SSE:600362 江西铜业股份有限公司（依据 09 财务原件 SECURITY_NAME_ABBR=江西铜业、600362.SH）
- 结果：10/10 与规则输出一致；INDUSTRY_BACKGROUND 2、COMPANY_SUBJECT 4、COMPANY_MENTIONED 2、UNRELATED 2。
- 去重：该 10 条样本没有相同规范URL或相同正文哈希，故 10 个唯一事件、0 转载、0 修订；同文异URL/修订/别名冲突由 METHOD 应用测试覆盖，不能由本样本声称真实转载已出现。
- 对象：本样本只登记了目标证券身份；第 7 条标题中的其他代码未登记，未被伪造成已解析公司对象。多对象路径由 METHOD 测试用 000657 注册身份验证。
- 身份时点限制：关联使用当前已登记身份，不声称按新闻发布时点的身份历史快照；它只作观察展示，不进入 PIT 研究输入或收益结论。

| # | 标题 | 规则分类 | 规则依据 | 手工结论 | 说明 |
| --- | --- | --- | --- | --- | --- |
| 1 | 8.96亿元资金今日流入有色金属股 | INDUSTRY_BACKGROUND | TARGET_CODE_IN_BODY、INDUSTRY_MARKER_WITH_KEYWORD_ONLY | 一致 | 标题为有色金属板块资金流汇总，600362 仅出现在个股表格，按行业背景保留并标注查询词命中，不作为公司主体。 |
| 2 | 江西铜业600362.SH)：2026年中报净利润为86.32亿元、同比较去年同期上涨106.77% | COMPANY_SUBJECT | TARGET_NAME_IN_TITLE、TARGET_CODE_IN_TITLE、TARGET_NAME_IN_BODY、TARGET_CODE_IN_BODY | 一致 | 标题同时含公司简称与代码，明确公司主体。 |
| 3 | PCB概念下跌2.48%，23股主力资金净流出超亿元 | UNRELATED | TARGET_CODE_IN_BODY、THEME_PAGE_KEYWORD_ONLY | 一致 | 标题主题为 PCB 概念，600362 仅在表格，未出现公司名或铜行业语汇，判为不相关。 |
| 4 | 江西铜业：拟与控股股东签订2027-2029年度日常关联交易合同 | COMPANY_SUBJECT | TARGET_NAME_IN_TITLE、TARGET_NAME_IN_BODY、TARGET_CODE_IN_BODY | 一致 | 标题以公司简称开头，明确公司主体。 |
| 5 | 资源禀赋构筑供给壁垒 新兴产业打开长期需求 沪市有色龙头“家底”有多厚？ | COMPANY_MENTIONED | TARGET_NAME_IN_BODY、TARGET_CODE_IN_BODY | 一致 | 标题为行业综述，公司名仅出现在正文/摘要，判为公司提及而非主体。 |
| 6 | PCB概念上涨1.92%，7股主力资金净流入超亿元 | UNRELATED | TARGET_CODE_IN_BODY、THEME_PAGE_KEYWORD_ONLY | 一致 | 同 PCB 下跌条目，代码仅在表格，判为不相关。 |
| 7 | 快速拉升！600362、603979、601212封死涨停 | COMPANY_SUBJECT | TARGET_CODE_IN_TITLE | 一致 | 标题含目标代码，属于目标证券价格异动；同列其他代码未登记身份，故不作为已解析对象。 |
| 8 | 江西铜业与控股股东重签关联交易合同，三年采购预计上限超520亿元 | COMPANY_SUBJECT | TARGET_NAME_IN_TITLE、TARGET_NAME_IN_BODY、TARGET_CODE_IN_BODY | 一致 | 标题含公司简称，明确公司主体。 |
| 9 | 从周期资源迈向战略资源 沪市有色行业长期价值凸显 | COMPANY_MENTIONED | TARGET_NAME_IN_BODY、TARGET_CODE_IN_BODY | 一致 | 行业综述标题，公司名在正文，判为公司提及。 |
| 10 | 有色金属行业资金流出榜：云南锗业等10股净流出资金超亿元 | INDUSTRY_BACKGROUND | TARGET_CODE_IN_BODY、INDUSTRY_MARKER_WITH_KEYWORD_ONLY | 一致 | 标题含“行业”，600362 仅在表格，判为行业背景。 |
