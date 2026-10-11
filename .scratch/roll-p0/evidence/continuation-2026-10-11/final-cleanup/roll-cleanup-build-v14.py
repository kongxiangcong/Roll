import json,hashlib
from pathlib import Path
v=Path(__file__).parent
def rd(name):return json.loads((v/name).read_text(encoding='utf-8-sig'))
release=rd('roll-cleanup-release-v13-exact3802.json');versions=rd('roll-cleanup-cache-version-dispositions.json')
assert len(versions['exact_historical_source_versions'])==len(versions['current_rows'])==1
release['exact_historical_source_versions']=versions['exact_historical_source_versions']
manifest=v/'roll-cleanup-cache-version-dispositions.json'
tree=next(x for x in release['trees'] if x['name']=='ticket30-producer')
tree['additional_manifests'].append(dict(path=str(manifest),field='current_rows',count=1,bytes=530,source_base=tree['path'],destination_base='D:\\dsh-proj\\Roll',manifest_bytes=manifest.stat().st_size,manifest_sha256=hashlib.sha256(manifest.read_bytes()).hexdigest(),special=None,root_mirror=None,self_copy=None))
release['coordinator_release_id']='roll-root-final-cleanup-20261012-v14-exact3802-cache1-bounded4'
(v/'roll-cleanup-release-v14-exact3802.json').write_text(json.dumps(release,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
source=(v/'roll-cleanup-batch-v13-root-exact-batch.ps1').read_text(encoding='utf-8-sig')
old='[pscustomobject]@{source=$s;destination=$dest;bytes=[long]$v.bytes;sha256=$v.sha256;manifest=$path}'
new='''$row=[pscustomobject]@{source=$s;destination=$dest;bytes=[long]$v.bytes;sha256=$v.sha256;manifest=$path}
   $versions=@($Release.exact_historical_source_versions|Where-Object {$_.source -eq $s -and $_.manifest -eq $path -and $_.historical_destination -eq $dest})
   if($versions.Count -gt 1){throw 'Duplicate exact historical cache binding'}
   if($versions.Count -eq 1){
    $z=$versions[0]
    if($z.kind -ne 'PUBLIC_PYTEST_CACHE_CURRENT_VERSION' -or $z.tree -ne $t.name -or $s -ne (Join-Path $Root '.scratch/worktrees/ticket30-producer/.pytest_cache/v/cache/nodeids') -or $z.historical_bytes -ne $v.bytes -or $z.historical_sha256 -ne $v.sha256 -or -not(Test-Path -LiteralPath $z.source_owner_receipt)){throw 'Exact public cache version provenance differs'}
    $null=In $z.current_destination (Join-Path $Root '.roll-data/implementation-evidence/final-cleanup-cache-current-20261012')
    $row|Add-Member -NotePropertyName source_expected_bytes -NotePropertyValue ([long]$z.current_bytes)
    $row|Add-Member -NotePropertyName source_expected_sha256 -NotePropertyValue $z.current_sha256
   }
   $row'''
assert source.count(old)==1
source=source.replace(old,new)
oldadd='AddExpected $expected $r.source $r.bytes $r.sha256;AddExpected $expected $r.destination $r.bytes $r.sha256'
newadd="AddExpected $expected $r.source (GetProp $r 'source_expected_bytes' $r.bytes) (GetProp $r 'source_expected_sha256' $r.sha256);AddExpected $expected $r.destination $r.bytes $r.sha256"
assert source.count(oldadd)==1
source=source.replace(oldadd,newadd)
(v/'roll-cleanup-batch-v14-root-exact-batch.ps1').write_text('# V14 exact one public cache current/historical split; original manifests and old saved bytes retained.\n'+source,encoding='utf-8')
wrapper=(v/'roll-cleanup-run-v13-final-phase.ps1').read_text(encoding='utf-8-sig').replace('roll-cleanup-release-v13-exact3802.json','roll-cleanup-release-v14-exact3802.json')
(v/'roll-cleanup-run-v14-final-phase.ps1').write_text(wrapper,encoding='utf-8')
print('V14 exact cache1 normalized; no source or old target rewritten')
