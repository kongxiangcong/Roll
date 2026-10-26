# 21 区块统计参照验收

arch 8.0.0/NCSA，Python 3.13.12，独立10项依赖见 requirements.lock。实际源码、版本、数值依赖记录在每份报告；官方PyPI wheel SHA见package-metadata.json，许可证原文见ARCH-LICENSE.md。业务依赖不增加；原statistics.py及12个旧模型依赖不改。

预登记method-before-evaluation.json先于首次计算，容差固定1e-12/相对0，20/40日非循环移动区块、2000次、seed1701。端点各为单侧95%，合中央90%。arch/PCG64与冻结Python/MT19937不要求逐次随机样本相同。每次实际arch索引回到原始日期组核对统计量，索引全序列SHA/首组索引/点估计与端点差异保存；解析常数例证另核对冻结方法。对照使用SHA绑定的原始rounded/paired_block_interval定义，在同一30秒受限子进程内执行，未重写或替换冻结算法。

同20的固定METHOD donor，manifest SHA528688f65d19849fffeead4aa8082adc9374dac471eff71ff504c483460c62e7，193文件哈希核对后仅打开副本。来源完整CAL40日历/20成熟事件，各阶段总体和p≥.60条件组×20/40日，共8项区间保持INCOMPLETE；未知日/同日未知证券不删除，不压缩。另6项人工METHOD常数/变化成对/空条件组正向运行实际arch，均数值一致。METHOD不补入来源支持，也不授统计假设/独立有效性/资格。

公开API运行→保存→列表/查询→幂等→无库重启/原件校验；报告入口、来源与METHOD表、结果明细和工件重放均可用。工件重放只验归档，不重新抽样。

证据：

- api-red.log：新增入口404，1 failed/14.40s。
- api-green.log：1 PASS/32.21s，首次正向完整API链。
- edges.log：冷环境测试未限定数值线程，30秒超时；保留失败，测试环境随后与生产worker保持相同单线程设置。未增加时间预算或放宽容差。edges02.log：1 PASS/5.28s。
- 审查P2：冻结bootstrap原在主进程，已移入受限worker按原SHA加载；final-api.log：API及实际库边界2 PASS/22.42s。
- 新同日已知+未知成员回归，edges-final.log：2 PASS/5.08s；未知仍保留为None。
- browser-final.log：Chrome 1 PASS/28.9s，实际库生成、8来源不足/6METHOD通过、原件重放、刷新保存版本、390px无横向溢出；mobile.png。
- build.log：TypeScript/Vite通过。
- standards-review.md / spec-review.md：P2修复复审，开放发现0。
- 首次statsmodels0.15下载停滞，确认仅本轮uv进程后停止，install-stall.log保留；固定兼容0.14.6后20秒HTTP/零重试安装10项完成，install.log。未修改既有业务或其他三个隔离环境。

preservation.json：15份原现场保护文件无差异（仅剔除本feature插入）；model-preservation.json：12旧依赖无差异。旧冻结、attempt预算、真实账户、前向起点均未改。票21工程完成，来源支持不足仍如实显示。
