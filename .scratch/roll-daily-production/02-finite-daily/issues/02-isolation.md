# 2.2 多证券独立运行与失败隔离

Status: ready-for-agent
Execution: resolved
Acceptance: core-verified; target-environment-checks-pending
Type: task
Spec: ../spec.md#r2
Blocked by: 前阶段完成；前一ticket完成

## 需求
两只持仓和一只关注；单证券/单来源失败不阻断其他证券；保留账户确认和来源开关；不启用自动交易。

## 验证
针对公共API/真实模块的离线确定性测试、前端类型检查与构建；运行条件不足时明确记录，不能标作通过。

## Answer
完成：页面和worker接有限名单；四项日常来源按名单授权、严格证券转换；财报参考证据不跨公司复用；移出名单停止新任务。17项公共API/worker测试通过，含两持仓+一自选、局部失败、重启；前端类型检查和构建通过。外网采集未在本轮真实运行。

## Comments
2026-10-26：按用户授权创建。
