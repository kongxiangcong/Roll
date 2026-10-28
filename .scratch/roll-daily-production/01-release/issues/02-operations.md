# 1.2 启动停止、诊断、备份恢复与可移植配置

Status: ready-for-agent
Execution: resolved
Acceptance: core-verified; target-environment-checks-pending
Type: task
Spec: ../spec.md#r2
Blocked by: 前一ticket完成

## 需求
Windows脚本使用构建产物；保留PID身份核验；配置情绪模型目录并保留哈希检查；干净目录启动、备份恢复测试。

## 验证
针对公共API/真实模块的离线确定性测试、前端类型检查与构建；运行条件不足时明确记录，不能标作通过。

## Answer
实现完成。锁定安装成功；前端类型检查/构建通过；API构建网页和真实进程备份/升级/恢复测试10通过（26.01s）。Windows脚本实机验收待执行，未标作通过。

## Comments
2026-10-26：按用户授权创建。
