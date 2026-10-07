# 01 验收记录

日期：2026-10-07。**01 自身切片通过，Completion: complete。** 本次使用合成脱敏账户，不是用户真实账户或投资资格证据。

环境：Windows 11 10.0.26200，隔离 Python 3.13.12 / SQLite 3.50.4，Node 25.8.1 / npm 11.11.0。锁文件已实际安装；FastAPI 0.141.1、Starlette 1.7.0、Uvicorn 0.52.4、Pydantic 2.13.5、pytest 9.0.2、httpx 0.28.1；React 19.2.4、Vite 7.3.1、TypeScript 5.9.3、Playwright 1.58.2。

## 结果与复现

| 层次 | 命令/输入 | 实际结果 | 证据 |
| --- | --- | --- | --- |
| 应用+实际进程 | 在 backend：`.venv/Scripts/python -X utf8 -m pytest -q` | 22 passed，13.60s；19 个应用案例 + 3 个真正的子进程恢复案例 | [输出](backend-test.txt)、[API 测试](../../../../backend/tests/application/test_account.py)、[恢复测试](../../../../backend/tests/recovery/test_account_process.py) |
| 实际浏览器 | 在 frontend：`ROLL_BROWSER_CHANNEL=chrome`，API 8111 / Web 5211，`npm run test:e2e` | 1 passed，9.4s；独立 headless Chrome 154.0.8037.95 连接真实服务与临时 SQLite | [输出](browser-test.txt)、[报告](browser-result.json)、[今天截图](baseline-today.png)、[权限历史](permission-history.png)、[流程测试](../../../../frontend/tests/e2e/baseline.spec.ts) |
| 构建 | 在 frontend：`npm run build` | TypeScript 和 Vite 构建成功，33 modules，1.72s | [输出](frontend-build.txt) |

[启动步骤](../../../../README.md) 与 [字段/接口契约](../../../../docs/account-contract.md) 固定精度、未知值、错误、环境和可重复启动。正式运行目录默认 `%LOCALAPPDATA%/Roll`，支持 `ROLL_DATA_DIR`，服务仅绑定 127.0.0.1；测试用临时隔离目录，01 无附件/市场归档需求。没有 worker 或市场/研究空包。

API 测试保留 1 个 Starlette TestClient/httpx 弃用提醒，浏览器另有 NO_COLOR/FORCE_COLOR 工具提醒；均不影响通过结果。测试版 Chromium 下载超时，实际验收已用本机安装的 Chrome 完成，未复用用户登录会话。

## 主责任 AT：固定输入、预期、实际

| AT | 输入与预期 | 实际 |
| --- | --- | --- |
| AT-01 | 现金100000.10、可用90000.10、冻结10000.00；SSE:600000 300股、参考成本10.12345678，可卖/原买入/历史费用/收益未知。草稿不入账，确认建立基线 | 草稿后version0，确认后version1；INITIAL_CASH、INITIAL_POSITION、PERMISSION_CONFIRMATION共3事件；金额/精度/未知/source/effective_at/recorded_at保留。浏览器完成表单→差异→确认→查询回执→今天→刷新 |
| AT-02 | 同草稿同键并发4次；后续version2再重试原命令；同键异内容 | 同一回执、只入账一次；版本推进后仍返回原version1回执；异内容409且无新事件/版本 |
| AT-04 | 两页面version0不同现金快照并发；version1权限草稿晚于另一次权限变更确认 | 一次200、一次409，返回当前版本和before/after；无覆盖/部分入账，基线仍3事件；旧权限提交也冲突，历史版本仍可查 |
| AT-44 | 实际Uvicorn进程在before_commit / after_commit调用os._exit(86)，另一次在收到成功回执后由父进程立即OS kill，再启动同SQLite | 提交前version0/events0，重试后仅一次version1；提交后与回执后version1/events3，原回执可查，同键重试仍同回执，事件逐项不变，审计仅1次。所有断言通过重启后的公开HTTP查询 |

## 额外条款与限制

- ACC-01/03/04：资金字段分列；只接受精确十进制字符串，最大金额`999999999999999999.99`原样返回；已知0和未知null分开。浮点JSON、负数、NaN、过量小数、无时区/未来日期拒绝且不建账户。基线不补造历史。
- ACC-09 / OPS-04 / DATA-INV-01：真实SQLite使用BEGIN IMMEDIATE + FULL/WAL，事件、投影、版本、审计、回执同事务；草稿/预览不改变正式投影；HTTP与未来后台复用同一Ledger.confirm。
- 1.3 / 12.1 Account：权限OPEN/NOT_OPEN/UNKNOWN保存独立范围、basis、事实/确认时点、版本；API验证草稿不生效和旧版可查；浏览器把主板已开通改成未开通后仍能查看version1已开通、科创板未开通、创业板未知。未登记范围也未知，持仓不证明开通。
- BR-03：未配置取证后端仍能建立账户；首页交易判断未启用，无HOLD/判断型WAIT/猜测卖出数量。当前切片无券商交易端点或凭据，全工具/密钥边界须13联验。
- 无效第二条持仓使整份草稿拒绝；既有基线不能用第二个BASELINE覆盖；list/dict作为权限状态返回422而非500。

TDD：先写首条公开FastAPI流程，红为尚无roll.app导入失败，最小实现后1passed。逐项验证上述精度/版本/幂等/权限；坏结构权限下一条红发现list/dict触发TypeError（2failed），仅加边界类型校验后4cases绿。浏览器定位器先失败，按实际可访问combobox校正后通过；最终全集通过。此前失败没有算作验收成功。

生产结构只有当前入口/配置、accounts、React页面/样式；无通用repository、unit-of-work、event bus或预造动作表。字段未知/精度校验均用于真实输入边界。当前schema bootstrap版本1；后续成交/资金扩展prepare并复用唯一确认事务。动作失效26/27、执行规则06、成交/CSV/资金/估值/对账各原责任票继续验收；[需求追踪](../../requirements-traceability.md)整条联验要求保持部分，01自身完成。
