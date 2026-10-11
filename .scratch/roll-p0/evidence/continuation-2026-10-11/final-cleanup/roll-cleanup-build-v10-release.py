import json, hashlib
from pathlib import Path
v=Path(__file__).parent
def read(name): return json.loads((v/name).read_text(encoding='utf-8-sig'))
r=read('roll-cleanup-release-v9c-exact63.json')
c=read('roll-cleanup-v9c-coverage-only.json')['uncovered']
extra=read('roll-cleanup-extra-untracked-manifest.json')
receipt=read('roll-cleanup-extra-untracked-receipt.json')
p=read('roll-cleanup-v9c-private-provenance.json')
assert receipt['count']==3687 and receipt['source_and_target_sha_mismatches']==0
assert p['summary']['proven_public_method_writer_and_case']==113 and p['summary']['unknown']==2
manifest=v/'roll-cleanup-extra-untracked-manifest.json'
sha=hashlib.sha256(manifest.read_bytes()).hexdigest()
covered=[]
for tree in r['trees']:
    if tree['name'] in extra:
        rows=extra[tree['name']]
        tree.setdefault('additional_manifests',[]).append(dict(path=str(manifest),field=tree['name'],count=len(rows),bytes=sum(x['bytes'] for x in rows),source_base=tree['path'],destination_base='D:\\dsh-proj\\Roll',manifest_bytes=manifest.stat().st_size,manifest_sha256=sha))
        covered.extend(x['source'].lower() for x in rows)
    for row in p['rows']:
        if row['tree']!=tree['name'] or row['status']=='UNKNOWN': continue
        assert row['status']=='PROVEN_PUBLIC_METHOD_WRITER_AND_CASE'
        assert not row['contents_read'] and not row['hashed'] and not row['copied']
        tree.setdefault('exact_exclusions',[]).append(dict(path=row['source'],kind=row['kind'],source_provenance=row['source_provenance'],accepted_receipt=row['accepted_receipt']))
        covered.append(row['source'].lower())
unknown=[x for x in p['rows'] if x['status']=='UNKNOWN']
r['exact_private_retention_moves']=[]
for row in unknown:
    name=Path(row['source']).name
    assert name in {'channel.json','channel.lock'}
    dest=Path('D:/dsh-proj/Roll/.roll-data/implementation-evidence/final-cleanup-private-retained-20261012/ticket28/browser-green2/notification-private')/name
    r['exact_private_retention_moves'].append(dict(source=row['source'],destination=str(dest),kind='PRIVATE_METADATA_RETENTION_MOVE',classification='UNKNOWN',bytes_from_prior_metadata=row['bytes_from_prior_metadata'],source_provenance='Exact previously inventoried private endpoint; origin unresolved; retain by same-volume rename without body read/hash/copy',accepted_receipt=row['accepted_receipt']))
    covered.append(row['source'].lower())
assert len(covered)==3802 and len(set(covered))==3802
assert set(covered)=={x['source'].lower() for x in c}
r['coordinator_release_id']='roll-root-final-cleanup-20261012-v10-exact3802'
r['residual_closure']=dict(total=3802,public_preserved=3687,proven_method_metadata_exclusions=113,unknown_private_retained=2,omitted=0,duplicates=0,private_contents_read=0)
out=v/'roll-cleanup-release-v10-exact3802.json'
assert not out.exists()
out.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(r['residual_closure']))
