# Ticket 19 真实重建研究验收（2026-10-10）

工程基本闭环及真实模型/CAL工件已完成。校准有效性 **未独立确认**，完整实验 **未冻结**，正式能力 **NOT_GRANTED**。只完成19，不拆子票、不实施20及以后。ADR0004是明确批准的用途变更，严格历史PIT原版不足仍作为局限保留，不能称当年实际公开预测或证明盈利。

## 实际工作树与保全

分支`codex/roll-p0-integration`，起点HEAD`66a30792fd446041a82cf268febec4dc5be59ecc`。保留起初已有修改与未跟踪工作；未提交、推送、合并或重置。实际隔离运行库 `.roll-data/reconstructed19-v1`；原宿主库只读及原件 opaque 备份，账户/资金/资格不改。见[初始清单](initial-state.json)、[保全核验](protection-verification.json)、[最终票据/保护表/指纹复核](final-scope-verification.json)。原宿主继续运行，其review_worker/session运行期变化不当作研究历史改变。

## 数据与支持

证券 **江西铜业 SSE:600362**。固定Wind主源、Sohu重叠对照、Fuyao/BaoStock旧资料仍保留；本轮明确研究包主要消费Wind RAW+Sohu对照、实际补取BaoStock RAW/交易/ST状态、SSE归档日历/规则、发行人7次现金分派及8份年度股本审计、历史印花/过户及现金税原件。Fuyao/BaoStock2023—2026旧容器不混入此固定窗口。

Wind登记1945交易日期（1937 DAILY、8停牌占位），Sohu1916重叠不相加。实际研究上下文 **2016-12-01—2023-12-29，1723日期**；基本质量 **1721通过**，2次量冲突局部隔离，37次可选金额差异保留但不全局拒绝。所选上下文缺状态0、报告停牌0；更早2016停牌保留在旧包，未因结果挑年份。逐日原值/字段与原因见[完整质量/支持报告](v4/quality-support-report.json)。

| 窗口 | 观察区间 / 前置20日上下文 | 观察日期 | 可构特征 | 成熟标签 | 实际拟合支持（负/正） |
|---|---|---:|---:|---:|---:|
| DEV |2017-01-03—2021-12-31 /2016-12-05起|1217|1192|1168|1148（626/522）|
| CAL |2022-02-08—2023-12-29 /2022-01-04起|464|464|444|444（238/206）|

按质量、已适配规则和完整年度覆盖在首版标签/候选表现计算前固定2017—2021 DEV、20交易日隔离、2022余下至2023 CAL；各标签实际结束必须在本窗。DEV48不可评分+1未成交、CAL20跨窗未定保存，不置零或标负。DEV成熟标签再与有效21行特征相交得1148。20日标签重叠，贪心不重叠持有区间DEV56/CAL22也不证明独立；同日重复/多情景不增加支持。每类20拟合门槛未降低；占用概率箱20/入选40/有效块30等仍是后续验证条件，不能据CAL444宣称444独立样本。

本轮BaoStock实际2调用、1723行，wire SHA `5ebe0b56877a2660a2290dda26bcb998fc0a05ccd6a5b1582cd0261c9ab6fc56`，实际取得`2026-10-10T08:01:53.802822+00:00`；见[原始采集收据](status-collection/receipt.json)。日线所属日期、可证实发布时间（未知保持未知）、原接收/可消费时间和历史15:05研究完成假设分列。供应商历史状态、当前版本现金/年度审计不等于严格PIT或完整日内可成交证明。年度财报正文只用于事后股本审计，从未作为历史模型特征。

RAW价格/股数/金额与依据保存，冲突不平均，停牌/缺行不压缩日历。未知券商佣金使用3bp/min5元、每边滑点5bp的冻结研究情景；印花/过户按真实生效日，现金权益按登记日资格、支付/应收、自然月年税制和HALF_UP研究精度处理。未知复杂权益或无法退出保留未定；排除可能有选择偏差，模型结果只覆盖可评分范围。

## 实际工件与接口

代码/契约范围：新增宿主有限重建准入reconstruction.py；必要改造datasets/training_preflight/design/registry、models及18已有execution/historical_costs/cash接口消费；备份只补新来源谱系引用核验。app新增准入路由，研究/models页面显示真实工件与用途/质量下载。ADR0004、GLOSSARY、数据/研究/透明模型/单机会执行契约和AT-41追踪同步；没有新增影子组合/NAV、完整实验冻结、资格/动作/通知/前向发布模块。

数据集`86cd98e9-f687-4249-a0e7-ec917f7ab3be`；协议`f977645b-200a-4c39-a6de-5e122f4e5101`；模型`8be461f3-af8b-4f0f-a707-13e41cf48249`；CAL尝试`2b4fb2f8-a995-4a37-acf4-1700ff6ab139`；预测`0276c810-1214-4ef0-9472-8c2016f66dbf`。候选PRICE_VOLUME_LOGIT_RECONSTRUCTED_V2，四特征、λ1、NEXT_OPEN、20交易日。过去有效现金的逐日因子`(close+cash)/prevclose`构成5/20日复合及20日波动，量特征为当日报告股数/前20日均股数对数；成交使用RAW。DEV独占标准化/逻辑回归，5步收敛；独立CAL截距拟合3步。先归档CAL原模型预测和审计事件，再登记唯一CAL拟合，保存校准后输出。

| 指纹 | SHA256 |
|---|---|
| model | `062d5e3a5389d918367ee84d815250bfad8e7fe9bb4adfdeb73914f1a1002f50` |
| calibrator | `85966ee09476d01af83548fa66fbca644598cd36e108c70c0d826f92dcfdbb1d` |
| features_and_inputs | `64deada41e4b3ee1056e56b0c36568f8d783896807982131a73ff10d86bac9d8` |
| code | `9c9e8b701dd4db90486654b7d44781dc317cf52fa37574214d6d2b7989e9e3db` |
| data | `0eaefd09803c54924263181b84f60fe1b028e19b9569ce4f3bd4c335def22ae0` |
| protocol | `9c383bc45c9f1627d14cf767066669392e29e69ad59f074af73c2a7a2f972458` |

冻结manifest SHA `349508062d4c17540ea203310a314f419f2434d353c7bd3c8a06e9e438a70e2e`，包含模型/CAL/训练及CAL输入/排除、窗口、特征、DEV预处理、执行/现金/历史费用/代码依赖、重叠说明。不是完整实验政策冻结。

接口：`GET /api/research/models/{model_id}`、`GET /api/research/protocols/{protocol_id}/models`、`GET /api/data/archives/{sha}`，历史获准CAL `POST /api/research/models/{model_id}/forecasts`，`GET /api/research/forecasts/{forecast_id}`、`POST /api/research/forecasts/{forecast_id}/replay`；严格PIT仍409，当前日期/非CAL预测403。源准入`POST /api/research/datasets/{id}/reconstruct`、实际支持`GET /api/research/protocols/{id}/training-preflight`。拟合后CAL预算已用完，预检会阻止再拟合，不影响已冻结模型查询。

API完整证据：[真实模型](v4/real-model.json)、[预测](v4/real-forecast.json)、[分窗/用途](v4/dataset.json)、[拟合前支持](v4/fit-admission.json)、[新进程原输入重放](v4/restart-replay.json)、[禁止外网验证](v4/offline-network-guard.json)、[两次真实HTTP启动/PID](v4/http-restart-replay.json)、[Chrome结果](browser-results.json)、[研究页面截图](research-view.png)。原SDK响应、归档、清理分片、输入和预测全部按内容SHA核验。

## 描述性结果及必要基线

DEV训练内Brier 0.239601；CAL原模型Brier 0.247424、校准后同窗拟合内 0.247132；DEV固定基础发生率CAL Brier 0.248787；CAL ROC AUC 0.560680。均为描述，无独立校准确认/优势/PASS结论。校准后阈值0.60入选20低于后续40门槛，不能签发资格。

CASH零暴露、DEV基础发生率、每次初始持有参考、固定RAW MA5/20逐机会对照已真实计算并保存在model.baseline_comparison；共用18原输入/费用SHA，规则信号不是概率、重叠机会不拼连续NAV。完整初始持有政策/连续NAV/可比风险账户属于后续票，本轮未实现。

## 原验收逐项证据

1. 单候选/基线/全尝试：models/registry真实工件；两个旧失败保留，新PRIMARY_FIT一次+CAL一次，家族五次主拟合额度剩2/CAL剩0，未重置。
2. 时间隔离/跨窗/依赖/可得性：dataset/actual-preflight/label-support及逐日索引，13项边界方法测试包含未来扰动、DEV外扰动、严格PIT拒绝、原接收不改、错误单位/冲突、保护原容器范围、空价停牌入口/退出、现金权益和税精度。
3. 不读SEALED/工件冻结：NOT_ALLOCATED元数据、所有当前协议审计无SEALED访问、新原容器保护前置拒绝；freeze manifest完整。旧v2/v3清理及预检标签保留，v4仅修作用域、指纹依赖、空价停牌/税精度，不改窗口、来源或候选，不重开预算/未接触身份。
4. ForecastBundle：实际历史CAL预测持久化事件/20日/证券/两种时钟/执行/成本/经济情景/范围/支持/限制；LLM不进入数值。
5. 研究视图：真实Chrome1 passed，显示模型与CAL状态、DEV/CAL支持、DEV与CAL描述、基线/限制和质量/冻结下载，历史保存预测/原输入重放通过。
6. 正式版本/账户隔离：保全哈希、旧记录逐行保留；capabilityNOT_GRANTED、forward_started_atNULL；不改真实账户/授权。
7. 持久化/重启/离线：新进程与两个真实HTTP PID一致、禁止外网且重放0外部调用；旧算法代码不符继续409，不以新算法冒充旧产物。

## 本轮命令与回归

所有命令本轮实际执行；Python3.13虚拟环境、FastAPI0.141.1、PyArrow25.0.1、BaoStock0.9.4、pytest9.0.2、Playwright1.58.2，前端TypeScript5.9.3/Vite7.3.1。普通沙箱遇私有SQLite/pytest目录权限及esbuildEPERM后，自动审批允许在相同隔离范围重试；没有审批拒绝或更改源权限。

- `python -B -X utf8 scripts/prepare_reconstructed19.py`：工具执行记录与[initial-state](initial-state.json)（原件只读/opaque校验；首次沙箱备份失败生成的空副本保留，获准后使用新隔离目录）。
- `scripts/collect_reconstructed19_status.py`：[实际采集](status-collection/receipt.json)。
- `scripts/prepare_reconstructed19_references.py`：[限定引用](reference-imports.json)。
- 设置`PYTHONPATH=backend/src`后 `scripts/reconstructed19_acceptance.py clean/labels/fit --final-version`：分别[clean](clean-v4-command.txt)、[labels](labels-v4-command.txt)、[fit](fit-v4-command.txt)；已拟合状态禁止再次fit，离线复现只运行verify/replay。
- `scripts/reconstructed19_offline_verify.py`：[最终断外网日志](offline-verify-command-2.txt)。首轮guard误拦Windows asyncio本机socketpair，保留[失败](offline-verify-command.txt)，仅允许本机IPC后通过；未放开任何外网。
- `scripts/reconstructed19_http_restart.py`：[实际HTTP](http-restart-command.txt)。
- `scripts/reconstructed19_invalid_inputs.py`：[原响应损坏副本409、客户端可信标志422](negative-real-integrity.json)，原件不变。
- `scripts/reconstructed19_regression.py --run-name full-frozen`：完整后端 **460 passed /0 failed**，52模块恰好一次，源码/测试/引用JSON前后指纹不变，见[manifest](full-frozen-manifest.json)、[四组日志](full-frozen-command.txt)。
- 边界13 passed见[日志](boundary-final.txt)；相关67 passed见[日志](focused-final2.txt)（其间最终停牌修正另由冻结完整回归覆盖）；初次58 passed/1旧硬编码指纹失败保留，已更新当前算法断言，旧工件不改。[初次完整扫描](baseline-full.txt)被中止，非稳定基线；[中间完整回归](full-final-manifest.json)460通过但运行中DEV可靠性描述补齐导致源码变化，不算最终稳定验收。
- `npm run build`：[最终TypeScript/Vite通过](frontend-build-final2.txt)；`node node_modules/@playwright/test/cli.js test --config=playwright.reconstructed19.config.ts`：实际Chrome1 passed，见[最终browser日志](browser-command-final.txt)；登记快照与模型工件状态澄清后复核，初轮日志/结果和截图另保留。
- `scripts/reconstructed19_protection.py`：[最终保全](protection-command-final.txt)。首次白名单遗漏本轮ADR导致核验失败，旧报告/命令保留；识别为明确授权的本轮文件后复核，未豁免非本轮用户修改。

隔离目录启动示例：设置`ROLL_ENV=test`、`ROLL_DATA_DIR=D:/dsh-proj/Roll/.roll-data/reconstructed19-v1`后在backend运行`.venv/Scripts/python.exe -m uvicorn roll.app:create_app --factory --host 127.0.0.1 --port 8049`。这是研究库，不指向真实账户。后续直接消费上述model_id/manifest/input SHA；ticket19依赖已具备，后续可另行实施。本轮至此停止，不实施后续票。
