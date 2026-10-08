import hashlib,json,re,subprocess
from pathlib import Path
root=Path('D:/dsh-proj/Roll').resolve()
secrets=[]
for line in (root/'.env').read_text(encoding='utf-8-sig').splitlines():
    line=line.strip().removeprefix('export ').lstrip()
    name,sep,value=line.partition('=')
    if sep and name.strip() in {'DEEPSEEK_API_KEY','FUYAO_API_KEY'}:
        value=value.strip()
        value=value[1:value.find(value[0],1)] if value.startswith(('"',"'")) else re.split(r'\s+#',value,maxsplit=1)[0].rstrip()
        if value:secrets.append(value.encode())
assert len(secrets)==2
auth=json.loads(Path('C:/Users/72449/.codex/auth.json').read_text(encoding='utf-8'))
auth_tokens=[auth['tokens'][name].encode() for name in ['access_token','id_token','refresh_token'] if auth.get('tokens',{}).get(name)]
assert len(auth_tokens)==3
secrets+=auth_tokens
overlap=max(map(len,secrets))-1
def check_bytes(content):
    assert not any(value in content for value in secrets),'CREDENTIAL_MATCH'
def digest(path):
    checksum=hashlib.sha256(); tail=b''; size=0
    with path.open('rb') as stream:
        while chunk:=stream.read(2*1024*1024):
            size+=len(chunk); checksum.update(chunk)
            combined=tail+chunk; check_bytes(combined); tail=combined[-overlap:]
    return size,checksum.hexdigest()
paths=subprocess.check_output(['git','diff','--name-only','aad2645','6ad9928c71ebc0b3ffd59fcf8c9f25fdfc4c9461'],cwd=root,text=True).splitlines()
for path in paths:check_bytes(subprocess.check_output(['git','show','6ad9928c71ebc0b3ffd59fcf8c9f25fdfc4c9461:'+path],cwd=root))

assert subprocess.run(['git','check-ignore','--quiet','.env'],cwd=root).returncode==0
report={'changed_git_blobs_scanned':len(paths),'credential_matches':0,'env_keys_scanned':2,'authorized_auth_tokens_scanned':3,'root_env_ignored':True,'credential_files_modified_or_copied':0}
(root/'.scratch/roll-p0/evidence/continuation-2026-10-08/merge-review-fixes-secret-scan.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(report))
