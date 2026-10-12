# Ticket 20/21 工作树清理收据

2026-10-11；依 implement-spec 第9步及本轮明确授权，只清理两个已经合入的工作树，不修改tracker进度，不删分支，不推送。

- `D:\dsh-proj\Roll\.scratch\worktrees\ticket20`：HEAD `4a099d891360b5f428de4ea6063826b7bcf1524e` 已在集成祖先链，tracked clean。提升身份后核实本轮自有pytest/browser临时文件8543件，完整绝对路径清单见[预检](cleanup20-21-preflight.json)。普通权限status没有显示私有pytest目录，不能作为完整清单；按完整清单另获明确清理授权。
- `D:\dsh-proj\Roll\.scratch\worktrees\ticket21`：HEAD `aef9b27bd32bb9983fcce77ab642a17c2dfcf3e0` 已在集成祖先链，tracked clean。自有validation红/绿临时文件1519件，同一预检保存逐件路径。对应红/绿日志和最终验收均已在集成根。
- 相关Python/Node/浏览器进程路径核查为0；没有停止其它进程。每棵树恰有两个junction：backend/.venv精确指向根backend/.venv，frontend/node_modules精确指向根frontend/node_modules。逐个用 `.NET Directory.Delete(path,false)` 只解除链接本身，再确认根目标仍在，没有递归进入目标。

必要运行件清理前逐源/根目标核SHA256及长度，清理后再次核根目标，均0差异：20历史浏览器312件/16,195,497字节、20修正版浏览器312件/16,195,499字节、21最终浏览器315件/17,887,006字节、20最终独立METHOD193件/10,755,082字节、21独立METHOD209件/17,792,808字节。根合计1341件，78,825,892字节，原manifest及工程版本身份保留，不把不同版本成绩拼接。21实际一致副本的冻结原档、最终验证input/manifest三个归档另核SHA/长度，不启动原19或消费SEALED。

原生Git第一次删除20时注销了worktree登记，但实体目录部分残留。再次调用确认已不再登记，见[原输出](cleanup20-remove-error.txt)。随后用[收尾脚本](finish-cleanup20-21.ps1)在同一PowerShell内再次检查准确绝对目标、无残余reparse points，`Remove-Item -LiteralPath`仅删除这两棵自有工作树，准确删除21登记。没有跨shell枚举或拼接删除命令。初始[预检/清理脚本](cleanup20-21.ps1)及完整[最终结果](cleanup20-21-results.json)保留，最终进程退出0。

清理后根Python环境、Playwright包/CLI/registry、已安装Chrome共8个代表文件SHA/长度与清理前相同，12个19模型指纹依赖源码相同。原受保护未跟踪 `.scratch/local-commit-20261011`、19 negative-real-integrity lock/backups、`.workbuddy`均存在且未操作。ticket23、ticket30仍为登记中的独立工作树；23待审批材料与其运行件未操作。20/21实施分支仍保留。根只增加本次scoped清理证据，没有产品源码或tracker改动。
