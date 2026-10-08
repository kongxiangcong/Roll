# BaoStock 认证路径核查

日期：2026-10-09，Asia/Shanghai。仅查第一方文档与发行包源码；未读取 `.env`、API key 或个人认证，没有执行 SDK、调用 provider login 或发送行情请求。

## 已核实的官方事实

- [官网平台介绍](https://www.baostock.com/mainContent?file=home.md) 声明平台免费、无需注册，并在 0.9.4 更新说明中列出 API key 对 `vip-api.baostock.com` 节点的支持。这不是“所有请求都必须使用 API key”。
- [官方 PyPI 0.9.4](https://pypi.org/project/baostock/0.9.4/) 发行 wheel SHA-256 为 `0bf71c6069ab5890ff3596632f9c3f8f1fbc6bfcac582c2f9d6a5c11ab2cfaf8`。第一方源码 `login/loginout.py` 的默认 `login()` 使用匿名身份，未设置 context API key 时 options 为 `0`；若 context 已有非 `0` key，登录会校验格式并发送该 key。因此仅省略 `set_API_key` 不一定清除同进程已有 key，PUBLIC 模式应保证专用新进程/无残留 key context。
- 同包 `common/contants.py` 定义公共主机 `public-api.baostock.com`、VIP 主机 `vip-api.baostock.com`，端口均为 10030；`util/socketutil.py` 根据传入 key 是否以 `bs-` 起始选择 VIP 或公共主机，没有源码中的失败自动回退。PUBLIC 是明确选择公共路线，不是尝试绕过 VIP 鉴权。
- 源码中格式校验失败常量为 `10001012`。格式校验通过、登录成功或 TCP 可达，都不能独自证明该 key 对具体查询有有效服务权限。

## 10001015 的证据边界

父级提供的运行事实是：来源 Agent 对官方 0.9.4 VIP 路线的一次江西铜业查询得到 `10001015`。本轮没有读取或重跑其凭据/运行响应；该记录应继续由实际调用证据引用，不能以本文件代替原始错误响应。

本轮读取官网 `home.md`、`pythonAPI.md`，检查官方 wheel 内全部 Python 源文件，并作 `site:baostock.com` 定向搜索，**未找到 `10001015` 的官方定义或处理说明**。这只能说明本次核查的公开材料没有定义，不能证明供应商从未发布说明。不能推定为 key 过期、充值不足、格式错误、账户封禁或永久不可用；若实际错误消息明确写了认证失败，可以记录该原消息，但仍不扩展成未被证明的根因。

## 本次采用的运行决定

父级已明确选择 PUBLIC 模式继续授权范围内采集。该模式不读取/发送 API key、不执行 VIP 失败后的静默切换；调用仍遵守现有超时、调用总预算、取消与零自动重试规则。公共路线上若失败，应保留实际错误与覆盖缺口。免费路线不免除数据资格、历史 PIT、状态与公司行为完整性校验。

## 原件与可复核性

官方文档通过官网前端使用的公开读取路径取得：`POST https://www.baostock.com/helpdocs/api/markdown/home.md` 与 `pythonAPI.md`，正文 `{}`。这只是文档读取，不是账户或行情 SDK 请求。

官方 Markdown、PyPI 元数据、完整 wheel 及认证相关源码原件保存于忽略目录，含获取时间、长度、SHA 和 URL：[原件清单](D:/dsh-proj/Roll/backend/.roll-data/ticket19-continuation/source-docs/auth-doc-manifest-2026-10-09.json)。该目录没有用户密钥；未执行下载源码或修改环境依赖。现有代码、任务状态与资格均未修改。
