# 07 固定五背景补充验收

在 d07496c 集成基线上补齐票13的30股+5指数容量输入：仅增加预固定沪深300 `SSE:000300` 和中证500 `SSE:000905`；其余三背景、持仓/关注边界不变，交易能力全部NONE。拒绝新增两指数关注（422）、RESEARCH/OBSERVATION用途（403），BACKGROUND可取日线。未更改13 registry、CAL40、模型、训练/封存或阈值。

## 身份与原件

- 官方[中证沪深300事实表](https://oss-ch.csindex.com.cn/static/html/csindex/public/uploads/indices/detail/files/zh_CN/000300factsheet.pdf)名称沪深300指数、代码000300；当次2026-08-31 PDF原件454479 bytes、SHA `8653755655ded0148202f0e43a20d36e9beaa1682a09b0c8e6d84f321f13c056`留存运行目录。
- 官方[中证500事实表](https://oss-ch.csindex.com.cn/static/html/csindex/public/uploads/indices/detail/files/zh_CN/000905factsheet.pdf)索引内容名称中证小盘500指数、代码000905、彭博代码SH000905。Web读取的索引版本标2025-10-31，仅用于稳定身份核验；直接/配置代理HTTPX下载超时，未声称该PDF原件已归档，也未复制指标用于研究。
- 官方扶摇[指数文档](https://fuyao.aicubes.cn/docs/api-reference/a-share-index/)明确沪深300标准码000300.SH；使用宿主key完整thscode精确 `/api/meta/tickers/search?q=000300.SH&limit=5` 和000905.SH查验两者SH/a-share-index/CNY/中文名，ticker分别1B0300/1B0905，不把ticker内部码代替thscode。完整响应原件SHA及身份见[manifest](background-identity.json)。加SSE/asset_type过滤的限定检索实际返回空列表，去过滤完整码查询成功；保留空响应，不把无结果当不存在指数。

## 方法与实际证据

公开FastAPI + 真实SQLite/原件归档TDD：固定名单权限新测试先因3≠5失败；Fuyao请求映射新测试先因新增对象OUTSIDE_FINITE_LIST失败。仅增加固定两对象后，[名单/规则+Fuyao相关22项](background-related.txt)通过（46.70s）；两个新案例检验权限、000300.SH/000905.SH单对象端点、无adjust、背景事实禁止个股模型、离线回放与账户不变。

[真实运行](background-real.json)2026-10-08：两次外部日线调用，仅BACKGROUND/2026-09-01—09-30，各21条RAW，共42条。两原JSON与Parquet逐件下载SHA一致；离线回放与事实相等、联网0次；进程关闭再开启原run相同、回放0次；账户未写且不变。模型/训练/封存结果未读取。历史PIT/总历史完整性仍false，指数点位不能当股票价格量额均价。以固定范围输入为工程资料，不授概率/校准能力。

初次运行相同取数与所有验证完成后，脚本打印不存在network_calls字段抛KeyError；[原运行](background-real-initial.json)及[失败输出](background-real-initial.txt)保留。修正打印后使用新隔离目录，第二次同样仅两外部调用，成功退出输出见[最终stdout](background-real-final.txt)。没有覆盖初次数据目录。未全套后台/浏览器重跑；容量/页面联验由票13负责。

新增运行/身份/脚本/输出另列 [runtime-preservation-background.json](runtime-preservation-background.json)，原181项清单不变；清理工作树前须按补充manifest同样保全原件。密钥仅宿主读入，未复制.env，已对变更与新增运行检查两个实际key精确字节，无泄漏。
