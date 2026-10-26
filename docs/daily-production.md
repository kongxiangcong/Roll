# 日常版发布与运行

基线 codex/roll-capability-expansion @ e47013fd；阶段规格见 [.scratch/roll-daily-production](../.scratch/roll-daily-production/README.md)。

Windows：安装 Python 3.12+、uv、Node 20.19+，在干净仓库执行 `./scripts/install-roll.ps1`，然后 `./scripts/start-roll.ps1 -DataDirectory <账户目录>`。打开 http://127.0.0.1:8010。网页由API提供构建产物，不需要开发服务器。旧服务先 `-Stop` 再启动；`-WebPort` 只保留旧启动回执身份兼容。`-Status` 检查API、worker和网页；日志在账户目录/logs。

`GET /api/runtime/release` 给出实际源码提交、脏工作树状态、依赖锁指纹和前端构建身份。变更代码后重新构建、停止再启动。默认不开启情绪模型；如需现有分类，配置 `ROLL_SENTIMENT_PYTHON`、`ROLL_SENTIMENT_MODEL_DIR` / `ROLL_SENTIMENT_RESEARCH_MODEL_DIR`；所有原模型文件哈希仍需匹配。新闻/财务隔离运行环境沿用 docs/daily-use.md，不配置时只影响该来源。

首次启动自动建库/迁移，复用原升级前备份。设置页创建并导出完整备份；恢复包先检查再登记，停止所有本账户服务后重启执行恢复。恢复后保留 RECOVERY_LOCK，观察可用，授权及账户核对按原恢复流程执行。不要复制正在写入的 SQLite 文件作为备份。

发布缺口：基线 app.py 引用未纳入Git的 roll.market.sse_daily。日常启动现隔离该缺失模块，相关研究写入口返回503/SSE_DAILY_MODULE_NOT_SHIPPED，发布身份明确列出；没有重建或声称该研究功能可用。其原始历史工件保留。

Linux仅验证核心API/SQLite/构建；采集器子进程的Windows Job Object隔离与PowerShell启停仍以Windows为支持环境。没有将Linux核心测试等同于Windows发布验收。
