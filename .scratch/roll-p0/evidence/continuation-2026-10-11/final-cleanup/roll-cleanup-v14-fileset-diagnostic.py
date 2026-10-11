import os, json
from pathlib import Path
from collections import Counter
v = Path(__file__).parent
p = json.loads((v/'roll-cleanup-batch-v6-preflight.json').read_text(encoding='utf-8-sig'))
rows = p['source_inventory']
results = []
for t in p['trees']:
    base = t['path']
    old = [r['path'] for r in rows if r['path'].lower().startswith(base.lower()+'\\')]
    now = []
    queue = [base]
    while queue:
        with os.scandir(queue.pop()) as entries:
            for e in entries:
                st = e.stat(follow_symlinks=False)
                if st.st_file_attributes & 1024:
                    continue
                if e.is_dir(follow_symlinks=False):
                    queue.append(e.path)
                elif e.name != '.git':
                    now.append(os.path.normpath(e.path))
    a, b = Counter(x.lower() for x in old), Counter(x.lower() for x in now)
    results.append(dict(tree=base, before_count=len(old), now_count=len(now), removed=list((a-b).elements()), added=list((b-a).elements()), duplicate_before=[k for k,c in a.items() if c>1]))
out=dict(status='METADATA_ONLY_DIAGNOSTIC', source_file_bodies_read=0, private_bodies_read=0, hashes=0, sqlite_connections=0, deleted=0, trees=results)
(v/'roll-cleanup-v14-fileset-diagnostic.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(results,ensure_ascii=False))
