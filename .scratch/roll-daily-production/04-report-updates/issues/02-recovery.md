# 4.2 自动报告版本与重启幂等

Status: ready-for-agent
Execution: open
Type: task
Spec: ../spec.md#r2
Blocked by: 前阶段完成；前一ticket完成

## 需求
worker产出初报/更新版，输入不变不增版本；任务身份含证券/日期/类别/次数；重启不重复；旧报告可读取、可验证；连续10交易日验收表。

## 验证
针对公共API/真实模块的离线确定性测试、前端类型检查与构建；运行条件不足时明确记录，不能标作通过。

## Answer
待实现。

## Comments
2026-10-26：按用户授权创建。
