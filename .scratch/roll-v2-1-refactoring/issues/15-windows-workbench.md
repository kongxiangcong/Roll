# 15: 在 Windows 贯通三个页面、CLI 与 WorkBuddy

Status: ready-for-agent

**What to build:** 通过本机单进程入口贯通晴雨表、持仓与跟踪池、回测与校准，并从 WorkBuddy 读取导出结果。

**Blocked by:** 04, 05, 11, 12, 14

- [ ] 使用一份浏览器端到端配置走通同步、看盘、记账、回测与日报；各页按需读取，市场首页可独立于账户加载。
- [ ] 从命令行验证同步、报告、回测、启动服务四项操作；CLI 与网页并发生成同日的报告，均返回首次冻结内容。
- [ ] 验证 WorkBuddy 可读取 JSON 或 Markdown 冻结结果，断网重读并核对截止时间。
