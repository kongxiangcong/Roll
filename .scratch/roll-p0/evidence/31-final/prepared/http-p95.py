"""Preparation helper: explicitly released owned live test API only; no startup."""
import argparse
import json
import math
import os
import platform
import re
import sqlite3
from pathlib import Path
import subprocess
import sys
import time
from urllib.parse import urlparse

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute',action='store_true')
    parser.add_argument('--accepted-fix-oid')
    parser.add_argument('--owned-server-receipt',type=Path)
    parser.add_argument('--stage',choices=['home','confirmation'],required=True)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    if not args.execute:
        print('PREPARED_ONLY: no HTTP request, test or startup');return
    tree=Path(__file__).resolve().parents[5]
    assert tree==Path('D:/dsh-proj/Roll/.scratch/worktrees/ticket31-final')
    assert re.fullmatch('[0-9a-f]{40}',args.accepted_fix_oid or '')
    subprocess.run(['git','-C',str(tree),'merge-base','--is-ancestor',args.accepted_fix_oid,'HEAD'],check=True)
    assert args.owned_server_receipt and args.output
    assert args.output.resolve().is_relative_to(tree/'.scratch/roll-p0/evidence/31-final/runs')
    assert not args.output.exists(), 'Preserve prior measurement; use a new output'
    receipt=json.loads(args.owned_server_receipt.read_text(encoding='utf-8'))
    assert receipt['owner']=='final31' and receipt['accepted_fix_oid']==args.accepted_fix_oid
    assert receipt['source_root']==str(tree) and receipt['environment']=='test'
    assert receipt['runtime_is_new_owned_copy'] and receipt['original_sqlite_connections']==0
    assert Path(receipt['runtime']).resolve().is_relative_to(tree/'.roll-data')
    assert receipt['process_pid']>0 and receipt['process_creation_time'] and receipt['source_oid']
    assert receipt['source_oid']==subprocess.check_output(['git','-C',str(tree),'rev-parse','HEAD'],text=True).strip()
    url=receipt['api_url'];parsed=urlparse(url)
    assert parsed.scheme=='http' and parsed.hostname=='127.0.0.1' and parsed.port
    import httpx
    sys.path.insert(0,str(tree/'scripts'))
    from account_confirmation_performance import measure_confirmations
    with httpx.Client(base_url=url,timeout=10,trust_env=False) as client:
        assert client.get('/api/health').json()['environment']=='test'
        if args.stage=='confirmation':
            result=measure_confirmations(client,samples=100,warmup=10)
        else:
            times=[]
            for index in range(110):
                start=time.perf_counter()
                response=client.get('/api/today');response.raise_for_status();response.json()
                elapsed=(time.perf_counter()-start)*1000
                if index>=10:times.append(elapsed)
            result={'stage':'cached /api/today HTTP plus decode','samples':100,'warmup':10,
                    'samples_ms':times,'p95_ms':sorted(times)[math.ceil(.95*len(times))-1]}
    result.update(accepted_fix_oid=args.accepted_fix_oid,server_receipt=receipt,
                  device={'platform':platform.platform(),'processor':platform.processor(),
                          'python':platform.python_version(),'sqlite':sqlite3.sqlite_version},
                  network_scope='LOCAL_LOOPBACK_ONLY_NO_PROVIDER',fit_calls=0,forecast_calls=0)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    assert result['p95_ms']<=2000,result['p95_ms']

if __name__=='__main__':main()
