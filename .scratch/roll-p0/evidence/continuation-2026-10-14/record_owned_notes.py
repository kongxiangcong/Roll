"""Prepare only this continuation's tracker hunks; retain pre-existing dirty text."""
import difflib
from pathlib import Path
import subprocess

ROOT = Path('D:/dsh-proj/Roll')
EVIDENCE = ROOT / '.scratch/roll-p0/evidence/continuation-2026-10-14'
common = '2026-10-14 本轮继续工程独立接受：'
notes = {
    '.scratch/roll-p0/issues/20-policy-continuous-shadow.md': common + '新增后继研究政策、不可变迁移及原持仓/ADD批次各自期限，独立政策/模拟冻结和连续 METHOD 影子。迁移后续数量、损坏帧、UNKNOWN/错过交易日、OPEN暴露及两项期限P2均完成公共入口验证和审阅闭合。既有v1接受证据保留；新增v2仍缺完整经济/统计协议、对应验证器和合格后生产派发，不能把 policy_and_simulation_frozen 解释为完整实验。Completion据扩展责任改partial，UNVALIDATED/NOT_GRANTED，旧实际模型/预算不变。见[本轮独立验收](../evidence/continuation-2026-10-14/acceptance.md)。',
    '.scratch/roll-p0/issues/25-current-actions.md': common + '券商费用原文、版本/账户/资金/期限、公共估算与ACTUAL捕获/发布/当前复核已接通；设置默认折叠、确认丢响应后原回执重试及历史/手机布局通过。后继研究ADD/HOLD/WAIT/EXIT、反向冷却、显式批次迁移及连续METHOD已交付并修复独立P2。没有新正式资格。生产有效期/用途时效政策和v2完整验证/生产派发仍缺，Completion保持partial，不能用费用有效区间替代动作有效期。见[本轮独立验收](../evidence/continuation-2026-10-14/acceptance.md)。',
    '.scratch/roll-p0/issues/30-forward-archive-deadline.md': common + '新增不可变ACTION_WINDOW_SUCCESSOR及公共协议窗口消费者，显式绑定保存行动包/assessment/source IDs/义务审计，把候选和报告缺失行数接到原日线行及前向只读路径。原采集/解析/参考件指纹、旧包和重放保持，零新外部取数，不推定公告身份/支付/完整状态或DAILY/session。独立合后验证含固定IDs/损坏/重启；完整来源依据仍不足，Completion保持partial，真实前向起点不成立。见[本轮独立验收](../evidence/continuation-2026-10-14/acceptance.md)。',
    '.scratch/roll-p0/issues/31-engineering-delivery.md': common + '本轮实际实现政策/连续影子、费用与设置、公司行动窗口消费，按票级工作树合入并执行独立API19/6/3三个固定阶段、真实Chrome与最终TypeScript/Vite构建；两轴审阅提出的三项迁移/批次P2及输入完整性缺口已闭合。不是只做启动记录，也不宣称全239条/90AT或整套P0完成。20/25新政策验证/派发/有效期、27LOSS、30完整来源、28真实外发及32—34仍按责任保留。原启动切片和未提交内容保留；仅暂存本轮自己的记录。见[本轮独立验收](../evidence/continuation-2026-10-14/acceptance.md)。',
}
summary = '2026-10-14继续工程：已实现后继研究政策/独立冻结/连续METHOD及批次迁移、源绑定券商费用与设置回执重试、公司行动协议窗口实际消费。独立API固定阶段19/6/3通过，Chrome及最终构建通过，审阅三项P2已修复闭合。旧v1接受保留；20新增v2及25/27/30/31仍有明确协议/验证/生产派发/有效期、LOSS与完整来源责任，真实资格/起点未升级。原未提交修改保留。见[本轮验收](evidence/continuation-2026-10-14/acceptance.md)。'
notes['.scratch/roll-p0/execution-status.md'] = summary
patch = []
for relative, note in notes.items():
    path = ROOT / relative
    base = subprocess.check_output(['git', '-C', str(ROOT), 'show', 'HEAD:' + relative]).decode('utf-8')
    base_newline = '\r\n' if '\r\n' in base else '\n'
    original = path.read_bytes()
    current = original.decode('utf-8')
    newline = '\r\n' if b'\r\n' in original else '\n'
    if note in current:
        raise RuntimeError('Notes already present; do not duplicate')
    if relative.endswith('20-policy-continuous-shadow.md'):
        base_updated = base.replace('**Completion:** complete', '**Completion:** partial', 1)
        current = current.replace('**Completion:** complete', '**Completion:** partial', 1)
    else:
        base_updated = base
    if relative.endswith('execution-status.md'):
        anchor = '## 当前前沿\n\n'
        base_updated = base_updated.replace(anchor, anchor + note + '\n\n', 1)
        current = current.replace(anchor.replace('\n', newline), anchor.replace('\n', newline) + note + newline * 2, 1)
    else:
        base_updated += base_newline * 2 + note + base_newline
        current += newline * 2 + note + newline
    path.write_bytes(current.encode('utf-8'))
    patch.extend(difflib.unified_diff(base.splitlines(keepends=True), base_updated.splitlines(keepends=True),
        fromfile='a/' + relative, tofile='b/' + relative))
(EVIDENCE / 'owned-tracker-notes.patch').write_text(''.join(patch), encoding='utf-8', newline='\n')
print('Prepared five owned tracker hunks; prior dirty content retained.')
