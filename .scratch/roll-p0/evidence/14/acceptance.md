# 14验收：决定性事实独立核验

开始2026-10-08T04:43:20+08:00；实际来源取得2026-10-08T05:10:56+08:00；最终真实联合Chrome及保全完成2026-10-08T05:42前后+08:00。源码冻结 `9a97b997cd7812e0a277347e555e1a4784a1c6ab`，包含实际最新集成 `c6cd196`（18/15），无新依赖。Python3.13.12、SQLite、已锁FastAPI/Parquet及Chrome154.0.8037.95；API8034/Web5194。适配器原字节SHA与真实最终记录相同，见[source-freeze](source-freeze.json)。文档结项另有后继commit。

## 分层结果

| 层级 | 实际结果与原输出 | 边界 |
| --- | --- | --- |
| FastAPI＋真实SQLite/原件/Parquet | [相关最终30项](raw/backend-final.txt)全部通过82.56s：本票13 application、08原14 application、3原生进程故障 | HTTP外部依赖固定METHOD，保留真实内部边界；没有声称完整后端/默认全浏览器通过 |
| 14/15后续交点 | [本票14项](raw/backend-joint-final.txt)全部通过39.45s；[并发三次只消费一次](raw/joint-green-final.txt)；[两原生联合崩溃＋15原触发](raw/joint-recovery-final.txt)3通过20.35s | 只测新增交点，不重复既有全仓/真实SDK |
| 17封存输入交付 | [定向1项](raw/sealed-joint-final.txt)通过4.47s | 独立create/query/history/replay＋15 consume/request-query六条实际payload均记封存日线暴露，confirmatory_pass_look=false；不签研究通过 |
| Chrome独立METHOD | [1项通过12.0s](raw/browser-method-final.txt)、[报告](raw/browser-method.json)、[页面](raw/browser-method.png) | 独立一致、同版本复用、修订失效、旧记录重放、两价格冲突；固定原始链仅方法材料 |
| Chrome联合METHOD | [1项通过12.7s](raw/browser-joint-final.txt)、[报告](raw/browser-joint.json)、[页面](raw/browser-joint.png) | 已存观察显式进入；原截止、原引用、一个核验ID和audit持久关联；普通审计不升级 |
| 真实市场原件＋Chrome | [最终2项通过13.1s](raw/browser-real-joint-corrected.txt)、[页面](raw/browser-real-joint.png)、[联合记录](raw/browser-real-joint.json) | 实际同对象Sina/Tencent仍不足；实际发行人原PDF重复只计一条；原PDF下载核SHA，原观察/账户不改；外部补查0/实际模型任务0 |
| 构建 | [最终tsc/Vite](raw/build-delivery.txt)通过50模块2.20s | 最后仅补实际缺口的中文显示标签，未重复来源取数/模型 |

## 原值与实际来源

根07永久保全 `backend/.roll-data/implementation-evidence/07/acceptance-07` 只读复用；只复制该目录43文件、2,707,432字节，逐文件原/目标SHA一致，见[输入清单](import-07.json)。自己的 `backend/.roll-data/14-real` 为新隔离目录；原源DB/文件未写、未移动。API真实调用新浪一次取得SSE:600519 2026-09-30报价，原请求、RetrievalRun、原件和Parquet见[实际报告](raw/real-run.json)；没有SDK/模型调用或认证复制。

最初样例选错腾讯背景指数QUOTE，原记录及[原报告](raw/real-run-initial-incomparable.json)完整保留，实际结果含对象/单位/时点不可比。复核后按 `instrument=SSE:600519/group=QUOTE/source_id=tencent-quote` 选原07 `cf2ceab5-0f16-4b33-8e0e-44dd5ab2635a #0`，与实际新浪 `d90eb9bb-1158-4f68-94e7-ee575697bfcb #0` 比较，原字符串1258.62/1258.620；[纠正输出](raw/real-correction.txt)没有重新联网或覆盖初记录。六次原件下载核验对应四个唯一原件/PDF。原07腾讯metadata未建立currency/adjustment且时点16:14:58不同于新浪15:34:59，保留口径缺口；两供应商独立原始生产链也未证明，结果 `INSUFFICIENT`，不因为Decimal相同签VERIFIED。相同版本复用和原07/新浪输入重放网络0。

真实发行人MAJOR_EVENTS公告 `AN202607171827064564` 披露日期2026-07-18及原PDF SHA `24e51c43dfc6da7d3a19c67b88081715a3a3b4a26c2d83ec51a557e3e5692873`，重复引用只计“发行人＋公告”单一依据，结果不足。归档metadata/不同托管页面不能产生第二原始生产者。现实两个独立生产者的一致正例尚不存在；本票完成的是该门禁及真实不足路径，不是为这些源认证独立。

最终真实联合核验 `5e1a8706-16cf-4551-8f40-94706eeec3b0` 关联实际观察 `aa3e6702-8c6d-494a-86fd-0d27fac78474` 与原审计，请求保持原knowledge_cutoff。实际原观察result不变，账户不变；源版本事实经17审计。查询副本SQLite实查CODEX/DEEPSEEK任务0、原观察retrieval_runs为空、network_seconds=0，见source-freeze。个人真实到账/成交或资金授权没有被核验修改。

## 决定性方法案例与红绿证据

- [01红](raw/01-red.txt)→[绿](raw/01-green.txt)：缺公共路由；ROUTINE拒绝，供应商/工具不签独立，账户不变。
- [02红](raw/02-red.txt)→[绿](raw/02-green.txt)：重复原始链只计一次；两个明确合成独立原始生产者且口径一致，METHOD可核验。
- 冲突与其他字段继续[首次已绿](raw/03-first-run.txt)：100/101可比才CONFLICT，时间不同比较不足，另一个已核日期仍READY；未伪造红。
- [04红](raw/04-red.txt)→[绿](raw/04-green.txt)：同证据版本复用；08价格修订使旧结论失效，原值及重放不覆盖。
- [05—09红绿](raw/09-green.txt)分别核：后知材料不足、单位未知、重复不计票/等价时区、重提交旧原件新UUID仍失效、损坏原件不阻断无关字段。
- [仅原字节/链变化红](raw/raw-version-red.txt)→[两项绿](raw/raw-version-green.txt)：规范数值未变也失效，08既有原事务保留。
- [基本校验红](raw/basic-check-red.txt)→[绿](raw/basic-check-green.txt)：两个相同close仍不能掩盖OHLC非法。
- 金额CNY[首次已绿](raw/unit-amount-first-run.txt)、RAW/QFQ/17[补充首次已绿](raw/supplemental-first-run.txt)，不作虚构红；RAW一致METHOD可核，等值QFQ不拼接。
- [联合缺路由红](raw/joint-red.txt)→[绿](raw/joint-green-final.txt)：三并发一个ID，重提交保持audit；原观察不改，来源修订后同ID失效。中间[时区字符串断言失败](raw/joint-green.txt)是测试过严，改同一瞬间比较，保留原冻结字符串。
- [原生进程红](raw/process-red.txt)→[3故障绿](raw/process-green.txt)：SQLite提交前0条、提交后/回执后1条；实际UVicorn进程退出/重启及原Parquet复放。新增两次联合提交前后进程故障验证请求、核验和audit全部原子恢复。

Chrome缺入口的[红](raw/browser-red.txt)保留；真实[首次定位器严格匹配失败](raw/browser-real.txt)保留。真实联合[首次失败](raw/browser-real-joint-final.txt)揭示误选指数引用并促成上述原件纠正。方法最后一次首次命令使用错误工厂名字只属启动前提错误，修为仓库实际 `verification_method_app:factory` 后再运行，通过结果见表，未把启动失败当产品红。没有以METHOD材料关闭真实双源独立性问题。

## 保全与范围

[运行保全](runtime-preservation.json) 精确登记九个已停止源目录；复制412文件、34,205,250字节至本树 `backend/.roll-data/implementation-evidence/14`，源/目标每项SHA与长度一致、mismatches0、auth_named_files0。每级拒绝junction/reparse/symlink，未复制个人配置/凭据，未移动/清理原件；SQLite原DB/WAL/shm均保留。后续只在额外自己 `14-freeze-query` 的DB副本只读计数，永久源/目标未重新打开，清单注明其他测试暂存仍留本树。

原件/SQLite均忽略、不stage；Git仅存公开脱敏报告、输出、截图及清单，`.gitattributes`保存捕获原字节。root保全应按清单精确复制，不把新copy时点变成材料可得时点。未修改父execution-status；12真实认证/13后端隔离、正式资格及未来权益/新行情真值仍由对应票验收。本票AT-79/80/85的明确触发、独立性、冲突vs不足、复用失效/回放及真实内部故障路径已实施；现实源不足就是输出，不补造依据。

2026-10-08T05:48:00+08:00 最终合实际新root7505019（19模型/forecast路由及其保全），merge tip 8b5867ad1c9c6c79521bc7933af0cd3cb39ab358；保留双方app/history/模型与14/15路由，合并冲突只为浏览器说明两段追加，全部保留。14适配器SHA未变，新增最终[两个交点7.97s](raw/latest-integration.txt)与[51模块build2.02s](raw/build-latest-integration.txt)通过；不重复30项/真实模型/新HTTP。412文件/34,205,250bytes源与目标[重新核验](raw/preservation-recheck.json)0差异；最后两个方法临时目录jI登记保留，不复制凭据。
