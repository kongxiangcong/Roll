from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import hashlib,json,shutil
root=Path('D:/dsh-proj/Roll');source=root/'.scratch/worktrees/ticket30-producer'
evidence=root/'.scratch/roll-p0/evidence/continuation-2026-10-11/ticket30-sse-current-independent'
outside=Path('C:/Users/72449/.codex/visualizations/2026/10/10/01a126a2-cdcc-7d52-b24a-ad47b49bcc56')/'roll-ticket30-sse-independent-runtime'
assert outside.name=='roll-ticket30-sse-independent-runtime'
def extended(path):return Path('\\\\?\\'+str(path))
def digest(path):
    with extended(path).open('rb') as f:sha=hashlib.file_digest(f,'sha256').hexdigest()
    return {'sha256':sha,'bytes':extended(path).stat().st_size}
files=[]
for name in ['r30si','r30si-remaining']:
    base=root/'.roll-data'/name
    for path in extended(base).rglob('*'):
        if not path.is_file():continue
        ordinary=Path(str(path)[4:]);assert ordinary.is_relative_to(base)
        assert ordinary.name.lower() not in ['auth.json','secrets.json','.env']
        files.append(ordinary)
def preserve(path):
    relative=path.relative_to(root/'.roll-data');dest=outside/relative
    expected=digest(path);extended(dest.parent).mkdir(parents=True,exist_ok=True)
    if extended(dest).exists():assert digest(dest)==expected,'Never overwrite earlier runtime'
    else:shutil.copyfile(extended(path),extended(dest))
    assert digest(path)==digest(dest)==expected
    return {'source':str(path),'destination':str(dest),**expected}
with ThreadPoolExecutor(max_workers=8) as pool:rows=list(pool.map(preserve,files))
manifest={'files':len(rows),'bytes':sum(r['bytes'] for r in rows),'mismatches':0,'outside_runtime':str(outside),'rows':rows,'scope':'OWN_STOPPED_METHOD_PROFILES_ONLY_OPAQUE_SQLITE_BYTES_NO_CONNECTION'}
(evidence/'owned-runtime-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
named=json.loads((source/'.scratch/roll-p0/evidence/30-sse-current-suspension/source-composition-after.json').read_text())['own']
for path,row in named.items():
    assert digest(source/path)=={'sha256':row['sha256'],'bytes':row['bytes']}
protected=json.loads((root/'.scratch/roll-p0/evidence/codex-review-repairs-2026-10-11/source-final.json').read_text())[:15]
for row in protected:
    for repo in [root,source]:assert digest(repo/row['path'])=={'sha256':row['sha256'],'bytes':row['bytes']}
js=source/'backend/src/roll/market/reference/sse-history/search_tradeTip_2021.js'
# Exact reference path is defined by its source manifest, not guessed filename.
mapping=json.loads((source/'backend/src/roll/market/reference/sse-history/sources.json').read_text())
fixed=[]
for item in mapping['sources']:
    if item['role'] in ['suspension','suspension_query_js']:
        p=source/'backend/src/roll/market/reference/sse-history'/item['path']
        assert digest(p)=={'sha256':item['sha256'],'bytes':item['bytes']};fixed.append({'role':item['role'],**digest(p)})
assert len(fixed)==2
proof={'stable_source':'05a17176ed5e55894076c69345bdb97dff175fd2','named_source_unchanged':named,'root_source_protected15_unchanged':True,'fixed_source_originals':fixed,'profiles_files':manifest['files'],'profiles_bytes':manifest['bytes'],'profiles_destination':str(outside),'sqlite_connections':0,'new_real_http_provider_fit_forecast_grant_calls':0}
(evidence/'final-source-and-preservation.json').write_text(json.dumps(proof,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in proof.items() if k!='named_source_unchanged'}))
