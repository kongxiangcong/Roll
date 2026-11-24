# 05: 从成交 CSV 完成记账与对账

Status: resolved

**What to build:** 在新入口批量导入成交，凭回执核对账户。

**Blocked by:** 01

- [x] 导入一组实际成交格式的数据，显示导入结果与回执。
- [x] 核对现金、成交和逐证券持仓；重复导入同笔成交后，余额和数量只变化一次。

## Comments

`account import-csv FILE` 复用既有 Roll CSV v1–v3 导入模块，返回草稿、行结果和已有回执；首次导入经 `account confirm DRAFT_ID KEY` 入账。`account reconcile RECEIPT_ID` 按回执版本显示现金、成交及逐证券持仓。

`backend/tests/test_v2_csv.py` 通过。独立进程从 10000.00 元开账，批量确认江西铜业、浦发银行各 100 股后余额 6605.00 元。同一文件重传返回原回执，仍为两笔成交。成交确认后按开账回执重读，余额仍是 10000.00 元且持仓为空。
