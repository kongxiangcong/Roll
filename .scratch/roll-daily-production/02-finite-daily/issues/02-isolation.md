# 2.2 多证券独立运行与失败隔离

Status: ready-for-agent
Execution: open
Type: task
Spec: ../spec.md#r2
Blocked by: 前阶段完成；前一ticket完成

## 需求
两只持仓和一只关注；单证券/单来源失败不阻断其他证券；保留账户确认和来源开关；不启用自动交易。

## 验证
针对公共API/真实模块的离线确定性测试、前端类型检查与构建；运行条件不足时明确记录，不能标作通过。

## Answer
待实现。

## Comments
2026-10-26：按用户授权创建。
