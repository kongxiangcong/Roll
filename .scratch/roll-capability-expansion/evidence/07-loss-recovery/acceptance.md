# LOSS原因绑定恢复验收

用户2026-10-15确认规则：显式重新确认损失边界并取得后继资格后恢复，保留原峰值和暂停历史。API/持久化/设置页面现已实现，真实资金未启用；票07按真实条件边界保留partial。

## 实现

恢复检查绑定账户、资金版本、部署、当前资格、原LOSS事件、当前损失事实、原损失范围及恢复锁。原资格必须已撤回/到期，且新资格显式关联原记录、在暂停和资金重确认后登记，并通过原资格检查。新阈值须严格高于保留峰值。REAL使用权威估值重放；METHOD凭证只用于隔离工程验证。

激活在同一SQLite写事务内重验检查快照、保存经原件校验的回执、恢复NEW_RISK并登记通知事件。不会复活旧资格、回放旧动作或删除原暂停。原峰值/历史标记保留；后续再次越界重新锁定，原恢复回执不能清除新触发。恢复回执及其父检查/规则均传递校验。请求不确定时保持原幂等键；明确条件变化且未提交时可重新检查。

## 验证与失败记录

- api-final02.log：42通过、1失败/225.68s。失败是旧successor测试缺少监测包，baseline-successor.log在33d2a9c导出基线同样失败；只修复测试输入为monitored_package，successor-final.log单项1通过/9.22s。未掩盖生产失败。
- api-final.log：正向路径、捕获与提交间变化、原件损坏、再次触发均验；history-red.log保留历史标记缺陷的原始失败，随后修复并纳入42通过。
- process-final.log：2通过/29.62s，真实子进程在事务提交前/后终止，分别保持LOSS暂停与恢复唯一已提交回执。
- browser-final.log：原METHOD正向、旧资格REVOKED、刷新及390px页面1通过/25.5s。
- browser-refusal.log：误用未播种工厂；browser-refusal-final.log：测试先unroute后fulfill导致Route already handled。均保留，修复仅涉及验收配置/拦截。最终browser-refusal-green.log：1通过/29.3s，明确拒绝→重新核验→刷新→实际隔离恢复全部通过。
- build-final.log：TypeScript/Vite构建通过。
- 双只读审查：产品开放问题0。preservation.json保护15份交接文件，model-preservation.json保护12份旧模型依赖。

## 边界

本轮未替真实用户填金额、签发真实后继资格或恢复真实资金。METHOD真实进程/HTTP/浏览器成功只说明工程闭环。真实恢复仍需用户自己的边界确认、当前完整可追溯损失事实、合法有效的后继资格及当前部署/验证条件；缺项保持暂停。09预算已经CLOSED_NO_RETRY，不以本票重新采集。
