# CSV解析候选定向适配结论

2026-10-07重新只读取得DSA固定提交 `ce364e457aab288863a5707e7b3df79786ad07f2` 的[src/services/portfolio_import_service.py](https://github.com/ZhuLinsen/daily_stock_analysis/blob/ce364e457aab288863a5707e7b3df79786ad07f2/src/services/portfolio_import_service.py) 与[LICENSE](https://github.com/ZhuLinsen/daily_stock_analysis/blob/ce364e457aab288863a5707e7b3df79786ad07f2/LICENSE)。实际HTTP200、字节数与SHA见[检查记录](../.scratch/roll-p0/evidence/03/component-inspection.json)。MIT，Copyright (c) 2026 ZhuLinsen。未复制第三方生产代码，没有第三方代码摘取资产；未来实际摘取须保留完整MIT文本及该版权。

评估的具体候选是CsvParserSpec/别名表、`_read_csv`编码回退与`dtype=str/keep_default_na=False`、`commit_trade_records`提交循环。字符串读取避免前导零/空值自动变化的思路有益；但专用券商列别名缺少用户脱敏真实样例，不能证明支持。自动编码回退会隐藏解释选择；逐行调用账户服务允许部分提交，不满足Roll整批原子语义。

分类：**仅参考设计**。Roll有明确模板，标准库csv/显式编码已足够，未摘取解析器；原服务直接pandas及内部证券解析/配置/PortfolioRepository/PortfolioService依赖不进入Roll。SQLAlchemy/仓库整体账户服务不采用，财务事实继续使用唯一Ledger。实际新增运行/开发依赖均为0，原锁文件不变。

语义适配：精确原字符串＋显式未知费用；原文件SHA/行号＋可靠分笔标识而非委托去重；已确认事实与草稿区分；单批账户版本/幂等/原子回执；原件先持久化、确认前指纹校验；文本作为材料。分类和实现取舍通过Roll公开FastAPI测试及真实进程/Chrome行为检验，见[03验收](../.scratch/roll-p0/evidence/03/acceptance.md)。未运行DSA代码，也不把DSA自身测试算成Roll通过。
