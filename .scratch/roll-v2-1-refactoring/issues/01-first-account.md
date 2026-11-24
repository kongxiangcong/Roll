# 01: 从 v2 独立入口记第一笔账

Status: ready-for-agent

**What to build:** 从空账本录入资金与实际成交，重启后核对真实账户镜像。

**Blocked by:** None (can start immediately)

- [ ] 新入口按需启动，使用共用的 SQLite 连接设施；账户模块在同一事务内完成十进制记账。
- [ ] 录入一笔资金和一笔成交，退出并重开，现金与逐证券数量和录入记录相符。
- [ ] 重复确认返回原回执，账户事件只入账一次。
