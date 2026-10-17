# 15 工程标准审查

- 结构：纯函数归并/关联与 FastAPI/SQLite 持久化分离；未引入第三方依赖（datasketch 未安装），符合“精确hash先行”。
- 边界：测试走公开 API 与真实隔离 SQLite，不锁定内部调用次数；新增浏览器用例只验用户可见事件分组与分类。
- 数据：派生表只追加（INSERT OR IGNORE），不更新旧事件/旧关联决定；事实、原件、采集运行和账户表未改写。
- 一致性：规范URL只允许 http(s) 且有 host，无凭据；内容哈希基于标题+正文（缺失时摘要）；事件关系显式 ORIGINAL/REPRINT/REVISION/LINKED。
- 前端：不新增全局样式或入口；事件与事实都是语义 section；移动端 390px 验证；无 dangerouslySetInnerHTML，正文按文本渲染。
- 安全：无网络、无文件系统外部读取、无 LLM；关联对象只来自已注册身份，不解析任意公司名。
- 可维护性：规则阈值/版本集中在 news_events.py；中文别名去法律后缀是确定性规则，已在验收限制中说明可能过度匹配（如“集团”后缀）。
- 复现：events-green.log、news-regression-final.log、build.log、browser-real-green.log、real-association.log 均为本票命令输出；code-versions.json 固定源文件 SHA256。
- 开放问题：无阻断级；近重复语义合并不在本票范围。
