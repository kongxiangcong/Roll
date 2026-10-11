# Final 31 有限验收准备：未执行

自有树 `D:\dsh-proj\Roll\.scratch\worktrees\ticket31-final`，branch `codex/roll-p0-ticket31-final`。安装与静态记录从 `50c3fad` 保留；本次已合入 accepted root `6ba71f32246f2a4099e01daed09a212daa42afaa`，merge `f3377d8c4fe2f7d8c9bc67368f02a32ec7535193`。29 与30第九已有独立接受。本轮等待四项 P2 修复独立接受；不合入随后 docs-only tip。下面全是准备，不能作为五入口、性能、进程或资格通过。

## 开门与执行边界

协调者给出最终修复独立接受 OID 后，合入最终 accepted root，核 own clean index 与祖先、安装锁是否变化。只在自己的物理 venv/node_modules 执行，显式 PYTHONPATH 为 own backend/src/support。当前安装 receipts 与公共组件/生产 Agent 静态 records 在 `../install/`；对最终版本只做有限源码与明确公共元数据差分。不得重新 whole install 或 fullsuite。

`run-bounded.ps1` 默认 preparation-only。执行需要 `-Execute -AcceptedFixOID <40hex>`，并验证该 OID 已合入。Reviews 只运行 Ticket 15 的两个精确 case；Benchmark 只调用实际既有 model/calibrator 参数与既有完整政策的 21 次局部数值/API评估。原25基准不改，三个明确 JSON 原件只字节校验后解析，不打开 donor SQLite。新 runtime 与结果均为 own GUID namespace。结果保留后才判 P95 阈值；失败保留且不自动重跑择快。

`http-p95.py` 默认不发 HTTP；执行需要 root acceptance OID 和当前 owner-server receipt。receipt 必须来自当轮三进程启动记录，含 source root/OID、fresh owned runtime、原 SQLite 连接为0、test 环境、API loopback地址、实际 PID+CreationDate。调用前执行者重新以精确 CIM PID/CreationDate 比对本轮 owner；仅 receipt 字符串不算进程证据。主页固定100+10warmup，确认固定100+10warmup，均 nearest-rank P95≤2000ms；数值评估固定21样本 P95≤30秒。确认 profile 先建立30持仓合成基线和足够现金，不能用真实账户。外部任务等待证据仍单列，不把三个测量互相替代。

## 五入口有限路径

新 baseline profile 与 fresh byte-verified donor-copy report profile 分开，浏览器只访问同版本 own React/API。五入口路径结合有限 UI flow 与真实 HTTP回执，不以旧默认11文件代替最终路径。P2修复接受后按真实当前字段写最后 UI断言；本准备不固化旧“交易判断未启用”常量。

| 入口 | 有限行为与证据 |
|---|---|
| 今天 | 当前 NOT_GRANTED/INCOMPLETE/G4G5 failure/G7 INCONCLUSIVE 字面状态；单独 METHOD active/ungranted/suspended/recovery/risk-only scope显示与动作权限对应，不升级实际资格。记录缺数据时点与按需/盘后观察。 |
| 持仓与关注 | 合成30股+5指数全部资产保留，范围外事实与未知可卖保持；收益范围仍一只冻结证券，指数仅背景。 |
| 同步账户 | baseline→CSV草稿/差异/整批确认→回执；无变化声明；实际300对应建议500、外部未决、未知费用和补费均真实入账；旧动作失效与账户事务一致。保存字面 event/版本/幂等回执。 |
| 历史记录 | `report_method_app.copy_donor` 按已接受193文件清单先复制至fresh ownruntime、逐项 SHA/length核验且源前后不变，再 factory连接副本；四 namespace、偏差三分、关联/时点/不可比、导出与旧深链。补录不改旧 shadow，不启用formal权限/研究通知。 |
| 设置 | CODEX-only/资金/暂停及有限恢复；撤权在重启/旧ACTIVE备份后保持、RECOVERY_LOCK存在。站内配置可验，用户未配置真实外部渠道不发消息。 |

29报告历史 donor 指针只作输入，不能原地开库：根 `.roll-data/implementation-evidence/20/independent-api-runtime-fixed`；193文件清单 `.scratch/roll-p0/evidence/continuation-2026-10-11/independent20-profile-manifest.json`，manifest SHA `528688f65d19849fffeead4aa8082adc9374dac471eff71ff504c483460c62e7`。既有报告 Playwright config 使用 root venv，**不得原样运行**；最终使用 own venv、自己的物理 node/cache、新ports与新profile，避免root安装/cache。

## 三进程与保全

参考 `docs/local-worker-delivery.md` 与 `frontend/scripts/worker-delivery-acceptance.mjs`，本轮尚未运行。新 owned empty runtime 用明确 API角色 uvicorn factory、`python -m roll.worker` 独立WORKER、own Vite三进程；API health成功后再启动worker。测试不启动 provider/源采集/fit/forecast/SEALED或真实外发；report复制profile若有持久任务，先静态确认无待执行外部工作，不能在未核副本上启动worker。

Start-Process Hidden 保存每个launcher与实际host PID、CreationDate、command/source/runtime；worker真实owner采用 reviews health 的 PID/nonce+新CIM验证。重复worker应拒绝唯一租约；关闭浏览器后API和worker仍活，正常停止与强制停止分开记录。终止只匹配本轮确切 owner，不按所有Python/Node名称kill。完整own运行目录union须在停止、确认无存活owner后保存，并逐项length/SHA对账；保留失败、logs和archives。精确private metadata排除依据本轮源定义路径列举，绝不扫描/打开/hash/copy凭据，也不把auth/.env通配成免检。未知private文件保留source并交协调者，不删除。

## 当前限制

脚本只经过静态解析，不执行 case、benchmark、HTTP或应用；没有新model、forecast或数据库连接。源码准备时sandbox own venv无法解析uv Python安装位置，随后只以escalation运行标准库文件生成/AST检查；保留该环境诊断。清理仅使用 outside cleanup计划，当前不执行、不扫runtime、不停任何进程。root的README/status/trace/manual239/plan不改，239条不可按COUNT或历史统计自动PASS。
