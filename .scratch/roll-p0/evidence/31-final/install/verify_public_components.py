"""Verify only explicit public CNEquity manifest entries, never import adapters."""
import hashlib
import importlib.metadata as metadata
import json
from pathlib import Path

output=Path(__file__).resolve().parent
runtime=Path('D:/dsh-proj/Roll/.roll-data/cnequity-runtime')
expected_commit='c118038ea82b5bb78783c0c17a1d9251b36de71d'

def read_public(relative):
    path=runtime/relative
    assert path.resolve().is_relative_to(runtime.resolve())
    assert path.is_file() and not path.is_symlink()
    return path.read_bytes()

manifest_raw=read_public('source-manifest.json')
manifest=json.loads(manifest_raw)
record=json.loads(read_public('runtime.json'))
assert manifest['commit']==record['commit']==expected_commit
assert hashlib.sha256(manifest_raw).hexdigest()==record['source_manifest_sha256']
assert record['profile']=='ROLL_BOUNDED_ADAPTERS_ONLY' and record['version']=='0.16.0'
rows=[]
for item in manifest['files']:
    relative=item['path']
    assert relative.startswith(('src/','contracts/v')) or relative in {'LICENSE','NOTICE','pyproject.toml','README.pypi.md','sources/SOURCES.yml'}
    raw=read_public('pinned-source/'+relative)
    actual={'path':relative,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),
            'git_blob':hashlib.sha1(f'blob {len(raw)}\0'.encode()+raw).hexdigest()}
    assert all(actual[k]==item[k] for k in ['bytes','sha256','git_blob']),relative
    rows.append(actual)
assert len(rows)==410
site=runtime/'.venv/Lib/site-packages'
distributions={d.metadata['Name'].lower():d for d in metadata.distributions(path=[str(site)])}
dist=distributions['cnequity']
assert dist.version=='0.16.0'
package=[]
for relative,expected in record['package_hashes'].items():
    assert relative.endswith('.py') and not relative.startswith('/') and '..' not in Path(relative).parts
    raw=read_public('.venv/Lib/site-packages/cnequity/'+relative)
    actual=hashlib.sha256(raw).hexdigest()
    assert actual==expected,relative
    package.append({'path':relative,'bytes':len(raw),'sha256':actual})
deps={name:distribution.version for name,distribution in distributions.items()}
for name,version in record['dependencies'].items():
    assert deps[name.lower()]==version,(name,version)
license_paths=['pinned-source/LICENSE','pinned-source/NOTICE',
    'pinned-source/src/cnequity/adapters/tdx_protocol/_wire/LICENSE.tdxpy']
for item in dist.files or []:
    if '.dist-info/licenses/' in str(item).replace('\\','/'):
        license_paths.append('.venv/Lib/site-packages/'+str(item).replace('\\','/'))
licenses=[]
for relative in sorted(set(license_paths)):
    raw=read_public(relative)
    licenses.append({'path':relative,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()})
result={'classification':'CURRENT_INSTALLED_PUBLIC_COMPONENT_STATIC_VERIFICATION_NOT_BEHAVIOR_ACCEPTANCE',
    'runtime_root':str(runtime),'commit':expected_commit,'version':dist.version,'profile':record['profile'],
    'official_source_files':rows,'installed_package_files':package,'dependencies':record['dependencies'],
    'licenses':licenses,'source_manifest_sha256':record['source_manifest_sha256'],
    'official_source_file_count':len(rows),'installed_package_file_count':len(package),'mismatches':0,
    'adapter_imports':0,'source_requests':0,'provider_calls':0,'database_connections':0,
    'credential_reads':0,'credential_hashes':0,'credential_copies':0,'test_runs':0,
    'limitations':['Public local installation matches its prior pinned manifest; no new upstream fetch or adapter/data behavior executed.',
                   'Software license is separate from upstream market data or redistribution rights.']}
(output/'public-component-verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:result[k] for k in ['commit','version','official_source_file_count','installed_package_file_count','mismatches','database_connections','provider_calls']}))
