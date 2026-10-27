# 真实启动路径纠正

首次沿合法launcher启动，rv08-real02独立8028/5208的API/worker运行，但08公开jobs路由返回框架Not Found，旧worker没有创建08 run。launcher使用原venv且未显式指定PYTHONPATH；结合原venv editable安装，诊断为导入原checkout旧代码。未改源/请求、未发新增08章节。

保留real-start05-authorized.txt、mislaunch05-service-receipt.json及原logs；使用同一launcher -Stop按自身receipt精确停止，仅本票进程。然后在同一原入口设置PYTHONPATH为本工作树backend/src重启，API/worker/web均RUNNING。相同环境下的实际module.__file__及18源hash记录在real05-module-path-proof.json；实际第9run的execution_code_hashes、公开路由及CODEX回执再核与冻结版一致。没有假称检查了旧进程内部module.__file__。

原packet的请求/资料/取得/知识冻结日期全部保留。新执行实际为2026-10-27T14:34:44.831858Z开始，不倒填上午检查点日期。启动接线供09/10交接使用，不改冻结18算法，也不扩大四请求授权。
