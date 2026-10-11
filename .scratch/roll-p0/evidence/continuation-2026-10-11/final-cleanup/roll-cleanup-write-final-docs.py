import json
from pathlib import Path
r=Path('D:/dsh-proj/Roll')
e=r/'.scratch/roll-p0/evidence/continuation-2026-10-11/final-cleanup'
s=json.loads((e/'summary.json').read_text(encoding='utf-8'))
assert s['status']=='PASS' and len(s['removed'])==10
assert s['unknown_private_files_retained_by_same_volume_rename']==2
body=f'''# 2026-10-12 最终实施工作树清理收据

结果：精确清理10个已合入、无跟踪变更的实施工作树，10个分支及其接受OID保留。Root在清理期间固定`{s['root_head_during_cleanup']}`；release `{s['release_id']}`。原42项非本票untracked入口集合未改变，无push/PR。

最终Preflight和Post各完成一次接受的字节核验；中间仅比较元数据和文件集合。原运行清单{ s['manifest_runtime_rows'] }行、唯一源{ s['unique_runtime_sources'] }项、唯一保存目标{ s['unique_runtime_targets'] }项；Preflight唯一校验{ s['preflight_unique_proofs'] }项，Post保留端校验{ s['post_retained_proofs'] }项。{s['root_dependency_files']}项Root依赖的集合与字节、15保护源码、3许可JSON工件、原19 SQLite字节均一致，未连接任何SQLite。9个精确junction只解除链接，Root依赖目录保留。

预检发现的3802项未覆盖材料已闭合：3687个公开生成/运行文件、304603079字节复制至`.roll-data/implementation-evidence/final-cleanup-residual-20261012/`，源与副本SHA/长度一致；113项私有文件有公开METHOD writer/case证据，仅元数据排除。两项browser-green2私有文件来源仍UNKNOWN，按精确同卷rename保留至`.roll-data/implementation-evidence/final-cleanup-private-retained-20261012/ticket28/browser-green2/notification-private/`，FileID/卷/长度/mtime不变、源消失；未读取、hash或copy私有内容，未声称内容验证或METHOD身份。第九runner auth源与旧保存目标保持原元数据专用边界。Root原63项外部运行源仍保留。另有1项Ticket30 pytest nodeids当前530字节与历史清单不同：5个已登记公开cache项核对仅此项改变，历史保存端仍按原SHA/长度验证；当前版单独保存至`.roll-data/implementation-evidence/final-cleanup-cache-current-20261012/`并验证源与新保存端，旧清单未改，初次完整预检拒绝诊断保留。

原40项Node进程均已证明在删除范围之外：30项相对模块路径经精确PID/CreationDate/父链与有界CWD元数据验证，其中20模块存在、10模块缺失的差异保留。一次刷新32项后另有历史进程退出；最终窗口{s['outside_process_records']}项实际存活进程归属再次核验；该证明仅是清理边界，不是模块可用性。清理接受区间没有停止进程；此前精确停止2个自有只读预检PID以修正小缓冲及串行I/O，业务/来源进程停止0，两次分别读取1088844991及2294891511字节、无删除，无接受全字节sweep。1MiB缓冲公开控制SHA等价；最终最多4个只读校验线程，8份公开控制在StrictMode 3下长度/mtime/SHA完全等价，首适配返回属性诊断保留，列表shape及AST核对保留。初次Git executable选择失败、初次未覆盖输出拒绝、Root外部源coverage失败、CIM时间表示和定位diagnostic均保留，未计作业务PASS；此前失败预检未删除材料。

清理不增加业务验收：实际provider审阅0、外部发送0、测试0、拟合/预测/SEALED/前向启运/资格签发0。95dd包实际Codex审阅仍恰一次；DeepSeek排除。25/27/28/30/31保持partial，32—34真实条件未成立，FITTED_UNVALIDATED / NOT_GRANTED不变；239条手工账本不是全规格PASS。

原v14完整字节预检已实际通过；首次Execute被文件集合比较误报拦住，未移动私有文件或删除工作树。原因是Execute按basename排除了Ticket26 `.uv-cache/sdists-v9/.git`缓存标记，Preflight只排除工作树根`.git`。v15仅替换这一比较表达式，使前后规则一致；十棵树完整文件集合和353101条原proof/inventory元数据再次相同，新执行器追加字节绑定，原执行器和完整Preflight原字节副本保留，原接受时间及60分钟窗口未刷新、源或保存端完整SHA sweep未增加。控制延续工具首轮Windows长路径metadata失败及修正同样保留，不算业务测试或新增接受字节轮次。见[控制延续](roll-cleanup-v15-control-continuation.json)、[原Execute拒绝](roll-cleanup-v14-first-fileset-execute-failure.json)。

v15实际完成2项私有同卷保留、9项链接解除及第一棵ticket25原生Git移除，随后被分支校验参数拼接错误拦住；实际正确参数读取确认其接受分支OID仍为759033c8bf87af1fecd7dff9021232b33542df0b，删除根及注册均消失，其余9棵仍存在。v16为精确部分续执行：原首棵完成状态、私有FileID及已解除链接重新核验，剩余9棵集合和323943条保留/剩余元数据一致，接受时间继续保留；新执行器和续执行清单追加绑定，私有移动/解除链接不重复、源SHA sweep不增加，只移除剩余9棵并逐项保留进度。v16随后实际Execute/Post通过，10棵总完成。两个清理控制错误均留原失败，不计为业务失败或重写成单轮全绿。见[精确续执行](roll-cleanup-v16-native-resume.json)、[分支参数拒绝](roll-cleanup-v15-first-branch-argv-execute-failure.json)。

[摘要](summary.json)、[保存文件字节收据](receipt-files.json)、[实际native结果](roll-cleanup-batch-v6-native-result.json)、[精确release](roll-cleanup-release-v14-exact3802.json)。完整大型Preflight/Post、原v14接受Preflight及v15续执行前字节清单在Root ignored `.roll-data/implementation-evidence/final-cleanup-20261012/` 同名文件中保留；小控制/证明另存本目录。legacy v6机器receipt文件名不表示旧执行器：最终执行/后验为{s['actual_executor']}及所绑定helper，完整初始Preflight为v14，首次私有保留/链接解除及首棵移除为v15。
'''
(e/'acceptance.md').write_text(body,encoding='utf-8',newline='\n')
status=r/'.scratch/roll-p0/execution-status.md'
old=status.read_text(encoding='utf-8')
line='2026-10-12最终清理：10个精确实施工作树已清理，10个接受分支保留；完整运行材料、Root依赖/15保护/3许可工件/原19字节核验一致，原42项非本票untracked入口未改。3802项新增遗漏闭合（3687公开双端保存、113测试私有元数据排除、2来源UNKNOWN私有同卷rename保留且不读/hash/copy）；业务/来源进程停止0（先前自有只读预检中止2）、SQL连接0、实际provider/外发/新业务验收0。原失败诊断保留。见[最终清理收据](evidence/continuation-2026-10-11/final-cleanup/acceptance.md)。各票Completion和真实条件仍按下列当前账本，未宣称全规格PASS。\n\n'
assert line not in old
status.write_text(old.replace('## 当前前沿\n\n','## 当前前沿\n\n'+line,1),encoding='utf-8',newline='\n')
ticket=r/'.scratch/roll-p0/issues/31-engineering-delivery.md'
with ticket.open('a',encoding='utf-8',newline='\n') as f:
    f.write('\n\n2026-10-12 root最终精确清理接受：10实施工作树移除、接受分支保留，Root依赖/保护/原19与全保存运行件字节一致，2来源未确认私有文件仅同卷rename保留，未读取/hash/copy其内容；原未覆盖及定位失败完整留存。[清理收据](../evidence/continuation-2026-10-11/final-cleanup/acceptance.md)。无新增业务测试、provider、实际发送、SQLite连接、真实前向或资格。31 Completion保持partial；239账本及25/27/28/30、32—34缺口不因清理升级。仅本地记录提交，不推送。\n')
print('Final cleanup acceptance/status/end-of-ticket comment written')
