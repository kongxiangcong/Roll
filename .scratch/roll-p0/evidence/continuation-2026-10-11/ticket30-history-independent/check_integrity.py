from pathlib import Path
import os,json,hashlib,subprocess,concurrent.futures
source=Path.cwd().resolve();root=Path('D:/dsh-proj/Roll')
out=root/'.scratch/roll-p0/evidence/continuation-2026-10-11/ticket30-history-independent'
ev=source/'.scratch/roll-p0/evidence/30-producer-followup'
def long(path):
    value=str(Path(path).resolve());return Path('\\\\?\\'+value) if os.name=='nt' else Path(value)
def check(path,sha,size):
    p=Path(path)
    with long(p).open('rb') as stream:actual=hashlib.file_digest(stream,'sha256').hexdigest()
    length=long(p).stat().st_size
    assert actual==sha and length==size,str(p)
    return {'path':str(p),'sha256':actual,'bytes':length,'matches':True}
files=[]
allowed_targets=[root/'.roll-data/implementation-evidence/continuation-ticket30-producer-followup',root/'.roll-data/implementation-evidence/continuation-ticket30-producer-followup-composition']
for name in ['runtime-preservation-manifest.json','composition-preservation-manifest.json']:
    files+=json.loads((ev/name).read_text(encoding='utf-8'))
assert len(files)==2570
jobs=[]
for item in files:
    s,d=Path(item['source']).resolve(),Path(item['destination']).resolve()
    assert s.is_relative_to(source/'.scratch') and any(d.is_relative_to(t) for t in allowed_targets)
    assert not any(word in s.name.lower() for word in ['auth.json','.env','credential','token'])
    jobs.extend([(s,item['sha256'],item['bytes']),(d,item['sha256'],item['bytes'])])
with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
    hashes=list(pool.map(lambda row:check(*row),jobs))
protected=json.loads((root/'.scratch/roll-p0/evidence/codex-review-repairs-2026-10-11/source-final.json').read_text(encoding='utf-8'))[:15]
guards=[]
for item in protected:
    for repo in [source,root]:guards.append(check(repo/item['path'],item['sha256'],item['bytes']))
original19=check(root/'.roll-data/reconstructed19-v1/roll.sqlite3','ec46257c4420f69c245791778c49079355700615cc3ed7b94d8027bd4dcf66c4',165814272)
ref=source/'backend/src/roll/market/reference/sse-history'
manifest=json.loads((ref/'sources.json').read_text(encoding='utf-8'))
originals=[]
for item in manifest['sources']:
    disk=check(ref/item['path'],item['sha256'],item['bytes'])
    git_path=(ref/item['path']).relative_to(source).as_posix()
    blob=subprocess.check_output(['git','show','HEAD:'+git_path])
    assert len(blob)==item['bytes'] and hashlib.sha256(blob).hexdigest()==item['sha256']
    originals.append({**disk,'git_blob_matches':True,'role':item['role']})
assert len(originals)==6 and sum(i['bytes'] for i in originals)==360501
result={'source_oid':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'new_archive_files':2570,'new_archive_bytes':sum(i['bytes'] for i in files),'source_and_destination_checks':len(hashes),'mismatches':0,'only_new_preservation_targets':list(map(str,allowed_targets)),'old13989_preservation_accessed':False,'root19_other_raw_accessed':False,'original19_checksum_only':original19,'protected_15_source_and_root':guards,'originals_disk_and_git':originals,'files':hashes,'composition_cases':sorted(set(Path(i['source']).relative_to(source/'.scratch/t30h-composition').parts[0] for i in files if Path(i['source']).is_relative_to(source/'.scratch/t30h-composition')))}
(out/'integrity.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k in ['source_oid','new_archive_files','new_archive_bytes','source_and_destination_checks','mismatches','composition_cases']}))
