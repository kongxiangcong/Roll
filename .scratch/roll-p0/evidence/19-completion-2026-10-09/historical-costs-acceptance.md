# Ticket 19 历史执行税费切片验收

2026-10-09。工作树基线为 `codex/roll-p0-integration` / `d16ad7bef373d6330984b4529d3a99dd4b3a0b1a`，自有分支 `codex/ticket19-historical-costs`。implement-spec/TDD 的公开应用边界已由任务和规格确定。仅访问临时合成事实及其 SQLite/归档；未读取实际运行数据库、封存事实/标签、训练真实模型、修改真实账户、启动外部服务、付费或推送。

## 结果与范围

- 非 METHOD 定义新增 `historical_costs.BUY/SELL`，按计划入场日及固定退出/终结日分别解析。2008-09-19起买方0/卖方印花税1‰，2023-08-28起卖方0.5‰；跨政策日期按各边版本计算。
- 2015-08-01—2022-04-28过户费为成交额0.02‰双向，2022-04-29起0.01‰。2022原URL已回主页，本次取得官方原URL的2022-05-16捕获正文；保留 publisher DATE、capture_at、真正 received_at及原/捕获URL，不声称精确首次发布时间。
- 2013—2015旧沪市面值0.3‰的全部时期起始/最低额仍未证明，`HISTORICAL_TRANSFER_FACE_VALUE_START_AND_MINIMUM_UNPROVEN`，不按金额代替、不猜最低1元，UNSCORABLE/空损益。
- 2026既有rule范围为 CURRENT_DISPLAY_SCENARIO，绑定2022原件及现行收费页；MONTH页面不编造月初生效日，不单凭它证明历史稳定。实际券商佣金UNKNOWN，冻结研究佣金含监管/经手费，不重复收费。
- 自动数量使用入场费率，未知不补现行值。成本指纹联合绑定scenario和两边法定费用；引擎指纹覆盖执行源码、费用模块、来源清单、原件SHA。原输入/结果不可变，依赖变化时重放/复评409，原档案重放联网0。
- METHOD完全保持原合成costs路径，不成为真实法律/训练证据；原rule/PIT/status/actions/分窗门禁未放宽。

## 原件

`backend/src/roll/research/reference/historical-cost-sources.json` 记录每份URL、SHA、字节、实际收到时间及披露精度。新增4原件72,622字节，复用2026页41,658字节：5份/5唯一SHA/114,280字节，离线SHA及长度差异0，现有Git binary属性保持HTML原字节。

| 材料 | SHA256 |
| --- | --- |
| 2015联合降费原文 | `68d86fbded6d151eac74501ed285ce7c24a0746cd09a791ea927d81172266796` |
| 2008财政部单边印花税 | `4edaa053cbc7c2727e183a27f2e974aabb3534e4485522e3675f40ca7a6d8263` |
| 2023财政部39号公告 | `64783f48ef9b4a0650d058cec330268431f28b7ffad527add1a047a1b0184b36` |
| 2022中国结算原通知捕获 | `40cd7a2ddc9e1608cb4820171cb165fc716005b2b3f5aef29c2c97c994d1dc51` |
| 既有2026SSE收费页 | `021afe9404902d1a316ba06880a8a08a97afcd8b805fea938cdc05fa75b3637c` |

## TDD 与验证 delta

以下红绿结果来自执行工具回执，非另有保存的完整原stdout；最终新场景原stdout另保存为 `historical-costs-backend-final.txt`。

1. 公开API红：`KeyError: historical_costs`，1 failed/11.48s；独立entry/exit/source归档实现后1 passed/8.26s。
2. 必要Decimal计算红：`fees`四参数 TypeError；实现后1 passed/1.27s。独立10万元卖出算例：佣金30元含规费、2018过户2元、印花100元，合计132元；原METHOD假设81元保持。
3. 新API/计算4项 passed/17.37s，验证未知旧费拒绝、当前明示场景、训练资格不授予、账户不变与重启/重放。
4. 2022原件接入后，执行/透明模型/协议/家族预算/来源导入/新费用六模块组合 **47 passed/207.01s**，生产版本在最后成本指纹小修以前。
5. 成本指纹红：2022边界费用不同但指纹相同；绑定冻结schedule后新费用集合6 passed/25.45s。同最终代码追加原stdout归档验证为 **6 passed/24.76s**，见 `historical-costs-backend-final.txt`。覆盖两种税费跨版本、原件SHA、旧面值未知、当前场景费用、METHOD、依赖门禁、原结果不变。上述是分层验证，不冒充最终HEAD全后端套件。
6. 初次缓存检查发现生成source清单CRLF的尾随空白，跟进提交仅将该生成JSON规范LF；canonical-LF依赖指纹不变、官方HTML原件不改。修复后按集成基线到最终tip的 `git diff --check`验证；无需前端改变，未以测试结果认定实际研究资格。

基础设施失败单列：普通沙箱Windows ACL/进程身份不适用时按授权提升；一次自动审批超时未判动作不安全，纯计算测试可普通权限执行。长工作树路径使Parquet临时文件超过Windows路径限制；一次短basetemp父目录未建导致fixture ERROR。改用专属短路径 `D:/dsh-proj/Roll/.scratch/t19-final-hfee` 并建立父目录后通过，未降低生产门禁。临时事实全部合成，不是用户/研究原件。

## 之后仍未实现的真实训练路径

本切片**不关闭19，不解锁20**。不得把外部资料叫唯一阻塞：

- `datasets.import_acquisition` 真实源固定BLOCKED/NOT_PREREGISTERED；下一切片需宿主验证资格子记录及引用式设计标识，只引用实际已取得版本原件/解析规则，不接客户端proved/eligible开关。
- `registry.register` 合法 successor 在读标签前保存DEV/CAL设计、家族预算/暴露；先只取attempt-manifest元数据核实额度，旧失败不清空，不新开根绕重叠证券范围。
- `models.features` 非METHOD恒拒绝；后续消费版本公开可得/完成依据，同时保留今天received/available_at，不能回填历史收到时间。
- `execution.evaluate` 仍不授真实训练资格，完整权益/逐日状态待接入；只有源资格、成熟/分窗、固定执行政策都通过，宿主才能派生真实eligible。
- `models.create/forecast/replay` 仍只有METHOD；后续固定透明拟合/DEV标准化，先归档CAL时间外原模型预测，再唯一截距校准和独立model-freeze receipt。每类20/固定可靠性箱/入选40/有效块30及原预算不降。
- 模型冻结可保留封存独立性UNPROVEN及统计不足；完整政策/协议冻结归20，确认性概率/经济检验归21，前向成熟及正式资格各自后续。不得读SEALED提前满足19，不能用校准同窗拟合内分数宣称独立检验PASS。

更完整接口建议见主进程保存的 `real-training-audit.md`。本切片未改父票/spec/执行状态、窗口/预算或模型路径。
