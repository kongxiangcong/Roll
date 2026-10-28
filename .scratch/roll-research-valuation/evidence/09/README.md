# 09 Markdown/PDF交付与恢复验收

09实现及文件层验收完成。基于08既有承德露露PARTIAL报告 `b9cfb2a0-8f93-516a-a4cd-7b7801fd7911` 追加三版文件交付，不调用新模型，不修改原报告、core或原始Markdown。最终交付 `e3e6e93c-0a17-4bfc-92af-82b86aa86487`，PDF45页，原始字节SHA `b135d59a72287ea6f998fd591882cc28de078f745741b7bc6d225ec1d7ddf408`；文件在[output](output/)。原MD仍134450字节/SHA `3970917631045c9c5a0ed88651849a8f2775b8a2d90711b8c0bdd2ebbc032720`。

## 改动和使用

- 独立不可变Delivery记录、manifest、固定输入、原件/事实引用索引和固定估值工件；复用EvidenceStore及Backups。文件版本与报告版本分开，幂等键冲突拒绝；失败重试追加父交付，旧文件/失败记录不变。
- 有界ReportLab纯文本渲染，中文字体嵌入、封面、目录、页码、书签、跨页表格；来源HTML不执行。图只能来自本报告冻结packet中的静态SVG；外部/file/data资源拒绝，无网络加载器。渲染默认45秒、最大90秒，每宿主最多2个，输出25MiB/300页上限。字体缺失/缺图/超时保留MD和独立失败状态。
- 实际API与生产字体/依赖说明：[交付API](../../../../docs/research/company-report-delivery-api.md)。依赖pyproject/uv.lock增加reportlab4.4.9、pillow13.0.0；锁文件既有包版本未升级，resolver修正httpcore2已有平台marker。生产不依赖Codex缓存、Poppler或本开发机路径。

## 已运行验证

红绿与错误分账见[commands.md](commands.md)。最终[regression08.txt](regression08.txt)：**8passed109.06秒**，覆盖6项09公共服务/API/渲染/备份测试与2项08原报告恢复/取消重试。未运行整个后端宽suite，也未重跑无关前端构建；09没有前端改动。

[real03-receipt.json](real03-receipt.json)：从独立8029完整API实际创建最终交付，6种白名单文件HTTP下载，SHA匹配，nosniff/attachment；任意文件名与编码越界路径404。历史3版，原report和前交付不变。经实际HTTP Backups生成 `0e55e47d-30c2-4fb2-9d5e-8decd0e8d2f1`，7137735字节bundle，恢复到新目录 `D:/dsh-proj/Roll/.scratch/rv09-restored01`；报告/交付记录相等，六文件恢复SHA相等，account0。

09原执行store为08备份恢复到 `D:/dsh-proj/Roll/.scratch/rv09-real01`，没有覆盖原08/07/05目录。09为API-only，不启动worker/模型；`serve_api.py`显式目录与runtime_role=API绕开.env加载，module-paths.json证实当前工作树。自身API实际listener22232/launcher3376，启动时间/命令见[api-receipt.json](api-receipt.json)，保持运行供10读取。原8010/5173、07/08服务未改。

## 视觉QA与真实失败

按PDF技能，首个PDF authoring前marker成功执行一次（exit0，无stdout）；没有为后续重渲重复marker。最终PDF03所有45页均以96dpi渲染；实现者实际查看12张四页contact图覆盖1–45页，另保留2/25/27/45关键原图。root独立检查目录、第9章长表/用途状态及最终45页。67张真实/METHOD页图及contact图SHA清单见[visual-qa03.json](visual-qa03.json)，关键截图在[screenshots](screenshots/)。原图保存在隔离store qa/pages03，未以文本抽取冒充视觉验证。

真实导出01发现附录表格行间空行退化为管线文本，补公开PDF回归后修复；保留原01 PDF及回执。02又由root发现末页独立两列表被并入前3列表；red07的首次断言因CJK visitor逐段切字而未正确匹配，修正测试采集为段落分组后red07b以列宽169.76<240明确暴露产品问题；green07修复分表。最终03新版本/新SHA，全页重渲重看；原01/02记录和文件均保留，没有改原MD来隐藏渲染问题。

METHOD公共渲染用例独立验证静态图、65行中文长表、长URL、HTML仅作文字、外部/file/未绑定图拒绝与0.01秒超时诊断；原图/缺图不是承德露露真实研究图。[method06.txt](method06.txt)1passed21.73秒，8页METHOD PDF也实际全页看过，图中文字/折线和长URL表格可读。实际报告没有足够有据图表，仍保留缺口，不造八图或把METHOD当真实图源。

## 边界及下一票

实际新model/source-network/auth读取均0；loopback HTTP仅用于本地文件/API验证。真实报告仍PARTIAL，CURRENT_PRICING blocked，BASELINE_RESEARCH conditional；09不新增事实核实或正式资格。A2/A10本票文件层通过，不等于所有联合A2/A6/A7/A10场景完成。10独立网页输入到下载路径、11概率只读入口和12真实联合验收仍按顺序待实施；实际盘后周期没有因本票增加。
