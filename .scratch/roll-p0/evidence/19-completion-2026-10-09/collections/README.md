# 公开资料 metadata 快照与逐字节核验

运行 `backend/.venv/Scripts/python.exe -B -X utf8 .scratch/roll-p0/evidence/19-completion-2026-10-09/verify-collected-sources.py` 可重建本目录的 JSON 快照及上一级 `source-verification.json`。输入仅限本轮 `.roll-data` 下名称为 manifest、inventory、assessment 的公开 metadata 和上一级 `*receipts.json`；仅沿这些文件中明确记载的公共路径核验原件。公开年报与公告复用路径限于脚本列明的上一轮公共归档目录。

快照保留来源 URL、原件路径、SHA256、字节数、原 manifest 的 SOURCE received_at、发布/生效日期、事实及原件页码；完整抽取全文省略。快照属于 metadata，不能作为发行人公告原件、政策正文或原发布行情。PDF、原始响应及抽取全文未复制，仍在 ignored 的公开资料目录中。

每条同时具有 `path`、`sha256`、`bytes` 的引用独立重读原始字节核验，receipt 与 manifest 中的重复引用仍计为两条。全局唯一字节数按实际 SHA256 去重求和；分类间可能交叉引用，分类字节数不能相加。缺少声明 bytes 的引用单列而不计入三字段核验总数；HTTP 状态未记载的复用公告/年报保持 unknown，不推断为 HTTP200。非 200、索引 JSON、现查报价/状态 JSON、新闻定位线索、官方政策正文、发行人 PDF、报纸正文分别分类。

`structure` 仅做 PDF 头、JSON 解析或 HTML 头的格式检查；HTTP200 和哈希一致不证明正文语义正确、完整状态、历史首次公开时钟或更正链。2022 年过户费历史捕获的正文核对结论以原 manifest 的 validation_checks 为依据；旧 raw 字符串查询的单一 false 不覆盖规范化正文核对。

SOURCE 收到时钟只沿用原 manifest；`verification_at` 是本轮核验时钟。源 receipt 原 Windows 字节只读并保存其 metadata 文件 SHA256；新脚本、prose、JSON 使用 UTF-8 和 LF。本轮核验不访问实际数据库、SEALED、标签、模型或预算，不执行真实训练，不证明完整 PIT 或全部每日状态/权益，也不授予训练资格或证明独立校准与模型冻结。

采集尚可并行继续；主进程应在最终采集完成后重跑，最终以 `source-verification.json` 的时点与 summary 为准。
