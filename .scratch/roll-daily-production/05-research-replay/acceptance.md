# 阶段 5 验收

实现：现金事件按证券隔离；旧单证券事件允许从冻结范围消歧，多证券缺证券拒绝；权益税按证券/入场批次/预测联合匹配。新 shadow_code 自动改变，旧冻结不重写。

`research_report_delivery.py` 复用公开 API，校验输入归档 SHA，遍历冻结 CAL 观察日期生成预测（明确记录质量排除），推进同一连续账本，校验重放，调用隔离 QuantStats 保存报告与同窗三项基线。不拟合、不读取 SEALED、不授予资格。

验证：shadow_security_cash、shadow_record_close、shadow 共 13 passed；research_report_delivery 共 2 passed。后者从全新 METHOD 研究库调用真实 API/SQLite 和 QuantStats 0.0.86，验证导出 SVG、重启幂等与旧代码拒绝重放，不依赖原 Windows METHOD donor。

真实验收限制：仓库中的真实模型 8be461f3-af8b-4f0f-a707-13e41cf48249 引用输入 SHA 64deada41e4b3ee1056e56b0c36568f8d783896807982131a73ff10d86bac9d8（7914804 字节），当前工作区无该原件或运行 SQLite。未生成、未声称真实数据研究报告。需在原运行库登记关联后继完整冻结后执行下列命令，不能修改旧指纹。

```sh
# 服务设置 ROLL_QUANTSTATS_PYTHON 为 quantstats==0.0.86 的隔离 Python
uv run --project backend python scripts/research_report_delivery.py --freeze-id NEW_FREEZE_ID --output research-delivery.json
# 如果仅渲染失败，使用相同冻结已保存的 revision，不重建预测/账本
uv run --project backend python scripts/research_report_delivery.py --freeze-id NEW_FREEZE_ID --render-only --output research-delivery.json
```

报告服务器已保存原始曲线、基线、输入/输出指纹、离线 HTML。客户端摘要不构成独立验证。重试预测阶段可能保留未使用预测，不能重置已有账本。
