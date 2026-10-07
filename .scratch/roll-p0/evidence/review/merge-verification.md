# 审阅修复独立合入验收

2026-10-08 07:16:54 Asia/Shanghai，独立 merger。合入前根 `codex/roll-p0-integration` 为 `7c9db983ad18ac7f9cd2adc7150e97a9a5147ffc`，来源 `codex/roll-p0-review-fixes` 为 `fe4d5e5c475f902d4d7d834f3557c103bca9dfaa`；双方工作树干净，根是来源祖先。`git merge --ff-only fe4d5e5c475f902d4d7d834f3557c103bca9dfaa` 无冲突快进；根和来源最终 HEAD 相同。没有推送、PR、真实模型/SDK或新公网取数，没有启动正式动作或真实前向。

## 三项发现与工程债核对

- Standards P2：14/15 共享 `market/verification_input.py` 的同一公开 Pydantic 命令，reason≤2000、fact_id≤100、field≤80、引用/事实数量原限制不变。新超长输入在保存前422；旧存量不兼容输入409/SAVED_VERIFICATION_INPUT_INCOMPATIBLE，错误有限并提示重提，旧请求/观察/知识截止不重写。正常冻结请求消费、同ID关联、三并发只消费一次、修订使当前结果失效继续通过。
- Spec P1：原 lineage 留存，共同根 family 全部版本/尝试纳入 manifest；`BEGIN IMMEDIATE` 内共同消耗5次拟合与1次校准。A→B五失败→A→C仍409，兄弟失败完整可查，遗漏 freeze 被拒；B校准中止后C校准仍409。未放宽拟合/校准预算，也未声称能检查宿主外未报告尝试。
- Spec P2：研究尝试、日线执行/复评、来源解析保存 PID/进程创建时钟/实例 nonce。活 peer 不中断原宿主工作；正常关闭只处理自身 nonce，实际死宿主恢复只产生一次中断。Windows 同步句柄检查真实进程存活，创建时间本身不当作存活证据。精确 pending METHOD 夹具只在隔离数据库模拟提交后、结果前边界：同时移除完成记录及完成事件，结束后恢复原记录；不声称真实模型中断验收。
- 默认 runner 逐文件新服务/空 SQLite，同文件顺序用例保留事实链；不新增产品 reset，任一文件退出失败传给最终退出码；默认移除模型凭据，外部/METHOD/恢复 profile 混用被拒。确切能力文本与600001成本500.01、未知 gross 金额及495.00/5.01费用分拆断言保留财务约束。只改测试轮询为冻结 timeout+10秒，生产120秒、工具/字节预算以及5秒进程等待/1秒清理上限没有放宽。
- README、17根永久保全复跑路径、三处EOF冗余空行已修。原红日志与CRLF原字节不改写；scoped Git属性随来源合入后，两跨度 diff-check 均0诊断。

## 根独立有限验证

所有运行目录只在根 ignored `backend/.roll-data/` 中新增；公共应用使用真实 SQLite/原件与明确 METHOD 提供方，不读取真实模型凭据。下列结果是独立有限复核，不与来源全套累计。

下列两条pytest命令在仓库 `backend/` 目录执行；node和Git检查在仓库根执行。

1. `.venv/Scripts/python.exe -X utf8 -m pytest -q tests/application/test_review_input_contract.py tests/application/test_research_lifecycle.py tests/application/test_independent_verification.py::test_frozen_review_request_consumes_once_and_links_original_audit_without_routine_upgrade --basetemp .roll-data/m-review-app`

   9 passed / 27.61s。覆盖三个输入上限、旧存量409、活peer尝试、活提供方来源解析、兄弟预算与校准、精确pending执行、正常14/15消费。原 stdout 分三次返回，顺序如下：

```text
..
```

```text
......
```

```text
.                                                                [100%]
9 passed in 27.61s
```

2. `.venv/Scripts/python.exe -X utf8 -m pytest -q tests/recovery/test_research_owner_process.py --basetemp .roll-data/m-review-os`

   仅一次实际自有 OS 案例：先检查记录内真实宿主PID存活，活peer保留 RUNNING、原宿主完成 FAILED；Job只终止本次已核自有宿主，≤5秒等待死亡与子进程归零，替代服务只记录一次 INTERRUPTED，peer视图一致。实际本机HTTP，外部来源/模型请求0；全部自有服务生命周期结束。

```text
.                                                                        [100%]
1 passed in 11.08s
```

3. 在全新 `m-review-g-*` SQLite，通过生产 `create_app` 公共接口检查 capabilities=UNGRANTED、HOLD请求403、测试样例404、观察summary200；没有授资格或启动前向。原 stdout：

```text
UNGRANTED/HOLD403/sample404/observation200 passed
```

4. `node --check frontend/scripts/test-e2e.mjs` 退出0/无输出。静态核对 runner 隔离与退出码传播；没有重复默认Chrome。
5. `git diff --check 7c9db983ad18ac7f9cd2adc7150e97a9a5147ffc HEAD` 与 `git diff --check 58e1d21d872556648c4fd353a56ac481e8c17951 HEAD` 均退出0/无输出。FF前根旧属性尚不识别新增CRLF捕获，初跨度检查的raw警告随来源精确属性合入消除，不规范化或重写原件。
6. `.scratch/roll-p0/execution-status.md`、`backend/uv.lock`、`backend/pyproject.toml` 在该修复跨度无diff。来源保持干净；根产品、任务与旧证据均无额外修改，只有本独立合入验收文件新增未提交，由父协调统一提交。

## 沿用来源分层与边界

[来源最终汇总](validation-summary.json)与[修复验收](fixes.md)实际冻结：完整后端343 passed / 1439.06s；默认离线Chrome11文件15 passed / 0 failed / 2明确profile skipped；构建53模块；真实OS与后置精确pending夹具各自单列。full-host-stop确认active0。这里没有重复完整后端、Chrome、构建、真实SDK或新公网材料，也不把本次9+1复核加到343冒充新全套。

原137 raw与Git捕获字节、520件/53,035,699bytes修复runtime指纹保全沿来源与根已存清单；本 merger 不重搬/移动/清理原件或写父执行状态、原审阅报告。12真实DeepSeek仍needs-info，19真实训练/校准仍partial及后继未解锁；实际来源独立性不足、22实际INCONCLUSIVE、27恢复权限NOT_CONNECTED及其他未来任务条件均保留。最终保全、状态与工作树清理由父协调负责。
