# Ticket31 独立工程切片验收

日期：2026-10-11。结论：**PASS within partial engineering scope**；31 Completion 保持 `partial`。冻结来源 `a19ce9b592aa0ae207255c40691cb6d76f1e6554`，managed `agent/ticket31-delivery` 已含集成 `2db3bd1`，tracked/index 干净。合并前根为 `719423ec81d24e8ee616644512fb911ef777b0c7`。依据本票 issue、`31-worker-delivery.md`、`docs/local-worker-delivery.md` 与三份生产源码，只补必要边界，不重跑全部历史测试。

## 独立新增结果

单轮两个新用例 **2 passed / 14.65s，实际 exit 0**；见 `execution.json`，并非历史测试数相加。导入冻结 managed 源码，用根 Python 3.13 环境，运行数据全在新建根 `.roll-data/implementation-evidence/ticket31-independent/pytest-01`；不写 managed 源码。

- 明确 API 参数覆盖继承 WORKER 环境；公开任务/recover 均持久 QUEUED、coverage sessions=[]，API 不取得租约或开启计划备份线程。一次 MockTransport 固定 METHOD 原件经公开盘后入口生成唯一 job/batch；关闭后重新建 API，重复检查保持同 job/batch、账户不变，没有第二供应读取，`actual_forward_start=false`。线程检查只是辅助实现观察，公开持久结果见 `source-role-results.json`。
- 真正独立隐藏 Windows worker 进程，公共 health 报实际 owner PID 39340，launcher PID 38864，与验收/API 进程不同。正常退出 API 的 TestClient 生命周期后重开 API，worker owner 原样保留，旧已发布任务逐值相同；再提交任务由同 worker 处理，两个任务均同 ID/attempt=1，无 forecast/forward sample。仅该独立控制台 Ctrl+Break 正常停止，进程实际 exit0，coverage 保留 `NORMAL_CLOSE_NO_ALWAYS_ON_REQUIREMENT`。见 `OS-worker-results.json`。这是实际 OS worker 与 API 生命周期组合；本例 API 使用 TestClient，不冒称独立 HTTP API OS 进程。
- 两个新真实 SQLite 的 research models/forecasts/attempts/forward plans/samples 均为0；实际账户、资金、模型训练/拟合、资格 grant、SEALED、通知、provider、外部 HTTP 全未执行。一次行情供应读取为本机 MockTransport METHOD，不等于真实来源或前向启动。

## 既有证据与保护

实施者实际独立安装/Chrome/真实 HTTP API+worker+UI、死亡重启/重复租约/恢复锁有原收据；本轮以限定旧证据接受，不把历史 4/25/6 与新增两例合并成一次绿色套件。现存最终组合 6 PASS/47.63s；干净安装来自独立 managed venv 与 npm ci，并非复用依赖的本轮测试。实施者先前中断扩测已有 METHOD 合成训练，之后精确两恢复原件例子另获授权，历史记录未删除；本轮 METHOD 训练为0。

已只读检查现存 Chrome `run-KSkC0e/receipt.json` 全检查 PASS 和 `receipt.png`：同步账户、确认回执与查询成功可读，浏览器关闭后服务存活见原 receipt。本轮没有再运行 Chrome，也不把小账户安装切片宣称完整容量/P95。

`preflight-results.json` / `postflight-results.json` 逐文件复核旧4057及组合237源与根保存件，共4294文件；manifest原字节、各 source/root SHA-256 和长度全0差异。保存档案未开启任何 SQLite 连接，即使 mode=ro 也未使用。只在新独立运行目录打开自有 SQLite。

12 模型保护源码加 shadow/statistics/validation 共15份前后及根/managed完全相同。三份本票生产源码和两锁文件前后相同。原19数据库仅文件 checksum：165814272 bytes，SHA-256 `ec46257c4420f69c245791778c49079355700615cc3ed7b94d8027bd4dcf66c4`；从未开启原19或实际研究副本。进程关闭结果见 `process-closeout.json`，精确 launcher/owner 均已退出，不处理其他进程。`closeout-results.json` 保存限定结果。

## 仍需主责任票完成

31只接受独立 worker/生产 API 角色与本机安装、恢复契约的工程切片。25—29 的完整出口行为、90 AT、125编号P0、14 BR、10数据不变量逐条实际证据、全部五入口/30股+5指数容量与真实 P95 仍待责任票收口；库存计数不能替代行为 PASS。28实际外部配置/送达待配，30内部完整 producer 与真实来源/前向资格仍不完整，32—34真实时间/验证/启用不关闭。当前 CODEX-only，无 DeepSeek 操作。

没有发现本次稳定切片的合并阻塞。安全集成建议：短 Git 独占窗内本地 no-ff 合入上述冻结 OID，再只提交本目录 receipts；保持31 `partial`，不改 root status/trace/README，不清理 managed worktree/branch，不推送。
