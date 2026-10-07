# TDD 工具输出摘录

本文件为对已返回工具文本的可读摘录，不冒充原stdout字节或重新运行的原红。实际初始权限/临时目录环境错误先修正，随后产品红如下：

第一次公开用例 `test_unsupported_fit_is_a_persisted_failed_attempt_without_probability`：

```text
response = client.post('/api/research/protocols/'+pid+'/models', ...)
assert response.status_code == 201
AssertionError: {"detail":"Not Found"}
404 != 201
1 failed in 6.73s
```

增加持久失败/预算/GET/预测拒绝后：`1 passed in 4.33s`。

第二切片 `test_method_artifacts_time_isolation_forecast_and_offline_replay`：

```text
model = response.json()
assert model['status'] == 'METHOD_ARTIFACT_ONLY'
AssertionError: assert 'FAILED' == 'METHOD_ARTIFACT_ONLY'
1 failed in 9.14s
```

补齐固定四特征、开发拟合、原时间外预测归档、唯一校准工件和原输入预测重放后：`2 passed in 11.32s`。加失败预算/未知时点边界后：`4 passed in 13.60s`。

最终集成原stdout独立保存 [backend-final.txt](backend-final.txt)，35passed85.57s；未把初始目录权限错误称产品红，未新增低层HTTP/SQLitemock。
