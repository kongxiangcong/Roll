import json,urllib.request
from pathlib import Path
out=Path(__file__).parent
with urllib.request.urlopen('https://pypi.org/pypi/arch/8.0.0/json',timeout=20) as response:data=json.load(response)
info=data['info']
result={k:info.get(k) for k in ('name','version','license','license_expression','requires_python','requires_dist')}
result['wheels']=[{'filename':f['filename'],'sha256':f['digests']['sha256'],'url':f['url']} for f in data['urls'] if 'cp313-cp313-win_amd64' in f['filename']]
(out/'package-metadata.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps({k:result[k] for k in ('name','version','license','license_expression')}))
