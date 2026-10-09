# BaoStock METHOD fixture 时钟修正

2026-10-09，本次现有基线的 `test_baostock_raw_status_are_archived_and_offline_replayed` 在 FastAPI 主 Seam 稳定复现失败。工作树 `codex/ticket19-public-history` 运行既有单测：`python -B -X utf8 -m pytest backend/tests/application/test_baostock_evidence.py::test_baostock_raw_status_are_archived_and_offline_replayed -q --tb=short -p no:cacheprovider`，1 failed，6.05秒。精确症状为 `historical_limitations=['PROVIDER_CURRENT_REVISION_NOT_PROVEN_POINT_IN_TIME']` 且 `point_in_time_input_allowed=True`，测试预期False。根原基线红证据 `baseline-focused-red.txt` 有相同症状。

诊断假设按优先顺序：固定响应首次收到时间已经早于默认当前请求截止；生产时间门禁变化；请求与重放使用时点不同。第一假设预测只把请求cutoff固定到早于响应received_at的历史时点就恢复原断言。实际仅改该测试请求增加 `cutoff=2026-09-30T16:00:00+08:00`，它早于注入worker声明的 `received_at=2026-10-09T00:00:00+00:00`。默认当前cutoff原本在10月9日凌晨以后，使True符合既有生产规则，属于fixture随真实日期漂移。

保留原False断言、时间门禁和原归档/重放断言，无任何生产变化、回填时间或模型资格更改。只使用注入METHOD测试worker，不访问真实BaoStock或扶摇网络接口。既有模块完整聚焦回归结果另记于下方；未重复全后端集合。

聚焦绿：同解释器/PYTHONPATH，`python -B -X utf8 -m pytest backend/tests/application/test_baostock_evidence.py -q --tb=short -p no:cacheprovider --basetemp=.scratch/baostock-clock-green`，12 passed，33.98秒。第一假设得到单变量修正验证。没有新增调试代码或生产仪器化。
