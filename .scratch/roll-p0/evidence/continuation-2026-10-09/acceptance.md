# Ticket 19 公共来源、历史日历与剩余研究门禁

本轮按用户要求主动收集、整理江西铜业资料，公共收集及实际宿主取数均不调用 Fuyao/BaoStock。工程接入与数据覆盖继续推进；Ticket 19 仍为 `partial / needs-info`，没有真实训练、校准或完整模型冻结产物。20 的依赖未满足，后续票未解锁。

## 真实资料及边界

- 搜狐 RAW 日线：2013-01-04—2025-12-31 共 3,126 条；保留原始响应、实际取得时点、SHA、数量单位依据和规范化 Parquet。手数按已核对 SSE 主板股票口径转换为股，万元转换为元；取整成交额容差有明确限度。
- 巨潮官方公告：完整索引报告、返回及唯一公告 ID 均为 1,005 条，34 页；61 份官方 PDF 已保存，实际读取并结构化整理 14 次现金分派，分别保留每股现金和差异化分派除息参考现金。2016-02-16—2016-02-25 停牌区间有实施原件，其余证券状态没有凭空补为正常。
- 官方交易规则原件及过渡说明已收集；SSE 2013—2025 年 13 份年度日历通知与 3 份修订已归档并接入日历查询，包含 2015 特殊休市、2019 五一修订、2020 春节延期及 2018 跨年闭市。历史交易阶段仍为 `UNKNOWN`，SZSE 旧年份保持未知；日历接入不表示历史规则和成熟标签已完整适配。
- [资料清单](public-data-inventory.json)记录 114 个原件引用、111 个唯一 SHA，原件逐 SHA/长度核对差异为 0；搜狐单位原件另见[保全记录](sohu-unit-preservation.json)。失败和中间版本原件保留，不以最终成功覆盖先前失败记录。
- [公司行为整理](corporate-action-reconstruction.json)、[研究报告](public-data-research.md)、[搜狐契约](../../../../docs/sohu-evidence-contract.md)、[适配器验收](../19/public-adapter-acceptance.md)、[日历验收](../19/calendar/acceptance.md)列出来源、字段和覆盖限制。分派公告不是税后到账或账户事实，完整公司行为及证券状态覆盖仍未获证明。

## 实际宿主验证

[首次成功实际取数](public-host-live-v2.json)保存 FastAPI、真实 SQLite、新建研究目录中的3,126条RAW日线、归档下载SHA、研究输入及0联网重放；空账户保持不变，能力仍为 `UNGRANTED`。当时仅靠健康接口判断重启，尚未证明服务进程的实际归属及停止，因此其重启结论不作为最终验收依据。当前历史来源导入保持 `BLOCKED`，开发分片409、封存分片403；403拒绝检查没有返回或读取封存数据。

首次失败运行 [public-host-live.json](public-host-live.json)保留：管理工作树的 cwd 不足以改变根虚拟环境的可编辑安装来源，旧代码拒绝 SOHU 请求。后续通过显式 `PYTHONPATH` 指向源工作树完成验证；未放宽请求或研究门禁。

[Windows启动器实测](windows-launcher-probe.json)证明Popen启动器PID与实际Python服务PID不同。修正后采用子进程启动原件、唯一标记、目录和实际PID核对，验收包装器单独实现正常停止、等待退出和监听关闭；该检查与端口占用拒绝、实际取数、重启重放分别留证，没有改变生产接口。

**最终集成实际取数通过**：[v3结果](public-host-live-v3.json)、[原始输出](public-host-live-v3.txt)。启动器7712/15496对应实际服务10520/42084；两次身份原件与HTTP一致，标记和实际PID不同，两次正常停止且监听关闭。真实3,126条RAW日线、原件下载SHA、SQLite持久化、重启后的研究输入相同及0联网重放通过，错误计数为空、成交额未知行0。历史日历缺口从研究输入限制中消除；其余PIT、完整权益/状态/规则、窗口及封存独立性门禁仍BLOCKED。账户不变，正式能力UNGRANTED，无标签计算、模型拟合或封存读取。

**Chrome实际归档流程通过**：[结果](browser-results.json)、[实际边界](browser-actual.json)、[输出](browser-run.txt)，1项/18.5秒，无flaky：SOHU可选、2019五一修订、旧交易阶段UNKNOWN、归档0联网重放、研究窗口和资格限制可见；账户仍不变。截图：[日历](browser-calendar.png)、[来源](browser-sohu.png)、[研究](browser-research.png)。首次错误为`getByLabel`精确文本未匹配嵌套select标签，页面快照确认控件及SOHU选项存在；仅验收脚本改为可访问combobox角色，产品未修改，原[失败输出](browser-first-run.txt)、[结果](browser-first-results.json)、[快照](browser-first-error-context.md)保留。

## 剩余明确缺口

1. 当前取得的历史行情无法证明当时可得版本，原件取得时点如实为本轮时间；完整停牌/ST、权益及历史规则支持不足。
2. 新来源的窗口未预登记，训练分片没有合法授权；原失败尝试、谱系预算、输入暴露和旧封存独立性均保留。没有重置旧实验或查看封存结果。
3. 真实开发、独立时间外校准及必要基线比较没有合格产物；原每类 20、概率分箱、入选支持和独立依赖块条件未降低。新增长序列不自动证明校准支持充分。
4. 真实特征、模型、校准器和完整研究冻结链尚未成立。现有真实导入及特征路径仍拒绝未获证明的输入；本轮没有用 METHOD 或人工资格标志替代该缺口。

这些是现有可取得材料和实现的实际限制，不是等待用户提供个人财务、凭据或选择统计参数。没有真实前向起点或三自然月倒计时；整个 P0 规格未完成。

## 审阅与最终集成验证

本轮固定起点 `01563d6`。双轴报告分别见[Standards](review-standards.md)与[Spec](review-spec.md)，两个P2分别涉及验收进程身份和零成交量/正成交额冲突；原报告保留，修复和最终集成结果分别留证。

- Standards：原1项P2已修复；[最终Windows复核](review-standards-windows-followup.md)明确纠正早期启动器PID假设，剩余0项。生命周期专项[成功](lifecycle-v3-final.json)和[受控失败](lifecycle-startup-failure.json)与真实取数v3分列。
- Spec：原1项P2已修复；[独立复核](review-spec-followup.md)确认零量正额质量冲突及模型输入拒绝，剩余0项。已知Ticket19真实研究缺口仍partial；审阅问题关闭不代表该票完成。
- 旧代码完整基线：[391通过/1失败](backend-baseline-normal.txt)，1633.24秒。唯一失败为固定接收日期跨日后默认截止进入未来，已先聚焦复现、固定测试cutoff后BaoStock模块12项通过；生产时点门禁未修改，未调用真实BaoStock。
- 沙箱基线因测试私有目录ACL错误中止，[原输出](backend-baseline.txt)不是功能基线。前端沙箱构建因esbuild子进程EPERM失败[留证](frontend-build.txt)，正常Windows[TypeScript/Vite构建](frontend-build-normal.txt)通过54模块；没有修改系统权限或构建规则。
- 最终完整后端：**406通过、0失败**，45个模块，每个模块恰好一次，四个隔离进程分别102/101/102/101项，全部退出码0。代码、测试、参考JSON/HTML和依赖前后指纹相同；见[完整清单](backend-final-manifest.json)、[收集](backend-final-collection.txt)、[执行](run-backend-final.py)。这是完整集合的一次分组执行，不把此前专项或实际网络结果加总进406项，也不将其作为真实训练/校准证据。

## 本地集成与保全

集成分支`codex/roll-p0-integration`，生产集成与辅助验收最终合入`168aa8f`；仅本地提交，未推送。本轮两个托管实施工作树均已归档，分支、提交和可恢复快照保留，目前仅集成根工作树。清理前后搜狐单位原件及根Python/Playwright依赖逐SHA/长度相同；[清理前](cleanup-before.json)、[清理后](cleanup-after.json)记录源目录已不存在与0差异。真实公共资料及宿主运行原件保留在根忽略目录，没有清理用户资料、凭据或旧研究证据。
