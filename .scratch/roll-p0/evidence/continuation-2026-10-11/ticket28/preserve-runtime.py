"""Copy stopped, owned METHOD profiles; never inspect private channel config."""
from pathlib import Path
import hashlib, json, shutil, sys
from concurrent.futures import ThreadPoolExecutor

root = Path('D:/dsh-proj/Roll').resolve()
tree = (root/'.scratch/worktrees/ticket28').resolve()
output = tree/'.scratch/roll-p0/evidence/continuation-2026-10-11/ticket28'
correction = len(sys.argv)>1 and sys.argv[1]=='length-correction'
current = len(sys.argv)>1 and sys.argv[1]=='current-composition'
assert len(sys.argv)==1 or (len(sys.argv)==2 and (correction or current))
suffix='current-composition' if current else ('length-correction' if correction else 'final-internal-v2')
prefix='current-runtime' if current else ('length-runtime' if correction else 'runtime')
destination = root/'.roll-data/implementation-evidence/ticket28'/suffix
assert tree.is_relative_to(root) and destination.is_relative_to(root/'.roll-data/implementation-evidence/ticket28')
profiles = ['.test-tmp-notifications-final','.test-tmp-notifications-composition',
    '.test-tmp-notifications-root-baseline','.test-tmp-notifications-current-supplement',
    '.test-tmp-notifications-browser-final','.test-tmp-notifications-browser-final-errors']
if correction: profiles=['.test-tmp-notifications-length-red','.test-tmp-notifications-length-final']
if current: profiles=['.test-tmp-notifications-current-composition']
entries, excluded = [], []
for name in profiles:
    directory = tree/'backend'/name
    assert directory.is_dir() and directory.resolve().is_relative_to(tree/'backend')
    for source in sorted(directory.rglob('*')):
        if source.is_dir(): continue
        assert not source.is_symlink() and source.resolve().is_relative_to(directory.resolve())
        relative = source.relative_to(directory)
        if source.parent.name == 'notification-private' and source.name in {'channel.json','channel.lock'}:
            excluded.append({'source':source.relative_to(root).as_posix(),
                'reason':'Exact private notification configuration/coordination file: not opened, hashed or copied',
                'owner_fixture':'backend/tests/application/test_notifications.py or backend/tests/recovery/test_notification_process.py or frontend/tests/e2e/notifications.spec.ts',
                'identity':'fresh owned METHOD fixture; real channel never configured or called'})
            continue
        assert source.name not in {'auth.json','.env'}, 'Unregistered sensitive file: STOP'
        entries.append((source,destination/name/relative))

destination.mkdir(parents=True,exist_ok=False)
def extended(path): return Path('\\\\?\\'+str(path))
def checksum(path):
    file = extended(path)
    with file.open('rb') as stream: digest = hashlib.file_digest(stream,'sha256').hexdigest()
    return {'bytes':file.stat().st_size,'sha256':digest}
def copy_verified(pair):
    source, target = pair
    extended(target.parent).mkdir(parents=True,exist_ok=True)
    before = checksum(source)
    shutil.copyfile(extended(source),extended(target))
    after, copied = checksum(source), checksum(target)
    assert before == after == copied, str(source)
    return {'source':source.relative_to(root).as_posix(),'destination':target.relative_to(root).as_posix(),**before}
with ThreadPoolExecutor(max_workers=8) as pool: manifest = list(pool.map(copy_verified,entries))
(output/(prefix+'-preservation-manifest.json')).write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
(output/(prefix+'-private-exclusions.json')).write_text(json.dumps(excluded,indent=2)+'\n',encoding='utf-8')
result = {'status':'PASS','source_profile_count':len(profiles),'copied_files':len(manifest),
    'copied_bytes':sum(v['bytes'] for v in manifest),'missing':0,'hash_length_mismatch':0,
    'excluded_private_configuration_files':len(excluded),'private_configuration_opened_hashed_copied':False,
    'sqlite_opened':False,'actual_provider_or_ntfy_calls':0,
    'manifest_sha256':checksum(output/(prefix+'-preservation-manifest.json'))['sha256']}
(output/(prefix+'-preservation-receipt.json')).write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result))
