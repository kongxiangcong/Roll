from pathlib import Path
import hashlib,json,subprocess
root=Path('D:/dsh-proj/Roll');source=root/'.scratch/worktrees/ticket30-producer'
out=root/'.scratch/roll-p0/evidence/continuation-2026-10-11/ticket30-obligations-independent'
def digest(path):
    extended=Path('\\\\?\\'+str(path.resolve()))
    with extended.open('rb') as stream:sha=hashlib.file_digest(stream,'sha256').hexdigest()
    return {'path':str(path),'sha256':sha,'bytes':extended.stat().st_size}
rows=[]
for name in ['r30oi','r30oi-literals']:
    parent=root/'.roll-data'/name
    for path in parent.rglob('*'):
        if path.is_file():
            assert path.is_relative_to(parent) and path.name not in ['auth.json','.env']
            rows.append(digest(path))
(out/'owned-runtime-manifest.json').write_text(json.dumps({'files':len(rows),'bytes':sum(r['bytes'] for r in rows),'rows':rows,'profiles_stopped':True,'root_preserved_sqlite_connections':0},indent=2)+'\n',encoding='utf-8')
baseline=json.loads((source/'.scratch/roll-p0/evidence/30-known-obligations/source-composition26-after.json').read_text())
own={p:digest(source/p) for p in baseline['own']}
for p,row in baseline['own'].items():assert own[p]['sha256']==row['sha256'] and own[p]['bytes']==row['bytes']
protected=json.loads((root/'.scratch/roll-p0/evidence/codex-review-repairs-2026-10-11/source-final.json').read_text())[:15]
for row in protected:
    assert digest(source/row['path'])['sha256']==row['sha256']
proof=json.loads((source/'.scratch/roll-p0/evidence/30-known-obligations/known-notices-proof.json').read_text())
literal_profile=root/'.roll-data/r30oi-literals/test_literals_binding_replay_a0'
audits=[]
for path in (literal_profile/'raw').glob('*.raw'):
    try:value=json.loads(path.read_bytes())
    except (ValueError,UnicodeError):continue
    if isinstance(value,dict) and value.get('known_notice_count')==14 and value.get('basis')=='Independent METHOD known schedule':audits.append(value)
assert len(audits)==1
# Raw archived object inspection only; no SQLite connection to captured source/root materials.
for key in ['notices']:
    assert audits[0][key]==proof[key]
result={'stable_source':'aa234ee8f9fcfb5dd54182c2128744f48d50428e','source_named_7_unchanged':own,'protected15_after':True,'known14_notice_facts_equal_source_proof':True,'root_preserved_sqlite_connections':0,'owned_runtime_files':len(rows),'owned_runtime_bytes':sum(r['bytes'] for r in rows)}
(out/'final-source-and-proof.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k!='source_named_7_unchanged'}))
