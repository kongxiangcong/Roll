# Final31 有限工程验收

本轮行为源码 `d4864a4e29ddcb80462e44250569d652e8cc03cf`，包含 accepted root `076e67d53e4e550d4027b4f76909fb693c952957` 的四项最终修复。随后只合入 root docs `6bbc3f94c05fd62e0afb9d0c4be2f1f502fffbf2`，own merge `6cad5e121d8de4b34847195a4ef2a52d5902d0c9`；产品源码相同，未重复已通过行为或数值基准。root-owned状态/README/trace/manual239不改。仅下述有限工程路径通过，不自动将239条或研究资格升级为PASS。

## 当前结果

五入口真实 Chrome/HTTP/SQLite flow PASS，`runs/live-20261011-223216/five-entry/five-entry.json`：UI建立30持仓/未知可卖、差异与持久回执；全部30资产保留及5背景指数；实际300股无建议成交、10元暂估费用再补实际5元；CSV利息25.01整批入账/查询；无未记录变化声明；历史成交及settings维护默认折叠、展开、按原因暂停/恢复。零pageerror/HTTP500。截图人工查看今天与settings：未授资格标题保留、结构可读；settings截图是展开后的控件状态，默认关闭由浏览器断言证明。该flow没有伪造500股正式建议，也不声称当前未授实际账户出现GRANTED；最终修复独立接受及既有26/27记录另属其原范围。

复制报告 Chrome单case PASS，4.9s（runner7.3s），`runs/live-20261011-223216/report-browser/`。193个固定METHOD donor文件先逐项SHA/length复制与源前后核验，再连接新的 `report-runtime`，原/保全SQLite连接为0。四namespace、实际估值103600.10/NOT_COMPARABLE、readonly JSON导出、旧research链接、原shadow不变及formal403通过。报价来自固定 MockTransport；这不是新的真实源取得或市场/PIT验证，没有report worker、新actual ReviewRecord、模型拟合或forecast创建。

| P95 | 当前独立测量 | 阈值 | 原始证据 |
|---|---|---|---|
| 缓存首页HTTP+JSON | 221.6225ms，100样本+10warmup | ≤2000ms | `runs/live-20261011-223216/home-p95.json` |
| 单笔确认HTTP+JSON | 1079.4350ms，100+10，30持仓，max1453.8808ms | ≤2000ms | 同目录`confirmation-p95.json` |
| 30股+5指数局部数值+public评估 | 0.5617275s，21样本 | ≤30s | `runs/4c8ac26b2cee4753822177d3176f8971/numeric-p95.json` |

数值每样本真实重算既有feature/scaler/weights及intercept校准，三个明确许可model/calibrator/config原件只校验/解析JSON。METHOD账户/数据/资格，1股冻结scope、29股明确拒绝、5指数背景。相同输入返回同一evaluation_id（distinct=1），不称21个独立研究或21次新动作；无fit/forecast持久化/外部获取，实际资格与G1—G7不改变。三测量分别保留设备/时点/样本，缓存、数值与外部取得未混为一项。

Ticket15只此两case：日线完成/旧quote时点1PASS（同段总体1pass/1fail24.83s）；重试case最终单独1PASS11.44s，`runs/retry-contract-sourcebound/public-retry-receipt.json`。三attempt、六retrievalruns，每attempt同时OBSERVATION/BACKGROUND且工具合计≤8，partial facts与ConnectTimeout保留、相同identity幂等、forecast为空。当前持久审计dup CHECKED/merged0，最终站内RUN_SUMMARY1（source snapshot_id与task_id分别绑定）、transmission0、deliveryUNKNOWN/CHANNEL_DISABLED。它是受控源超时，不是真实网络/外发；日线已PASS后未重跑。

当前own物理安装build PASS：66modules/2.22s，`final-build.log`。四manifest/锁字节与干净安装receipt一致，无重装/audit fix。`current-agent-component-delta.json`对七个公共源：五个Agent launcher/evidence/review-runtime/settings保持原字节，仅saved-material enumerator与受控capability服务变化；动态工具仍取证3项/审阅2项。此前固定CNE410源/382installed/Apache2 NOTICE/TDX MIT、DSA design-only MIT与11/23真实receipt保持分别归属，本轮不重复CNE读取/联网/新实际Agent调用，不读取/hash/copy认证内容。npm2个历史诊断保留，不推断当前可利用性。

## 进程与保全

`live-receipt.json` PASS：own API、独立WORKER、own Vite三进程；API启动不取租约，重复worker非零且ALREADY_RUNNING；关闭浏览器后三服务与同一实际workerowner存活。worker与恢复后worker均CTRL_BREAK退出0、coverage NORMAL_CLOSE；API完整lifespan teardown后进程码3，Vite的CTRL_BREAK码3221225786，均明确保留，**不称所有进程exit0**。没有taskkill fallback、未停其他进程。实际host/launcher argv、CIM PID/CreationDate、worker nonce、stop后不存在记录保留。备份在全部宿主停止后应用，API及worker重启均RECOVERY_LOCK/formal403，旧动作/通知不得恢复；未授fixture不证明真实资格恢复或positive LOSS恢复。

完整own runtime union已保存根 `.roll-data/implementation-evidence/31-final-r01`，645文件/291181324字节；manifest178259B SHA `ca3331799dbf8ffcf298e45d0c2fe076ac94a939361a000cf378dfe91252ba7d`，两端0差异、39精确CIM检查、private metadata exclusions0（没有生成认证文件），reparse0。覆盖全部own `.roll-data`、四个短pytest runtime及public browseroutputs，包含失败profile；不扫生产/SEALED、不读依赖cache。`runtime-union-manifest.json`与`runtime-preservation-summary.json`记录来源与目标；短pytest目录仍留自有树为已保全的untracked runtime，未删除或藏入Git。原19仅checksum165814272B/SHAec46257c…c4；15保护源和3许可JSON、当前application sources前后完全相同，`guard-before.json`/`guard-final.json`。

## 保留失败与限制

本轮失败都保留：834… 两setup ERROR3.01s（缺basetemp父级）；1f40… 两FAIL3.14s（Windows路径长度）；329…1pass/1fail24.83s（旧NOT_CONNECTED断言）；retry-current1FAIL12.30s（误将最终站内business数写0）；retry-literal1FAIL11.94s（错把snapshot source ID当task ID）。修正仅own harness与一个新通知接线后的调用方测试断言；产品/保护源未改。live222705在保存回执后重开同页CSV错误，live223009在嵌套summary strict locator错误；两profile均停止保全，223216完整flow通过后未重跑。

所有工程fixture `METHOD_ENGINEERING/system_usable=false`；未新fit/forecast、SEALED、真实provider/源采集/渠道外发、正式grant/资格或actual ReviewRecord。自然前向、月度终点、真实采样/资金/政策输入与用户配置后外发仍分别按原票缺口，不以本验收闭合。完成状态与manual239归root裁定；本票owner提供有限事实与可复核材料。
