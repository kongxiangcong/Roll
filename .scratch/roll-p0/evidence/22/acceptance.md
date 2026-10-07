# 22 独立风险政策工程验收

从integration7505019开始，源1b50406后合最新7260c8c得5b77e2e；保留14/15/09/11/12路径，父execution-status未编辑。一个具体确定性政策，既有Python3.13.12/uv锁定包，无新依赖、额外模型或公网取数。FastAPI/真实SQLite/隔离档案及安装Chrome公开验收。

**工程complete，实际资格INCONCLUSIVE。** 当前真实ACCOUNT0、没有人类资金授权，原档案不是财富/授权起点；真实检查明确FUNDING_AUTHORIZATION_MISSING、不产生数量/正式动作。METHOD资金与凭证只在隔离账户里测试，不把19实际支持不足变成真实模型或完整冻结；20仍未解锁，收益G3/G4/G7和24/25正向资格/动作链未执行。

## 证据与预期/实际

| 边界 | 预期与实际 | 原证据 |
| --- | --- | --- |
| AT70 独立注册 | 17协议内独立政策及RISK_POLICY_VALIDATION尝试，冻结10明确single/total较小交集、06具体身份/规则、范围、算法、恢复、代码依赖SHA；不填收益资格缺口 | [公开API测试](../../../../backend/tests/application/test_risk_policy.py)、[契约](../../../../docs/independent-risk-policy-contract.md) |
| ACC14 cash/fee-only | METHOD1050股、已知新鲜可卖1050、原价30、单票20000→最小400减量/650剩余；费用草稿使整体UPDATE_PENDING，数量REDUCTION仍allowed；账户不变 | [METHOD实际HTTP](http-method.json)、[17项相关](backend-final.txt)、[截图](22-method-quantity.png) |
| 授权边界 | 当前缩小单票10000→800/250，历史政策授权不改；撤回FAIL/不计算。不是由损失预算推仓位上限 | [HTTP](http-method.json)、[公开案例](../../../../backend/tests/application/test_risk_policy.py) |
| 不可计算 | 可卖未知、未决成交数量、身份/规则未知、停牌均受限；正常无超额但损失未知仍trigger=null，不作HOLD/WAIT/全卖。150可卖只能100、50股整余可卖50 | [17项相关](backend-final.txt)、[METHOD当前受限HTTP](http-method.json) |
| 09严格损失 | 同版本/截止的真实09公共估值缺基线仍RESTRICTED，loss=null、不作0或清仓；独立已知超额分支不依赖现金/费用补全 | [公开应用用例11](../../../../backend/tests/application/test_risk_policy.py) |
| 压力 | 650股遇33跳空剩21450仍超20000；27跌停0成交剩1050/28350；停牌/延迟风险未释放、未来价未知，50%压力按100股步长 | [HTTP](http-method.json)、[页面](22-method-quantity.png) |
| 实际不足 | 无授权工程/实际均INCONCLUSIVE，规则/数量/压力/数据不足；原输入ONLINE重放PASS、0网络，但不授真实资格 | [真实HTTP](http-real.json)、[真实页面](22-real-gap.png) |
| 原件与持久化 | raw先归档SHA，再SQLite引用；原价QUOTE原件重放校验，重启GET原结果完全一致；attachment/nosniff/SHA通过 | [真实过程](http-real-process.txt)、[METHOD过程](http-method-process.txt) |
| 无正式/账户副作用 | 公共formal EXIT服务端403、capabilities UNGRANTED；风险检查/重放不写真实账户或意向，页面仍5主入口 | [实际Chrome](chrome-real.txt)、[METHOD Chrome](chrome-method.txt) |

实际HTTP时间UTC2026-10-07 22:06:57—22:07:12（上海10/08 06:06:57—06:07:12）；METHOD22:07:31—22:07:41。METHOD源时点为9/30 15:00已完成收盘，账户/授权effective_at模拟9/30，实际取得及检查知识时点为10/08。并未伪造9/30用户授权或历史可得。当前实际没有资金授权，不需要人类选金额来完成不足路径工程验收。

## 检查与重现

最终17项相关public FastAPI用例 **17passed/47.29s**：11本票、3资金、2ACC14、1协议预算。早期404/KeyError/撤回结果红与逐slice绿原stdout保留，[TDD记录](tdd-transcript.md)说明输入和结果。最终build **52modules/2.39s**；真实Chrome1passed/9.9s、METHOD Chrome1passed/10.0s。原安装Chrome和真实HTTP/SQLite并不证明人类实际资金/新行情或资格PASS。

根默认全文件Chrome已有05共享fixture红、18相关组合已记录12固定SDK方法20秒轮询红；本轮没有重复全套、真实SDK或弱化生产预算，也不将这些债改写全绿。实际Chrome原JSON reporter位于test-results被下一次隔离运行自动清理，原list stdout与截图保持；METHOD reporter保留[原JSON](chrome-method-results.json)。

从根运行`backend/.venv/Scripts/python.exe -X utf8 scripts/risk_policy_acceptance.py --source D:/dsh-proj/Roll/backend/.roll-data/implementation-evidence/19/acceptance-19-final --data-root <全新隔离目录> --port 8042`；METHOD加`--method`，父进程PYTHONPATH指向backend/tests/application。该工厂仅测试httpx固定响应、不是生产真值端点。原目录存在时拒覆盖。

从frontend设`ROLL_RISK_LIVE=1`、`ROLL_BROWSER_CHANNEL=chrome`、`ROLL_RISK_DATA=<已保存实际目录>`运行`npx playwright test -c playwright.risk-policies.config.ts`；METHOD目录加`ROLL_RISK_METHOD=1`。API8042/web5202。浏览器只查询原检查、原输入重放和拒正式动作，不重置账户。

## 原件长期保全

自身已停止API/Chrome进程、8042/5202无监听后登记[清单](runtime-preservation.json)：**269文件/18,186,701 bytes**，每项source绝对路径、relative、原SHA/bytes；未复制实际凭据、没有合成认证seed文件。清单根 `D:/dsh-proj/Roll/.scratch/worktrees/22-independent-risk-policy/backend/.roll-data`，真实与METHOD子目录分别`acceptance-22-real-final`、`acceptance-22-method-final`。测试运行目录也同列，不能用方法材料替真实证据。

只读来源`D:/dsh-proj/Roll/backend/.roll-data/implementation-evidence/19/acceptance-19-final`，238 raw/Parquet逐字节opaque复制并SHA核对、SQLite只读逻辑backup。未解析封存输入或策略结果，只消费QUOTE与当前账户/授权；复制不算确认性PASS查看。根19原件未改/未移动/清理；自身原档案和SQLite保留供父精确复制长期保全，不能只留下JSON指纹。根永久映射由merger登记，本票不清理worktree。

政策注册指纹是材料JSON SHA，依赖代码指纹规范LF；原下载/来源SHA保持原bytes。捕获txt通过scoped `.gitattributes -text`保存，Git暂存blob与文件原字节核对见[source-byte-check.json](source-byte-check.json)。
