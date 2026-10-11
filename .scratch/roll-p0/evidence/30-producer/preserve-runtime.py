"""Copy only this implementer's explicit METHOD/test and public source-assessment files."""
import hashlib
import json
from pathlib import Path
import shutil
import sys

repo=Path(__file__).resolve().parents[4]
root=Path('D:/dsh-proj/Roll').resolve()
composition=sys.argv[1:]==['composition']
assert not sys.argv[1:] or composition
target=(root/('.roll-data/implementation-evidence/continuation-ticket30-producer'+('-composition' if composition else ''))).resolve()
assert target.is_relative_to(root/'.roll-data/implementation-evidence')
assert not target.is_symlink() and not target.is_junction()

def native(path):
    # CopyFile2 needs the extended namespace for these deliberately long fixture paths.
    value=str(path.absolute())
    return value if value.startswith('\\\\?\\') else '\\\\?\\'+value

def ordinary(path):
    return Path(str(path).removeprefix('\\\\?\\'))
sources=[(p,'worktree/'+p.name) for p in sorted((repo/'.scratch').glob('t30p-*')) if p.is_dir()]
sources += [(repo/'.scratch/roll-p0/evidence/30-producer/runtime','source-assessment'),
    (root/'.scratch/t30p-red1','root-owned-test/t30p-red1'),
    (root/'.scratch/t30p-green1','root-owned-test/t30p-green1')]
if composition:sources=[(repo/'.scratch/t30p-composition-1','worktree/t30p-composition-1')]
manifest=[]
for directory,label in sources:
    assert directory.resolve().is_relative_to(repo) or directory.resolve() in {
        (root/'.scratch/t30p-red1').resolve(),(root/'.scratch/t30p-green1').resolve()}
    if not directory.exists():continue
    for extended in sorted(Path(native(directory)).rglob('*')):
        if extended.is_symlink() or extended.is_junction():raise RuntimeError('REPARSE_POINT_NOT_COPIED')
        if not extended.is_file():continue
        path=ordinary(extended)
        body=extended.read_bytes();sha=hashlib.sha256(body).hexdigest()
        relative=Path(label)/path.relative_to(directory)
        destination=target/relative
        manifest.append({'source':str(path),'destination':str(destination),'sha256':sha,'bytes':len(body)})

expected={Path(p['destination']):p for p in manifest}
# The preceding invocation created this exact target and stopped before any receipt.
# Resume only matching owned copies; never overwrite unknown or mismatching content.
resumed=0
if target.exists():
    for extended in Path(native(target)).rglob('*'):
        if extended.is_symlink() or extended.is_junction():raise RuntimeError('DESTINATION_REPARSE_POINT')
        if not extended.is_file():continue
        existing=ordinary(extended)
        item=expected.get(existing)
        if item is None:raise RuntimeError('UNEXPECTED_DESTINATION_FILE')
        body=extended.read_bytes()
        if len(body)!=item['bytes'] or hashlib.sha256(body).hexdigest()!=item['sha256']:
            raise RuntimeError('EXISTING_DESTINATION_MISMATCH')
        resumed+=1

for item in manifest:
        path=Path(item['source']);destination=Path(item['destination'])
        Path(native(destination.parent)).mkdir(parents=True,exist_ok=True)
        if not Path(native(destination)).exists():shutil.copy2(native(path),native(destination))
        copied=Path(native(destination)).read_bytes()
        sha=item['sha256']
        if len(copied)!=item['bytes'] or hashlib.sha256(copied).hexdigest()!=sha:
            raise RuntimeError('PRESERVATION_MISMATCH')
        # A live writer must not be mistaken for a stopped accepted runtime.
        source=Path(native(path)).read_bytes()
        if len(source)!=item['bytes'] or hashlib.sha256(source).hexdigest()!=sha:
            raise RuntimeError('SOURCE_CHANGED_DURING_PRESERVATION')
receipt={'scope':'OWNED_METHOD_TESTS_AND_ANONYMOUS_PUBLIC_SOURCE_ASSESSMENT_ONLY',
    'files':len(manifest),'bytes':sum(p['bytes'] for p in manifest),'sha_or_length_mismatches':0,
    'copy_attempts':1 if composition else 3,'previous_failures':[] if composition else [
        'COPYFILE2_LONG_PATH_FAILURE_NO_SUCCESS_RECEIPT','DESTINATION_NORMAL_PATH_READ_FAILURE_NO_SUCCESS_RECEIPT'],
    'resumed_preexisting_verified_files':resumed,
    'target':str(target),'source_directories':[str(p[0]) for p in sources],
    'original19_sqlite_sha256':hashlib.sha256((root/'.roll-data/reconstructed19-v1/roll.sqlite3').read_bytes()).hexdigest()}
assert receipt['original19_sqlite_sha256']=='ec46257c4420f69c245791778c49079355700615cc3ed7b94d8027bd4dcf66c4'
evidence=Path(__file__).parent
prefix='composition-' if composition else 'runtime-'
(evidence/(prefix+'preservation-manifest.json')).write_text(json.dumps(manifest,indent=2),encoding='utf-8')
(evidence/(prefix+'preservation-receipt.json')).write_text(json.dumps(receipt,indent=2),encoding='utf-8')
print(json.dumps(receipt))
