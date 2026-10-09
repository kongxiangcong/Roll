# Windows venv launcher 与真实 HTTP 服务生命周期

根实际探针表明Windows venv可重定向解释器：Popen.pid41316，而服务os.getpid32428。因此原d267b84 helper精确Popen.pid校验不能作为成功所有权证据；旧v2仅健康检查的“重启”证明保持provisional，不能升级为已终止旧服务。生产代码/测试在完整回归期间保持冻结，本次仅辅助脚本/证据变化，先合入集成3eda8c6。

每次start生成新nonce，子解释器在app导入/创建前将nonce、规范数据目录、实际os.getpid写入唯一文件，经flush/fsync和原子replace发布。父进程要求HTTP identity与该启动receipt逐项一致、nonce/目录符合期待、Popen launcher仍存活，首次/重启均通过才返回给后续写入。receipt不假定launcher与实际服务PID相同。辅助脚本使用启动它的sys.executable，因此实际验收显式由根backend/.venv/Scripts/python.exe启动。

正常stop仅调用临时包装app的nonce认证端点，将本次uvicorn.Server.should_exit设True，随后等待launcher退出、探测监听端口关闭。生产app未增加任何端点。错误nonce返回403。启动异常/期限或正常退出失败仅凭本次有效receipt终止其实际PID，再收尾本次launcher；Windows已不存在PID的错误允许继续验证关闭。stop幂等，避免重启失败时finally重复终止已退出旧PID。启动receipt原子发布避免半份JSON，启动identity请求timeout1秒、总启动期限20秒。无论cleanup成功与否，finally保留报告并关闭客户端/日志。

真实Windows生命周期验证（无外部市场网络）：第一次启动Popen26852/实际35504，第二次43564/28572，两服务均认证关闭且监听关闭；最终代码回归Popen45416/实际41916→Popen42028/实际34136，新nonce与实际PID均不同，两个graceful=true/listener_closed=true、账户version0前后相同。完整JSON `lifecycle-v3-final.json`。

真实受控bootstrap失败验证：临时隔离源的create_app抛异常，launcher43084/实际receipt32488，helper退出1、steps为空、未执行市场/账户写入，startup内部收尾后listener_closed=true。完整JSON `lifecycle-startup-failure.json`。这些仅证明实例隔离/停止与重启；最终真实3126行来源采集和重放由根集成v3重新运行留证。
