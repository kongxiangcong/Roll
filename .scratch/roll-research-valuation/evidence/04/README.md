# 04 可复算条件估值计算器验收

日期：2026-10-27（Asia/Shanghai）。范围仅04；开始时 HEAD `f9991ae62c1095b1d1224344c5e11f58e92195e4`、独立工作树 `D:/dsh-proj/Roll/.scratch/worktrees/rv-ticket04`、分支 `codex/rv-ticket04`。公共计算器、研究服务/API及备份边界已由用户确认，按TDD执行，没有重复询问。最终受影响回归 **72 passed，5 subtests passed，289.95秒**，见 `final-regression.txt`。

## 交付与边界

[API/使用说明](../../../../docs/research/company-valuation-api.md)记录字段、单位、日期、规模上限及离线入口。实现完整年度FCFF/WACC、EV到归母权益逐项桥、情景/可选研究权重、敏感性逐格拒绝、声明已正常化且适用的EPV诊断、固定前N年反推N+1年现金流。非金融适用性、同口径收入换算及终值依赖有明确状态。独立永续闭式提供100/.1=1000、100/.08=1250，不把这些例子硬塞有限期预测。

03快照保持不可变；估值输入/结果分别追加版本并绑定snapshot ID/hash、冻结公司身份、事实/假设、显式预测假设、所有数值路径的单位/币种/范围/期间与引用、方法版本及实际原始/适配/包装文件hash。引用缺失、混单位币种、非有限值、WACC≤g、非正终值基础、桥接重复/符号冲突拒绝。DISCLOSED必须逐值逐口径匹配冻结数值事实；DERIVED还要求已保存的派生依据；显式ASSUMED不能借标签冒充披露/推算。股份数量无币种；金额与股数尺度严格匹配。

A/H上市集合从03冻结身份读取，不能由metadata隐藏H股。每股类使用各自股数×同日价格×明确方向的同日FX，股份总数与估值股数一致。时间按Shanghai交易日对齐，并检查价格真实瞬间不晚于估值截止、估值截止不晚于快照；日期型截止定义为Shanghai当日结束。同币种FX仅允许1或省略。服务还将股数、价格、FX逐值匹配冻结数值事实、股类/汇率方向、日期与引用。缺H价/FX等只拒绝反推，保留DCF；无正终值需求返回显式状态和空收入行。没有外部声称合计市值的捷径。

所有结果强制 `review.status=unreviewed`、`usable_range=false`，调用方不能自签reviewed。EPV正常化声明也标明未审核且不是独立验证。受限现金可明确排除、NCI/非经营资产逐行保留，经济重叠、经营量价→FCFF桥、增长/再投资一致性、WACC构成和长期增长经济检查交05。当前引用存在不代表这些假设成立，不产生可用估值区间。没有实现05经营驱动构建/经济审核工作流或UI；不写账户/资格/ForecastBundle/旧预算，不读SEALED。

## 红绿与失败记录

每个切片先经公共边界观察失败再实现；后续父代理走查反馈按公开边界补验证。命令模板与选择器见`tdd.md`，完整原始输出均保留。

| 轮次 | 公共行为 | 实际结果 |
| --- | --- | --- |
| 01 | 无默认权重、完整年度路径、EV1000/归母800/每股8 | red01缺入口；green01 1 passed |
| 02 | 冻结A/H身份、同日分股类/FX、缺口局部拒绝 | red02未拒绝单价；green02计算通过但CAGR手抄期望错误；50位Decimal独立立方根校正后green02b 2 passed |
| 03 | 独立永续、早期负FCFF、边界拒绝、EPV/权重/无正终值需求 | red03缺入口；green03 3 passed |
| 04 | 不可变版本/幂等/离线重开与重算 | red04缺命令；green04 shell默认GBK读取中文源码失败，保留失败输出；明确UTF-8后green04b暴露raw返回Path；修复read_bytes后green04c 1 passed |
| 05 | Shanghai交易日、真实时点截止、同币种FX | red05未来价格误通过；green05 5 passed |
| 06 | HTTP公开入口、备份恢复、重hash但缺关系仍拒绝 | sandbox TestClient挂起且无输出，CIM只定位两条含rv04-red06命令行的Python进程并精确停止；授权相同测试在sandbox外red06b得到404；green06 1 passed |
| 07 | 假设不得重标DISCLOSED/DERIVED，混单位/币种/未知引用拒绝 | red07未拒绝标签伪装；green07 1 passed |
| 08 | 原始回归与规范归档descriptor、身份/桥接复核 | review08 12 passed+5 subtests；原样十个上游测试只改两条本地路径并规范LF |
| 09 | 敏感性坏格不丢基准/好格 | red09整计算抛错；green09 1 passed |
| 10 | 服务从真实登记的METHOD数值事实建立A/H市场基础 | review10/10b被材料口径/旧假设引用闸门正确拒绝；修正测试为独立同口径材料及当前假设引用后review10c 1 passed |

最初一次脚本从backend相对根目录执行，StopIteration发生在写文件/运行测试前；随后固定显式工作目录。`.gitattributes`起初文本规范化碰到旧CRLF段，已从HEAD原字节恢复并只追加本票规则，不制造既有文件重写。提交检查另发现新包__init__.py的CRLF末行，已只规范该新文件LF；没有删除失败或降低旧闸门。

## 独立手算与数据来源

仅METHOD/合成验收，无新网络请求或模型调用，也没有把03真实江西铜业假设当作已通过估值。手算不调用待测公式作为期望：年度100、10%、g0的五年PV显式379.0786769408448，PV终值620.9213230591552，EV1000；债务300−自由现金100+NCI50−非经营资产20=扣减230，归母770、100股时每股7.7；受限现金保持排除行。A60×10+H40×20×.9=1320，EV加桥200为1520；固定前两年100，第3年终值FCFF要求162.92，同口径10%稳态margin收入1629.2，N+1=3期CAGR .176679355108605。无正终值需求另测，不能转换成正收入要求。

`synthetic-replay-bundle.json`是实际新建隔离store导出的完整便携JSON：输入/结果、03快照/证据包、原件与源文件/许可均在其中。`synthetic-replay-receipt.txt`保存实际ID及结果hash；不是生产或真实公司估值。数据目录为原工作区独立 `.scratch/rv04-offline-store`，未改03真实store，未提交整个运行库。

## 复现与恢复

从本工作树根目录执行：

```powershell
& D:/dsh-proj/Roll/backend/.venv/Scripts/python.exe -m pytest -c backend/pyproject.toml backend/tests/company_research backend/tests/application/test_backups.py backend/tests/test_assistance.py -q --basetemp=D:/dsh-proj/Roll/.scratch/rv04-final-regression-new
$env:PYTHONPATH='backend/src'
& D:/dsh-proj/Roll/backend/.venv/Scripts/python.exe -m roll.research.company.valuation_replay --bundle .scratch/roll-research-valuation/evidence/04/synthetic-replay-bundle.json
& D:/dsh-proj/Roll/backend/.venv/Scripts/python.exe .scratch/roll-research-valuation/evidence/04/verify_bundle_damage.py
```

`standalone-replay.txt`实际结果匹配保存hash、network_calls=0、model_calls=0；只用便携JSON和匹配的本地Roll版本，无SQLite/开发者外部项目路径依赖。代码源文件hash不匹配时明确拒绝并要求安装冻结方法版本，不能悄悄用新算法；不会执行bundle提供的代码。`bundle-damage.txt`证明修改算法原文、来源原件、数值结果均被拒绝。可以用`create_synthetic_replay.py --data-directory <新空目录> --output <新JSON>`产生新METHOD记录；它通过公共服务建立新版本，不伪装成原版重放。

所有算法/许可/输入/结果经EvidenceStore登记raw路径；读取用raw校验，归档复用既有规范descriptor，Backups统一枚举与恢复。公开备份测试验证恢复后原输入/结果及重放一致；人为重hash但缺input关系的记录仍拒绝备份。

## 许可、hash与最终检查

`hash-map.json`记录冻结源与实际适配路径/hash；原脚本SHA256 `64e56fc61487e3e61568f8580d9dfaf7546e5ff7c06da6e138512c1bc02aa1d8`，适配脚本SHA256 `c6351d80e26f9cc8fdfaa9c0fdf80c7d7c93e12ba68b77f5667cd565ed82eda9`。实际输入算法记录还保存包装入口/所有源文件hash。包内保留原始代码、da-damu MIT全文/范围及Sirius MIT全文/原始通知；配套书籍不复制。新增适配主要是可选研究权重、宿主拒绝自审核、独立分股类市场基础/来源验证和受控归档版本。

最终受影响回归72 passed/5 subtests，01冻结27文件/94门PASS、compileall退出0、git diff --check通过。没有运行：新真实取数/模型、05经济审核、完整日报/研报/UI/PDF、两次实际盘后周期、整分支最终code-review；这些属于后票，不用本票合成或算术结果替代A6/A7/A8。提交前已从f9991ae快进合并集成tip dbf791d（仅coordination指针、无产品差异），无冲突。git自动维护提示unreachable loose objects，未运行prune/clean。提交hash见父代理交接；全规格仍in-progress。
