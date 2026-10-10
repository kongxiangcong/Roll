# Standards

只读范围：`git diff d1b867e...14568b1582f9500ee091dabe2b741224e95e5322`；生产与测试源码固定在 `a7de4632927c48b2a25e1d937dc5ea7c17bf2b7f`，后续仅补充文档与验收材料。未运行测试或外部调用。

- **[P2] 文档规范违反：归档复用直接依赖市场模块私有存储。** `backend/src/roll/agents/codex_process.py:469–474` 在 `reuse_source` 中用 `host.evidence.ledger.connection()` 执行 `SELECT value FROM evidence_dependency_invalidations`，并自行读取 `changed_raw_hashes` / `verification_changed_raw_hashes` 判定是否重新取数。该表由 `market/resolution.py:54` 创建、由其 `activate` 维护；Agent 因而依赖市场内部表名和失效字段语义，市场调整失效结构时需要同步修改 Agent，漏改可能继续复用已修订依据。共同约束 `.scratch/roll-p0/project-layout.md:63` 明确要求“跨目录通过少量类型化命令/查询传递已定义结果，避免互相读取私有实现”。应由市场模块提供小型的原件复用有效性查询，在宿主组合处显式传入；Agent 只消费有效/需重新核验结果。

对应新增 hunk：

```python
with host.evidence.ledger.connection() as db:
    for row in db.execute('SELECT value FROM evidence_dependency_invalidations'):
        invalidation=json.loads(row[0])
        if hashes & set(invalidation.get('changed_raw_hashes',[])+invalidation.get('verification_changed_raw_hashes',[])):
```

未发现其他明确文档规范违反；无独立且足够有依据的 baseline smell。上述存储耦合已有文档规则支撑，不重复计为 heuristic finding。最终材料明确保留 METHOD/真实接入差别、旧失败、19 needs-info/partial 与资格未启用边界。

合计：1 条文档规范问题（P2），0 条独立设计气味。
