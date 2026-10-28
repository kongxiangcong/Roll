"""Read-only audit of this heartbeat's startup schema additions and backup."""
import hashlib
import json
from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / 'backend/src'))
from roll.runtime.backups import Backups
from roll.decisions.lifecycle_journal import sha

directory = Path(__file__).parent
key = '2026-10-12T080740Z'
def read(suffix):
    return json.loads((directory / f'{key}-{suffix}.json').read_text(encoding='utf-8-sig'))
before, after, result = read('before'), read('after'), read('result')
old, new = before['protected'], after['protected']
added = {n: v for n, v in new.items() if n not in old}
changed = {n: {'before': v, 'after': new.get(n)} for n, v in old.items() if new.get(n) != v}
bp = {v['id']: v for v in before['policies']}
ap = {v['id']: v for v in after['policies']}
policy_changed = {n: {'before': v, 'after': ap.get(n)} for n, v in bp.items() if ap.get(n) != v}
policy_added = {n: v for n, v in ap.items() if n not in bp}
data = ROOT / '.roll-data/pit'
batches = [result['batch'], *result['batch']['supplemental_batches']]
with sqlite3.connect(f'file:{(data / "roll.sqlite3").as_posix()}?mode=ro', uri=True) as db:
    origin_rows = list(db.execute('SELECT * FROM capability_journal_origin'))
    anchor = json.loads((data / 'backups/capability-journal/origin.json').read_text(encoding='utf-8'))
    grant_count = db.execute('SELECT COUNT(*) FROM capability_grants').fetchone()[0]
    event_count = db.execute('SELECT COUNT(*) FROM capability_events').fetchone()[0]
    reports = []
    for batch in batches:
        run = json.loads(db.execute('SELECT value FROM retrieval_runs WHERE id=?', (batch['run_id'],)).fetchone()[0])
        digest = run.get('cleaning_report_hash')
        if digest:
            archive = json.loads(db.execute('SELECT value FROM evidence_archives WHERE sha256=?', (digest,)).fetchone()[0])
            raw = (data / archive['path']).read_bytes()
            assert hashlib.sha256(raw).hexdigest() == digest
            reports.append({'run_id': run['run_id'], 'source_id': run['source_policy']['id'],
                            'sha256': digest, 'report': json.loads(raw)})

backup = result['backup']
backup_path = data / 'backups' / backup['backup_id']
manifest = json.loads((backup_path / 'manifest.json').read_text(encoding='utf-8'))
# Avoid constructing the application again or applying migrations/restores.
checker = object.__new__(Backups)
checker.validate(backup_path, manifest)
backup_check = {'backup_id': backup['backup_id'], 'reason': manifest['reason'],
                'database_and_attachment_hashes_and_replay': 'PASS',
                'attachment_count': len(manifest['attachments'])}
assert manifest['reason'] == 'PROSPECTIVE_COLLECTION'
assert manifest['backup_id'] == backup['backup_id']
origin_valid = (origin_rows == [(1, sha(anchor))] and
                anchor['origin'] == 'EMPTY_LOCAL_PERMISSION_HISTORY' and
                grant_count == event_count == 0)
audit = {'heartbeat_id': key, 'collector_exit_code': 0, 'summary_assertion_exit_code': 1,
         'strict_summary_retained': True,
         'existing_protected_records_unchanged': not changed,
         'existing_protected_record_changes': changed,
         'new_protected_tables': added,
         'journal_origin': anchor, 'journal_origin_binding_valid': origin_valid,
         'capability_grants': grant_count, 'capability_events': event_count,
         'existing_source_policies_unchanged': not policy_changed,
         'existing_source_policy_changes': policy_changed, 'new_source_policies': policy_added,
         'new_sources_invoked': False,
         'runtime_unchanged': before['runtime_manifest_sha256'] == after['runtime_manifest_sha256'],
         'cleaning_reports': reports, 'backup_revalidation': backup_check,
         'integrity': result['integrity'], 'readiness': result['readiness'],
         'notification_required': True,
         'notification_reasons': ['EASTMONEY_DAILY_ACQUIRED_TO_FAILED', 'FIRST_CURRENT_STATUS_OBSERVATION',
                                  'STARTUP_SCHEMA_AND_SOURCE_REGISTRATION_ADDITIONS']}
(directory / f'{key}-state-change-audit.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding='utf-8')
note = '''
## 追加核对

采集器退出0、stderr为空。严格前后对比的断言退出1，原汇总保留：应用启动新增7张空表、1张含一条空权限历史起点指纹的表，以及4条上交所来源登记。原有受保护记录及来源策略逐项不变，CNEquity固定运行时不变。新增权限起点与本地原件指纹一致，实际能力授权及事件均为0；新增上交所来源本次未调用。

东财日线从昨日成功变为失败，本次0条入库，保留EASTMONEY_DAILY_SOURCE_FAILED与原响应缺失证据，未重试掩盖失败。巨潮公告连续失败6次，保留退避。东财当前交易状态首次取得1条来源观察，仅当前板块快照，上市阶段、除权及ST子型仍未知，不可作模型日线输入或交易所状态证明。

本轮新增55条事实、6批；累计424条事实、44批。102个归档和全部事实离线重放检查通过；PROSPECTIVE_COLLECTION备份重新核验数据库、102个附件哈希、引用与账户重放通过。可计数前向完整交易日仍为0；保持COLLECTING／NOT_GRANTED／system_usable=false。未自动训练、升级采集器、读取SEALED、补造旧PIT或启用正式能力。

完整审计：[2026-10-12T080740Z-state-change-audit.json](2026-10-12T080740Z-state-change-audit.json)。
'''
with (directory / f'{key}.md').open('a', encoding='utf-8') as stream:
    stream.write(note)
assert not changed and not policy_changed and origin_valid
assert all(v['rows'] == 0 for n, v in added.items() if n != 'capability_journal_origin')
assert result['integrity']['consistent'] and not result['readiness']['system_usable']
assert audit['runtime_unchanged']
print(json.dumps({'audit_passed': True, 'new_tables': len(added), 'new_source_registrations': len(policy_added),
                  'backup_revalidation': backup_check}, ensure_ascii=False))
