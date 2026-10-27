# 09命令、红绿与实际结果

所有代码/测试命令cwd为rv-ticket09，Python为原Roll/backend/.venv/Scripts/python.exe，PYTHONPATH显式指向本工作树backend/src。pytest独立basetemp在原Roll/.scratch/rv09-*，不提交数据目录。实现依据spec/09和已确认公开service/API/renderer/backup seams；本票未启动CODEX。

|步骤|命令范围|实际结果|
|---|---|---|
|red01|test_fixed_markdown_delivery_manifest_and_download_are_immutable|ModuleNotFoundError report_deliveries，1failed22.75s；原工具输出，尚无单独txt|
|green01|同公开固定MD/manifest切片|1passed15.95s|
|red02|test_pdf_failure_retains_markdown_and_retry_creates_new_delivery|PDF_NOT_AVAILABLE，1failed16.87s|
|green02|前两测试|1pass/1fail23.16s；真实TEMP ACL拒绝，保留PDF_RENDER_FAILED细节|
|green02b|同PDF失败保留/重试|改为store/runtime/report-render临时目录，1passed22.62s|
|red03|HTTP下载切片|沙箱TestClient挂起；CIM查询本身亦被沙箱拒绝。正常权限精确核CLI/PID56040和58260，仅停止这两个pytest进程，证据red03-owned-hang.json|
|red03b|同HTTP切片正常权限|实际404缺route，1failed15.34s|
|green03|实现HTTP routes后|1passed14.13s|
|red04|备份/恢复+重算hash错误core|原备份未拒绝新增delivery错误绑定，1failed32.24s|
|green04|新增关系/manifest/固定索引验证|1passed28.36s|
|red05|实际空行表格回归|PDF含管线分隔文本，1failed21.08s|
|green05|适配空行/表前说明|1passed16.95s|
|method06|公共renderer安全/图/65行长URL/超时|1passed21.73s；8页METHOD独立视觉QA|
|red07|独立新表列宽回归|首次CJK visitor分段采集错误，1failed19.49s；保留而不当作产品红灯|
|red07b|分组文本采集修正后|明确实际169.76宽而非两列表半页宽，1failed17.54s|
|green07|新表头/分隔行边界修复|1passed20.11s|
|regression08|test_report_deliveries.py + 原08 backup/取消重试两测试|8passed109.06s|

安装命令 `uv pip install --python <原venv> reportlab==4.4.9` 首次沙箱3次socket10013重试后失败11秒，正常权限同命令成功安装reportlab4.4.9/pillow13.0.0。uv lock --offline因原baostock未在指定缓存失败；正常权限uv lock成功解析63包12秒，只新增两依赖及resolver平台marker，未缩小Python支持范围。

PDF技能marker：bundled node执行技能container_tools/mark_artifact_operation_started.mjs `--operation-kind create --expected-output-count 1 --output-format pdf`，首个green02 authoring前成功一次exit0，stdout为空。随后重渲为同任务修订，不重复marker。

实际路径：verify_real_delivery.py将08公开Backups恢复新rv09-real01，生成01；render_real02.py追加02不覆盖；verify_http_recovery.py从完整隔离8029 API生成03/下载6文件/导出/恢复到新rv09-restored01，实际结果real03-http-recovery.txt/receipt.json。这些脚本含固定验收ID/路径是证据入口，生产代码无这些常量。脚本拒绝覆盖已存在恢复目标。

全页渲染：bundled Poppler `pdftoppm -r 96 -png <实际PDF> <隔离qa/pages03/page>`，45页；METHOD同法8页。bundled Python/PIL仅生成contact图并采集PNG哈希。生产ReportLab子进程不调用Poppler或外部浏览器。首次01与02的页图/交付原文保留，最终03图SHA及人工视觉范围见visual-qa03.json。

所有首次失败/测试构造错误/实际产品失败均分列；没有把后续绿灯改写成首次通过。无全后端/前端宽回归、外部新来源、模型、账户、SEALED或训练动作。
