"""Complete current test inventory, four isolated OS processes; no agent delegation."""
import argparse,concurrent.futures,hashlib,json,os,subprocess,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];BACK=ROOT/'backend';OUT=ROOT/'.scratch/roll-p0/evidence/19-reconstruction-2026-10-10'
NAME='full-final'
def source_hashes():
    paths=[*BACK.joinpath('src').rglob('*.py'),*BACK.joinpath('tests').rglob('*.py'),*BACK.joinpath('src/roll').rglob('*.json'),BACK/'pyproject.toml']
    return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths) if '__pycache__' not in p.parts}
def run(index,files):
    command=[str(BACK/'.venv/Scripts/python.exe'),'-B','-X','utf8','-m','pytest','-q','-p','no:cacheprovider',*files,'--basetemp='+str(OUT/f'{NAME}-{index}-temp')]
    start=time.time()
    with (OUT/f'{NAME}-{index}.txt').open('w',encoding='utf-8') as log:
        result=subprocess.run(command,cwd=BACK,stdout=log,stderr=subprocess.STDOUT,env={**os.environ,'ROLL_ENV':'test'})
    value={'index':index,'command':command,'files':files,'exit_code':result.returncode,'seconds':time.time()-start}
    print(json.dumps(value),flush=True);return value
def main():
    global NAME
    parser=argparse.ArgumentParser();parser.add_argument('--run-name',default='full-final');NAME=parser.parse_args().run_name
    before=source_hashes();files=sorted(str(p.relative_to(BACK)) for p in BACK.joinpath('tests').rglob('test_*.py'))
    assert len(files)==len(set(files))
    (OUT/(NAME+'-source-start.json')).write_text(json.dumps(before,indent=2),encoding='utf-8')
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        results=list(pool.map(lambda item:run(*item),[(i,files[i::4]) for i in range(4)]))
    after=source_hashes();manifest={'files':files,'results':results,'source_unchanged':before==after,'all_modules_exactly_once':sorted(f for r in results for f in r['files'])==files,'source_hashes':after}
    (OUT/(NAME+'-manifest.json')).write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    assert before==after and all(r['exit_code']==0 for r in results),manifest['results']
if __name__=='__main__':main()
