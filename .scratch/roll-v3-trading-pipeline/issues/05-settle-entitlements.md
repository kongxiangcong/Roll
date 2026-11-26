# 05: 跨除权日结算在途权益

Status: ready-for-agent

归属：共享执行核 · 权益与净值。依据：[主方案 §5.3、§11.1、§14](../../../docs/design/architecture/roll_v3_trading_pipeline_spec.md)。

**What to build:** 由 CLI 查看登记日持仓产生的权益如何在除权、支付或上市时影响净值、现金和可卖股数。

**Blocked by:** [01 冻结并重读一段真实行情](01-market-snapshot.md)、[02 建立真实账户镜像](02-account-mirror.md)

## 验收

- [x] 用江西铜业 2025-07-21 登记、07-22 除息记录核对每股实际税前派现 0.70 元、参考扣减约 0.6965 元、参考昨收 23.70 元及原始开盘 23.73 元，各值可追溯。
- [x] 从 100 股每股 10 元起，每股派 1 元、除息价 9 元。支付前持仓 900 元、应收 100 元、可用现金 0 元，支付后应收转现金，全程净值 1,000 元。
- [x] 另演练每股送 1 股、除权价 5 元。上市前原 100 股可卖，另有应收 100 股；上市后持仓 200 股、应收为零。重复结算只转入一次。
- [ ] 回测、双基准及影子结果明确股息红利税前并含交易成本；真实账本以实际入账、扣税流水为准。

## Comments

- `roll entitlements evidence --snapshot-id <行情快照> --symbol 600362.SH --ex-date 2025-07-22` 离线核对公司行动与原始开盘记录。实际派息和参考扣减来自发行人公告 2025-026。扶摇原始行情给出前日收盘 24.40 元及当日开盘 23.73 元，参考昨收按发行人扣减和报价精度得 23.70 元。[公司行动观测](../../../config/research/600362.SH/dividends.json) · [发行人实施公告](https://static.cninfo.com.cn/finalpage/2025-07-15/1224163682.PDF) · [原始行情对照](../../../docs/design/research/roll_dual_pipeline_review.md)
- `roll entitlements settle` 以登记日账户批次产生在途权益，`roll entitlements value` 以冻结原价计入净值。模拟账本在派息日收盘结转现金并在上市日开盘转入可卖股份。真实账本通过 `roll entitlements confirm` 录入实际到账，通过 `roll account cash` 单列实际扣税。[CLI 演练](../../../backend/tests/test_v3_entitlements.py)
