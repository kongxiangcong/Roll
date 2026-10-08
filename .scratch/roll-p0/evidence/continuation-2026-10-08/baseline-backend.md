# 本轮完整后端基线

2026-10-08，Asia/Shanghai。源码基线为 `d1b867e`；实际运行期间根分支 `6842461` 仅新增 `.env` 忽略及本轮元数据，没有产品源码变更。测试退出前未合入票 12 或扶摇适配。

命令：在 `backend` 执行 `.venv\Scripts\python.exe -B -X utf8 -m pytest -q`。

实际退出 1：**3 failed, 340 passed in 1551.23s (0:25:51)**。

| 既有失败 | 实际结果 | 夹具时点 |
|---|---|---|
| `test_reviews.py::test_intraday_current_bar_cannot_replace_last_complete_daily_or_refresh_old_quote_time` | `last_complete_daily` 为 null，访问 trade_date 报 TypeError | review_clock 固定 2026-10-08 10:00，原件实际获取晚于该时点 |
| `test_source_resolution.py::test_cache_preserves_real_receipt_and_rechecks_own_knowledge_cutoff_and_session_usage` | DEGRADED，期望 HEALTHY | market_clock 固定 2026-10-08 08:30，原件实际获取晚于该时点 |
| `test_source_resolution.py::test_old_quote_blocks_current_monitoring_but_optional_status_gap_only_degrades_record` | observation 为 DEGRADED，但 facts 为空 | market_clock 固定 2026-10-08 10:00，原件实际获取晚于该时点 |

上述为本轮变更前的基线失败，不算新回归。需要统一修复冻结业务时钟与原件接收时钟不一致的测试夹具；不得放宽生产历史知识截止门禁。此前 2026-10-08 早晨的 343 passed 仍属于其原运行，不改写为本轮结果。

最初普通沙箱命令因 pytest 临时目录权限失败，未构成有效产品基线；uv 缓存权限及 esbuild spawn EPERM 亦为环境前提。获准在正常 Windows 进程环境运行后得到上表结果。锁定前端依赖安装后，原产品 TypeScript/Vite 构建 53 modules 通过。
