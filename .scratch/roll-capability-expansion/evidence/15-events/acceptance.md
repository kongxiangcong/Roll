# 15 新闻证券关联与转载去重验收

Completion已具备全部工程与真实样本验收条件。新增确定性事件归并与证券关联；原文、清单响应和旧判断不被覆盖。

## 交付

- `backend/src/roll/market/news_events.py`：规范URL（https+host+path，去查询/片段）、正文内容SHA256、并查集事件组、转载/修订/关联关系、注册身份的名称/代码标题正文匹配、四类关联（COMPANY_SUBJECT / COMPANY_MENTIONED / INDUSTRY_BACKGROUND / UNRELATED / UNCERTAIN）与别名冲突。
- `news_ingestion.py`：新增 `news_events`、`news_event_members`、`news_association_decisions`、`news_derivations` 表；`GET /api/market/news/{instrument}` 增加 `events`、`unique_event_count`、`reprint_count`、`revision_count`、`association_counts`、`derivation`，每条事实增加 `event` 与 `association`。派生写入只 INSERT OR IGNORE，旧版本/旧判断不更新、不删除。
- `frontend/src/components/news-panel.tsx`：按事件组展示，事件标题显示分类与转载/修订计数，汇总使用唯一事件数；逐条显示事件关系、证券关联、关联对象与别名冲突。
- 页面/接口保持原文不可变、账户/资格/前向不变；不调用外部服务。

## 真实数据验收（真实SQLite副本）

- 数据：`.scratch/r14real` 的隔离副本 `.scratch/r15real`，14 票实际归档的 10 条新闻、1 个采集运行。
- 注册身份：SSE:600362 江西铜业股份有限公司，依据 09 财务原件 `SECURITY_NAME_ABBR=江西铜业`、`600362.SH`。
- `real-association.json`：10 条事实、10 个唯一事件、0 转载、0 修订；分类 COMPANY_SUBJECT 4、COMPANY_MENTIONED 2、INDUSTRY_BACKGROUND 2、UNRELATED 2；账户版本 0→0。
- `real-association.log`：同次执行只读查询与派生，无网络调用。
- `manual-review.md`：代理逐条手工核查 10/10 与规则一致，并明确非独立人工标注、身份时点限制。
- `browser-real-green.log`：真实副本 Chrome 1 PASS/11.0s，校验 10 条→10 个唯一事件、公司主体/行业背景/不相关标签、390px 无横向溢出、0 采集POST；截图 `mobile.png`。

## METHOD 边界验收

- `events-red.log` 保留首次失败（事件数预期写错）；`events-green.log` 2 passed/16.05s：同文异URL→转载、同URL异文→修订、同标题异内容→不合并、多对象（000657 注册身份）、别名冲突→UNCERTAIN 且保留双方对象、SQLite 行数、重启后 event_id/关系一致。
- `news-regression-final.log`：news ingestion + events + SDK recovery 6 passed/44.71s；`build.log`：TypeScript/Vite 构建通过。
- 同上游多工具不增加独立证据：事件汇总只按唯一事件计数，不用媒体数或转载数加权。

## 限制

- 本 10 条真实样本没有相同URL或相同正文哈希，因此“真实转载/修订”未被样本证明；转载、修订、别名冲突与多对象仅由 METHOD 应用测试覆盖，不能写成来源事实。
- 近似转载（不同媒体改写同一公告）默认不合并；本样本不需要 datasketch，`similarity_candidates` 为空。数字/日期/否定变化因内容哈希不同不会被误并。
- 关联基于当前注册身份和确定性文本匹配，不使用 LLM/语义模型；不证明新闻与收益、情绪或交易动作的关系。
- 当前接口/页面是观察展示；`system_usable=false`、`capability=NOT_GRANTED`，不改变账户、资金、资格或真实前向起点。
