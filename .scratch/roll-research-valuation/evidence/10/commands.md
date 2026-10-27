# 10 命令与实际结果

所有工作在rv-ticket10，基于integration0e472e5f。前端依赖junction指向原frontend/node_modules，未更改依赖清单。

- `node scripts/company-report-check.mjs`（cwd frontend）：red01缺导航；green01/01b首次默认日常夹具不完整导致DOM脱离，补公共响应后green01c PASS。
- red02缺截至时间；green02 PASS（未来拒绝、任务状态/取消/重试）。
- red03缺报告预览；green03遗漏展开details导致隐藏文本等待，按用户操作展开后green03b PASS（安全文本、PDF_FAILED保留MD、retry新链接、mobile）。
- red04缺共享跟踪链接；green04 PASS。真实readonly红灯/修复分别见real-tracking-red与-green。
- regression05/07-report PASS；red06为select的getByLabel严格定位遗漏，改角色定位后red06b暴露真正重载丢公司问题，写入明确选择后的公司深链，green06 PASS。
- regression07-report PASS（来源/模型未配置、无资料、公司隔离等）；regression07-daily PASS（原路径3次METHOD更新）。旧07生成截图复制本票后按HEAD原字节恢复。
- red08-active-job：查看旧任务后reload恢复旧task、无法等到新QUEUED；只读历史任务不写新任务恢复指针，green08-active-job PASS。
- `npm run build`：build01 TS2322(unknown ReactNode)，Boolean guard后build02/03/final通过；最终build-final08通过（仅保留>500kB提示）。未运行整个后端suite。
- `PYTHONPATH=当前backend/src python prepare_real.py`：Backups09→全新rv10-real01，backup a45cdc4b-79df-4ae0-bd62-cdec4b5f1076，7137735 bytes；原store不变。公开服务verify_real.py通过，真实下载字节/报告和交付/账户/取消任务均核验。
- 真实IAB操作按已观察控件完成，源/模型历史复用与网页新任务分账见README；没有外发请求。MD/PDF下载是浏览器实际下载，随后只读复制至证据路径。
- 初次sandbox New-Item junction被拒，沿同命令必要escalated成功。sandbox GetProcess/TCP/CIM探测不可信，escalated确认真实Vite5210 PID50308存活；重复启动报端口已占保留，未杀其它进程。API显式module路径正确。

脚本company-report-check最终输出目录按import.meta.url解析，避免不同cwd将截图落在错误目录；早期regression05用repo cwd时的派生截图不作最终证据。程序测试均METHOD，不是新真实来源/模型。
