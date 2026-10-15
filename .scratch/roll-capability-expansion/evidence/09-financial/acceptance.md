# 09 利润表切片验收

## 交付及边界

独立 AKShare1.19.1/MIT/Python3.13.12；业务依赖未改变。源码 SHA 为 e9cb438a5e033e9ba2d14c0341528b1aeec3f162fb2c0e5cbff41a6bc293348e，wheel SHA 为 8ab82d4a468d2c384df02de470df3a44e8b899fd8cfe116bceff52dd7b804df9。完整依赖清单及许可证分别见 akshare-lock.txt、AKSHARE-LICENSE.txt。

公开利润表查询/有限采集/取消→HTTP实体原件→不可变观察版本→单股/PDF页链接已接入。默认来源关闭、只支持有限名单600362。未配置隔离Python时给出失败回执。保留原字段、NULL、负数、日期精度、来源更新与首次接收。先保存原件再规范化，内容重复不增版本；修订来源流关联与财务可比口径分开。

该票当前 **partial**：真实 SDK 有限来源评估已完成；整条生产 API→子进程→数据库→页面链只用保存响应作 METHOD 验收，尚未再次执行当前版本的真实联网整链。已封口来源预算没有重开。不能把两种证据合并宣称生产整链已运行。旧量价指纹、真实账户、资格、前向计时均未改变。

## 实际来源与文件

actual-plan.json 与 actual-source/attempt.json：一次18秒/8MiB/8calls封口评估，实际3次匿名HTTP成功，SDK返回5期利润表，零重试。原公司页516112B、日期索引21042B、利润表43896B；SHA分别为 3b9cf8a79304b301c99532783bbfa6a31eae98f1c9d92fd2c3f4d58bf3bd8842、697349c3954772a1c5c6dd318579ae7cc0ce19caaa80aa8f96f5aa12b5f7fcdc、06c52947d5c822ac625a9bb92f78d070a39a7e56e809c8f8e69d7f36dfbca4cc。原日期索引103条，库接收最近5个不同期间的明确派生视图。DataFrame不是原件。

另一次明确的来源格式JS计划（1HTTP）及独立PDF固定下载计划（4HTTP/45秒/32MiB）均封口，见各计划与回执。已存4份发行人PDF，经pypdf提取和Poppler页图目视核验：2025年报PDF103页、2026半年PDF62页、2026Q1 PDF10—11页、2025Q3 PDF10—11页。原件位于本目录，运行时语义引用及预期SHA位于 financial_reference。2025-H1使用2026半年报比较列，其UPDATE_DATE为2026-08-26，首次接收仍为2026-10-15；不回填到旧公告日。

## METHOD 和工程验收

- API首次红灯 api-red03.log：404。之前两个红灯为测试关注列表前置条件错误，原日志保留。
- api-green02.log：1 PASS/10.46s，原件/5期/幂等/重复内容/损坏/旧时点/重启。
- api-final.log：2 PASS/16.23s，补修订及取消。
- 审查发现收入或更新时间变化断开版本链，revision-red.log已复现；revision-green.log：2 PASS/15.68s，金额与更新时间修订仍链到旧版本，单位/合并口径UNKNOWN、不可比，账户版本0。
- SDK固定实体测试 sdk-method02.log：2 PASS/6.71s，真实锁定SDK处理成功和503原件；先前fixture文本读取归一化CRLF导致失败，已改按字节解码，未改源文件。
- 强杀回归 sdk-prefix03.log：3 PASS/10.16s。真实SDK子进程固定慢响应收到8192字节后被杀，原件前缀及SHA保留，完整标记false。之前两次日志保留了Windows日志重命名读句柄竞争失败；测试改为轮询前缀文件状态，不占用journal读句柄。
- Chrome browser-green02.log：1 PASS/16.4s，空态→显式采集→5期值→原响应200/PDF200→重载→390px无横向溢出。浏览器全METHOD、实际网络0。首轮错误导航名及重载后缺导航的失败日志保留。
- build.log：TypeScript/Vite构建通过。
- standards-review.md、spec-review.md：两项P2均已修复并复审，开放发现0。评审没有额外联网或测试。

15份原现场保护文件（仅剔除本feature新增hunk后）SHA无差异，12份旧模型依赖相对fe5d01c7未变，见 preservation.json、model-preservation.json。app.py及collection_sources.py使用缓存专用补丁，原SSE未提交改动留在工作树。

剩余：在下一次明确允许的真实单证券采集请求中验收当前生产整链；该运行不得自动重开本次封口评估。不因缺这一运行而声称财报/PIT/模型资格已完成。后续三表与Docling票仍保留各自验收要求。

最终修复后浏览器 browser-final.log：1 PASS/16.1s；build-final.log PASS。最新报告期优先，原件/PDF与移动布局通过。
