# Standards follow-up

只读复核范围：`git diff 14568b1...6ad9928c71ebc0b3ffd59fcf8c9f25fdfc4c9461 -- backend/src`，并检查相关测试增量、`docs/review-contract.md` 与 `evidence/continuation-2026-10-08/review-fixes.md`。源码修复为 `db9ef0c`；未运行测试、外部调用或修改仓库/Git。

**原 P2：已解决。** `agents/codex_process.py:471` 仅调用 `host.archive_reuse_check(hashes)`，不再读取市场模块的失效表或内部字段。失效依据由 `market/resolution.py:79` 的类型化 `can_reuse_archives(set[str]) -> bool` 查询掌握；其读取权威 `source_revisions`，不改写旧审计。`app.py:340–348` 在组合入口显式为 Codex 与 DeepSeek 注入该查询。符合 `.scratch/roll-p0/project-layout.md:63` 的跨目录查询边界。此接口有两个现有后端调用方和实际来源修订需求，未添加基类、插件或纯转发层，不构成过度抽象。

**修复没有新增 Standards 问题。** 父请求 `adjustment_source` 被保留给实际子请求；没有新兼容层。`runtime/reviews.py:22` 将固定调用上限由4改为8，服务现有四宽基 DAILY/QUOTE 共8次请求；`reviews.py:299–309` 仍在持仓与背景之间共用剩余额度，保持原期限、字节、3次尝试及退避。契约和公开回归明确验证四个对象、八个请求、共享上限、缺口和账户不变，没有动态扩张预算或通用调度抽象。

验证依据由 fixer 提供，未独立重跑：4项公开来源/修订回归通过，90项相关组合通过，最终25项 Reviews/input/agent 回归通过。报告准确区分 METHOD 工程证据与实际接入；原全套366通过/1失败、夹具开发失败及旧审计保留。最终整仓与 Chrome 结果由根另行确认。

结论：原 finding 已解决；新增规范违规0，独立设计气味0。
