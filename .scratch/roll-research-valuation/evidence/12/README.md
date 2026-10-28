# 12 联合真实验收检查点

最新本地[资本准备05](capital-prep05/README.md)：仅同已批准FY25年报字面新增35数字/10原文，公开API新副本冻结49facts/98190B与QUEUED source-only候选预览，exactSHA74f156b5...5989。原12materials逐项same、原51facts/input/c549/9797不变，明确遗漏清单与真实经济分类未知。0新增外发/0纠错，批次仍2/16；未发布估值/章节/PDF，Completion及A6/A7/A8不升级。

2026-10-28 Asia/Shanghai。**Completion: blocked，整体未完成**。本票没有另改生产源码；统一review修复8dd639解决原P1/P3。人类已授权特定14+2批次，最新[authorized04](authorized04.md)记录实际2/16：Lulu exact候选BLOCKED、JCC exact经营分析COMPLETE/新core，Lulu章节与纠错均未执行；旧checkpoint03待授权叙述已被可信授权记录取代。新的经营研究、真实网页、受控升级及必要恢复分账，不用已有05估值复用或新BLOCKED替代A6/A7。

本票新增实际来源、当前代码HTTP、真实网页新任务、重启及新目录恢复证据，详见[覆盖矩阵](coverage.md)、[最小差距与输入准备](readiness.md)、[运行/恢复交接](../../../../docs/research/company-research-usage.md)。未以旧证据目录整理、METHOD或新PARTIAL版本关闭本票。

198dd652后的最新实际补充见[postcheckpoint02](postcheckpoint02.md)：隔离两JCC公共源启用/已安装runtime接线、真实手动采集12 recorded network_calls、22新fact/8口径gap/2新闻拒绝、无auth新analysis UNAVAILABLE、第二个真实恢复，以及仅本地编译未发送的一份JCC exact command待审阅。此手动结果不增加自然盘后0/2。

## 本次实际工作

- [real-store.json](real-store.json)：公共Backups从rv11-real01恢复新rv12-real01；[daily-store.json](daily-store.json)另从rv07-real01恢复新rv12-daily01。原生产、07–11目录及服务不覆盖。
- [live-receipt.json](live-receipt.json)：8032当前12代码API核固定DAILY/REPORT/snapshot完全相同；六文件真实HTTP SHA不变；JCC真实身份在新库另注册本地ID ed1e10ad...，600362/00358/HKEX:00358归同公司；跨公司snapshot422。8033的真实JCC daily仍取其原e28c866f快照，未把露露财务胶合到JCC。
- [primary-acquisition.json](primary-acquisition.json)：两个官方PDF实际GET均200；原2025年报1056117字节/8c620b0b...一致，新深交所2026半年报831422字节/da5795d5...、139页，封面实际视觉检查[截图](halfyear-cover.png)。公开API导入material196c4aba-1620-496a-bc8b-dfddcca95d13，未造财务事实或新经营结论。
- [actual-annual-check.json](actual-annual-check.json)：另一次实际GET精确年报SHA后，公开service保存SUCCESS/0新增。范围只有该年报原件，不能代表公司全部披露已核查。公共context子版本6b94c24a-f27a-4e5b-a6f9-57358d8242a6，core仍37b719...；日报取到新核查，研究依据日期不刷新，原报告仍绑定7a430。
- [browser-receipt.json](browser-receipt.json)：CUA IAB browser2/tab2从000848解析、原报告预览/任务/历史、实际旧MD与PDF下载、同快照只读跟踪，再从网页选择新context子snapshot创建job3bbfac4c...。真实无auth worker运行后十二次UNAVAILABLE，发布新PARTIAL report8625ead2...，新MD实际下载SHA相同；**0次模型发送，不是12篇真实生成章节**。切回旧报告后刷新，新任务指针仍恢复。生成新PDF没有点击。
- [restore-receipt.json](restore-receipt.json)：实际HTTP backup83b2df11-2f3b-492c-9aea-da0852c12799，8883583字节，正常启动恢复到新rv12-restored01；15原件、2快照、2报告、新job、原六文件逐字/SHA相等，计算确定性重放、account0。恢复不调用模型/外部源。
- [restart-receipt.json](restart-receipt.json)：核PID/ticks/命令后仅重启自身8032 API；七个稳定公共记录及新增原件SHA相等。原进程身份、stop回执、新launcher29384/ticks639287461689967536见本目录。两worker与其它服务未停。
- [source-readiness.json](source-readiness.json)：对已保存真实Q3 PDF重新逐页核37/37数值字面存在，独立Decimal复算三现金流之和及期初/期末现金等式；这不是FCFF。新增半年报139页建立具体附注页码索引，仍不把6月附注当9月证明。
- [daily-configuration.json](daily-configuration.json)：隔离8033两关注证券research_postclose开启、其他三类关闭，news_refresh=true但来源仍按原配置/范围/预算，classify=false。worker显式清除模型auth配置、不load.env；新事实若需CODEX只能记录UNAVAILABLE。无待运行报告/辅助/观察队列。真实时钟未改，无平台automation。

## 工程与真实证据分账

[method-joint01.txt](method-joint01.txt)：11 passed/6 deselected/77.26s，既有公开service测试覆盖A3核查与过期、A4算例、混合因素固定顺序、AH缺价和不兼容基准。不是实际行情、模型、自然盘后周期或预测效果。初次session返回延迟被误判为无输出，读取后证实已成功；第二次重复命令在无输出时中止，exit1空日志不计通过，未再跑宽suite。

首次新库JCC创建误传源库company_id触发404；第二次已完成实操作但回执字段误用status触发KeyError；修正使用公共completeness字段后的verify-live03完成。失败原文保留attempt01/02，重复请求用幂等键，不新增公司/材料版本。首API sandbox后台退出，无监听；实际host02经合法提升启动。Kimi日志ACL失败后用CUA IAB；首浏览器连接早于Vite启动、子代理visible参数不支持均未算UI成功。取消按钮点击发生在任务已经快速发布后，无匹配控制且未发生取消，不能宣称新任务取消验收成功。

主报告库来源公网有3次PDF GET；另daily副本实际手动probe的适配器回执记录12 network_calls，见postcheckpoint02。网页新任务本身source_network_calls=0/model_calls=0。08既有真实CODEX和09既有45页PDF视觉验收分别引用原证据，不改称12新调用或新PDF生成。所有live stdout/stderr保留在隔离store/logs，未stage持续写入日志。

## 仍未通过

A6完整真实正向研报、A7完整新真实模型网页链、A8两自然盘后周期仍NOT_PASSED。当前真正周期0/2；10月28/29日15:05仅是最早可能观察时间，主机/worker/来源不满足则顺延。ARCHIVES_ONLY、来源scope unsupported或SOURCE_DISABLED不能冒充真实公源无新增。当前current pricing blocked和baseline conditional不升级。无fit、SEALED读取、旧预算重置、账户事件或资格授权。

root最终review修复须合入后重启本票host并核新模块路径，再做与修复匹配的必要真实链验证。不要依据本检查点把12或整体spec标complete。
