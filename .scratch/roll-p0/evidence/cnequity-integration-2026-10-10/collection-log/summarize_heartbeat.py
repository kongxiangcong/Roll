"""Summarize persisted collection output and compare the before/after inventories."""
import json
from pathlib import Path
import sys
import sqlite3

directory = Path(__file__).parent
key = sys.argv[1]
def read(suffix):
    return json.loads((directory/f'{key}-{suffix}.json').read_text(encoding='utf-8-sig'))
before, after, result = read('before'), read('after'), read('result')
old_by_source = {h['id']: h for h in before['sources'] if h.get('id')}
# The first inventory omitted health-table keys. Recover CNEquity identity
# from the retained old run, never infer identity from equal failure counts.
root = directory.parents[4]
with sqlite3.connect(f'file:{(root/".roll-data/pit/roll.sqlite3").as_posix()}?mode=ro', uri=True) as db:
    for h in before['sources']:
        if not h.get('id') and h.get('state') == 'FAILED':
            row = db.execute('SELECT value FROM retrieval_runs WHERE id=?', (h['last_run_id'],)).fetchone()
            source_id = json.loads(row[0]).get('source_policy', {}).get('id') if row else None
            if source_id:
                old_by_source[source_id] = h
new_failures = [s['id'] for s in result['sources'] if s['health']['state'] == 'FAILED'
                and old_by_source.get(s['id'], {}).get('state') != 'FAILED']
unchanged = before['protected'] == after['protected']
policies_unchanged = before['policies'] == after['policies']
runtime_unchanged = before['runtime_manifest_sha256'] == after['runtime_manifest_sha256']
integrity, backup = result['integrity'], result.get('backup') or {}
ok = integrity['consistent'] and integrity['sqlite'] == 'ok' and backup.get('status') == 'COMPLETE'
summary = {'heartbeat_id': key, 'completed_at': integrity['checked_at'],
           'added_fact_versions': after['facts']-before['facts'], 'added_batches': after['batches']-before['batches'],
           'integrity': integrity, 'backup_id': backup.get('backup_id'), 'backup_status': backup.get('status'),
           'readiness': result['readiness'], 'protected_state_unchanged': unchanged,
           'source_policies_unchanged': policies_unchanged, 'runtime_unchanged': runtime_unchanged,
           'new_failed_sources': new_failures,
           'sources': [{'id': s['id'], 'health': s['health']} for s in result['sources']],
           'notification_required': bool(new_failures) or not (ok and unchanged and policies_unchanged and runtime_unchanged)}
(directory/f'{key}-summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
text = f'''# roll-pit {key}

新增事实版本 {summary['added_fact_versions']}；新增批次 {summary['added_batches']}。
SQLite {integrity['sqlite']}；归档 {integrity['archives_checked']}；事实 {integrity['facts_checked']}；归档／关联错误 {len(integrity['archive_failures'])}/{len(integrity['reference_failures'])}；离线检查联网0。
PROSPECTIVE_COLLECTION备份 {summary['backup_status']}：{summary['backup_id']}。
受保护账户／研究状态不变 {unchanged}；来源策略不变 {policies_unchanged}；运行时不变 {runtime_unchanged}。
前向交易日 {result['readiness']['real_recorded_sessions']}；回看日期 {result['readiness']['real_context_sessions']}；状态 COLLECTING／NOT_GRANTED，系统尚不可用。
新失败来源 {new_failures}；需要通知 {summary['notification_required']}。已知缺口继续保留；未训练、升级、补旧PIT或读取SEALED。

完整输出：[{key}-result.json]({key}-result.json)；详情：[{key}-summary.json]({key}-summary.json)。
'''
(directory/f'{key}.md').write_text(text, encoding='utf-8')
print(json.dumps({k: summary[k] for k in ['added_fact_versions', 'added_batches', 'backup_status', 'new_failed_sources',
                                        'protected_state_unchanged', 'notification_required']}, ensure_ascii=False))
assert ok and unchanged and policies_unchanged and runtime_unchanged
