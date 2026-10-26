# Ticket 12 — Spec review

相对 `8787f84` 只读审查 Docling 服务/worker/API/UI/测试与运行时准备证据，依据 [ticket 12](../../issues/12-document-tables.md)、spec ID-08。未测试、联网、安装或下载权重。定向复核开放 0 项。

**P2 已关闭：输出目录失败终态。** mkdir 与 tasks 登记现纳入已提交RUNNING后的 try，准备失败写 FAILED，不留下活host不可取消的锁；事务内同key并发重验保留。`directory-red.log` 保存原失败，`directory-green.log` 3 PASS/25.26s：真实隔离文件/目录冲突返回FAILED、相同key幂等，修复目录后新key可COMPLETE，原PDF仍可读。

其余原件边界合理：只消费已存财务事实绑定的PDF，原SHA校验、选页范围与派生页码校验明确；派生表/文字独立归档，review_required 保持true，未修改源金额或事实。UI以React文本渲染来源内容，没有指令执行入口；括号负数、脚注、跨页说明及原PDF链接保留。worker离线开关、网络拒绝、CPU/内存/时限与取消逻辑已实现，但METHOD取消仅证明注入worker工程路径，不能代替真实Docling进程资源/取消验收。

runtime reference 为 UNAVAILABLE，未伪称解析可用。runtime-plan 与 resolve* 保存 CPU仓库/代理失败及后续官方Windows wheel解析尝试；尚未完成包/权重许可与指纹、真实可读财报/复杂跨页/扫描样例验收。METHOD API2 PASS/17.28s、Chrome1 PASS/17.2s/build成功不能替代上述实际运行；本票应保持 partial，并保留原 pypdf 可读入口。

本次增量还将 provider PARTIAL_SUCCESS 或选定页没有文本/表格明确记 PARTIAL，不再记全成功；缺页编号进入运行warnings，UI显示“选定页未提取到文本或表格”，不把空白页误称确定解析失败，也不静默丢页。原派生工件与来源内容仍分开保留。最新UI/真实运行验收据实另归档；本复核没有重跑。

## Partial 收口核对

已核对最终 acceptance 与 issue12：工程API/归档/查询/页面及METHOD正向交付，实际运行缺口明确分列，未将安装预演或元数据访问计作推理。最终 `pip-bounded-resolution-receipt.json` 为 CLOSED / RESOLUTION_WALL_TIME_LIMIT / 600.038993秒，model_downloads=false；运行时仍 UNAVAILABLE，未安装或运行模型。包/模型许可指纹、实际可读财报/复杂跨页/扫描样例及真实资源/取消仍待验，继续 partial 合理，不应重开预算。

最新UI已提供可展开边界、失败尝试原件链接，表格列按原offset排序，文本渲染不执行来源指令。`build-latest.log` 通过；`browser-latest-chrome.log` 现已完成1 PASS/19.3s，属METHOD工程验收。公开代码问题开放0；13依赖12实际完成尚未满足，独立14可继续。未执行测试、联网、安装或并行实现。


## 2026-10-18 最终规格复核

| 验收条件 | 结论 | 证据 |
| --- | --- | --- |
| 锁定代码/OCR/表格权重许可与指纹，隔离运行 | 通过 | docling-reference.json：11 包版本、8 运行时工件 SHA256、模型许可；独立 venv；requirements-lock-02 |
| 已存 PDF 生成表格/文本派生，保留页码/边界/hash/版本/回执 | 通过 | real-api-parse.json、real-api-scanned.json、runtime-check/*.json |
| 公开查询与页面原表定位、低置信/失败提示 | 通过 | real-browser-green.log；解析尝试原件；告警展示 |
| 与结构化源并列、不自动覆盖、内容不执行 | 通过 | 面板并列展示；无写事实路径；输入按文本渲染 |
| 真实可读财报 + 复杂跨页 + 扫描样例 | 通过 | 三季报页 10；年报 102—103 图像页 OCR；跨页告警与独立页码 |
| 版本、验收、真实/METHOD 边界、原失败与剩余条件 | 通过 | acceptance.md、code-versions-final.json、旧 CLOSED 回执保留 |

残余：OCR 准确率无人工基准；跨页表头不自动合并是明确设计；权重许可按模型卡记录。
