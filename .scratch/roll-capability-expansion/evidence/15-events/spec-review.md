# 15 规格审查

对照 [issue 15](../../issues/15-news-entity-dedup.md) 与 spec ID-09。

| 验收条件 | 结论 | 证据 |
| --- | --- | --- |
| 规范URL/内容hash精确去重；逻辑事件组与全部原件引用；不先建 datasketch 大索引 | 通过 | news_events.py；news_event_members；events-green.log 同文异URL/修订/同标题异内容 |
| 证券关联分明确公司/行业背景/不相关/不确定；多对象按对象保存；查询词命中不自动证明相关 | 通过 | real-association.json 四类分布；events-green.log 多对象；别名冲突测试；manual-review.md |
| 数字/日期/否定/更正变化不误并；相似组保留版本与参数；重跑不抹旧判断 | 通过 | 内容SHA256为合并键，同标题异内容分事件；news_derivations/参数版本；INSERT OR IGNORE 追加式表 |
| 页面按事件展开转载和修订；汇总用唯一事件数；多媒体同上游不增加独立证据 | 通过 | news-panel.tsx；browser-real-green.log；汇总文案 |
| 公开接口+真实SQLite验同文异URL/同标题异内容/修订/别名冲突/多对象/重启幂等；小样本手工核查留证 | 通过 | tests/application/test_news_events.py；real-association.json；news-regression-final.log；manual-review.md |
| 版本、公开行为验收、真实/METHOD边界、失败与剩余条件 | 通过 | acceptance.md、code-versions.json、events-red.log |

## 发现与处置

- 审查发现把名称与代码对象按“最长表面”合并会丢失“标题含代码/正文含名称”的区分，已改为按 (instrument, where, role, kind) 合并，并补充逐位置对象；修复后 6 passed、真实样本恢复 4/2/2/2。
- 事件ID由主事实ID确定，新增修订不改变既有事件ID；重启测试验证 event_id 与关系一致。
- 未发现阻断项。近近似转载不合并是本票的明确保守边界，不是遗漏。
