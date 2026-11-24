# 01: 从 v2 独立入口记第一笔账

Status: resolved

**What to build:** 从空账本录入资金与实际成交，重启后核对真实账户镜像。

**Blocked by:** None (can start immediately)

- [x] 新入口按需启动，使用共用的 SQLite 连接设施；账户模块在同一事务内完成十进制记账。
- [x] 录入一笔资金和一笔成交，退出并重开，现金与逐证券数量和录入记录相符。
- [x] 重复确认返回原回执，账户事件只入账一次。

## Comments

独立入口为 `python -m roll.cli --data-dir DIR account`。`show` 读取镜像，`draft` 从标准输入接收 JSON，`confirm DRAFT_ID KEY` 在同一 SQLite 事务确认并返回回执。缺省目录为本机 Roll 数据目录下的 v2。

`backend/tests/test_v2_account.py` 两项通过。每次操作启动新 Python 进程：零资金基线、转入 5000.10 元、以 21.321 元买入江西铜业 100 股、费用 5.01 元。重启后余额 2862.99 元，持仓 100 股；用原幂等键重复确认返回原回执，成交记录仍仅一笔。
