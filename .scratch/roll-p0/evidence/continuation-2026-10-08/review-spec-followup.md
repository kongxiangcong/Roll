# Spec follow-up · Roll continuation

只读复核 `14568b1...6ad9928c71ebc0b3ffd59fcf8c9f25fdfc4c9461`；工作树 `review-fixes-live`，产品修复 `db9ef0c`。结论：原P2已解决，修复范围未发现新的有充分证据的规格问题。

- `backend/src/roll/agents/codex_process.py:364–365` 把父 `adjustment_source` 传入子 `DataRequest`。共用工具同时服务Codex和DeepSeek。再次零联网捕获确认：父/子 `FUYAO` 相同，日线/报价来源及required_fields也保留。票12 DataRequest契约与spec:193的显式来源边界恢复。
- 市场模块提供 `SourceResolutions.can_reuse_archives`，app把必需查询传给两个后端。它读取真实revision的变化依据，不依赖缺失hash的旧target审计复制；旧运行/快照不修改。拒绝复用后仍沿既有有限重查路径保存原因，符合spec:193、211，不新增搜索循环。公共API测试覆盖两个跨后端方向、一次新取数、旧档案不可变与零联网旧回放。
- 四个固定宽基DAILY/QUOTE需要8次调用。复盘worker调整为固定共享8次，股票和背景共同扣减；8秒/4MiB、3尝试、退避、取消及缺口保持，模型后端8工具/6HTTP硬帽不变。新测试明确覆盖空账户四宽基与持仓共享预算下的未填缺口；没有修改研究资格、账户或拓展动态背景。

读证据 `review-source-contract-final-green.txt`：4 passed/34.63s；`review-reviews-final-green.txt`：25 passed/107.32s。均为METHOD工程回归，未称实际模型/行情资格。本复核未重跑长套、浏览器或网络模型任务；仅执行无凭据、ROLL_ENV=test、工作树PYTHONPATH的微型捕获。

Spec follow-up: original P2 resolved; 0 new findings. 最终整套与默认Chrome结果由根单独记录。
