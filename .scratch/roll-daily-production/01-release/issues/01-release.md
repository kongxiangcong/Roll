# 1.1 发布身份、锁定安装与构建产物服务

Status: ready-for-agent
Execution: resolved
Acceptance: core-verified; target-environment-checks-pending
Type: task
Spec: ../spec.md#r1
Blocked by: 无阶段内依赖

## 需求
健康接口给出源码提交与构建指纹；uv sync --frozen、npm ci、npm run build；API服务构建网页，未知API不能回退HTML。

## 验证
针对公共API/真实模块的离线确定性测试、前端类型检查与构建；运行条件不足时明确记录，不能标作通过。

## Answer
实现完成。锁定安装成功；前端类型检查/构建通过；API构建网页和真实进程备份/升级/恢复测试10通过（26.01s）。Windows脚本实机验收待执行，未标作通过。

## Comments
2026-10-26：按用户授权创建。
