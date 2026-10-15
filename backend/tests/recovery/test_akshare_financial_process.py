"""The real pinned SDK runs against fixed transport entities; no HTTP is sent."""
import json
import os
from pathlib import Path
import subprocess
import time
import pytest

ROOT=Path(__file__).resolve().parents[3]
CAPTURE=ROOT/'.scratch/roll-capability-expansion/evidence/09-financial/actual-source'
PYTHON=ROOT/'.scratch/rce-runtime/akshare/Scripts/python.exe'


@pytest.mark.parametrize('http_status',[200,503])
def test_pinned_sdk_raw_first_transport_is_bounded_and_keeps_failures(tmp_path,http_status):
    if not PYTHON.exists():pytest.skip('Pinned isolated AKShare runtime is not configured on this host')
    manifest=json.loads((CAPTURE/'capture.json').read_text())
    fixture={c['role']:{'status_code':http_status if c['role']=='lrbAjaxNew' else 200,
        'body':(CAPTURE/c['raw_file']).read_bytes().decode('utf-8')} for c in manifest['captures']}
    path=tmp_path/'fixture.json';path.write_text(json.dumps(fixture),encoding='utf-8')
    output=tmp_path/'capture'
    env={k:v for k,v in os.environ.items() if k.upper() in {'SYSTEMROOT','WINDIR','PATH','TEMP','TMP','USERPROFILE','LOCALAPPDATA','APPDATA'}}
    env['ROLL_ENV']='test'
    command={'instrument':'SSE:600362','output_directory':str(output),'deadline_at':time.time()+18,'fixture':str(path)}
    completed=subprocess.run([str(PYTHON),'-B',str(ROOT/'backend/src/roll/market/akshare_financial_process.py')],
        input=json.dumps(command),text=True,capture_output=True,env=env,timeout=20)
    assert completed.returncode==0,completed.stderr[-500:]
    result=json.loads((output/'capture.json').read_text())
    assert result['evidence_kind']=='METHOD_CASE'
    assert len(result['captures'])==3
    assert (output/'03.raw').read_bytes()==(CAPTURE/'03.raw').read_bytes()
    assert result['captures'][2]['status_code']==http_status
    assert result['date_selection']['reported_index_rows']==103
    assert result['date_selection']['upstream_original_is_unchanged'] is True
    assert result['status']==('CAPTURED' if http_status==200 else 'FAILED')
    if http_status==200:assert result['sdk_result']['rows']==5
    else:assert result['errors']==['AKSHARE_FINANCIAL_HTTP_503']


def test_hard_kill_keeps_the_active_entity_prefix(tmp_path):
    if not PYTHON.exists():pytest.skip('Pinned isolated AKShare runtime is not configured on this host')
    manifest=json.loads((CAPTURE/'capture.json').read_text())
    fixture={c['role']:{'body':(CAPTURE/c['raw_file']).read_bytes().decode()} for c in manifest['captures']}
    fixture['lrbAjaxNew']['pause_after_prefix_seconds']=30
    path=tmp_path/'fixture.json';path.write_text(json.dumps(fixture),encoding='utf-8')
    output=tmp_path/'capture'
    env={k:v for k,v in os.environ.items() if k.upper() in {'SYSTEMROOT','WINDIR','PATH','TEMP','TMP','USERPROFILE','LOCALAPPDATA','APPDATA'}}
    env['ROLL_ENV']='test'
    process=subprocess.Popen([str(PYTHON),'-B',str(ROOT/'backend/src/roll/market/akshare_financial_process.py')],stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,env=env)
    command={'instrument':'SSE:600362','output_directory':str(output),'deadline_at':time.time()+18,'fixture':str(path)}
    try:
        process.stdin.write(json.dumps(command).encode());process.stdin.close()
        until=time.monotonic()+10
        while time.monotonic()<until:
            prefix=output/'03.raw'
            if prefix.exists() and prefix.stat().st_size>=8192:
                # Avoid Windows read handles racing the child's journal rename.
                time.sleep(.1)
                break
            time.sleep(.05)
        else:pytest.fail('Child did not persist the active stream prefix before its deadline')
        process.kill();process.wait(timeout=3)
        saved=json.loads((output/'capture.json').read_text())['captures'][2]
        assert not saved['original_complete']
        assert (output/'03.raw').read_bytes()==(CAPTURE/'03.raw').read_bytes()[:8192]
        import hashlib
        assert saved['sha256']==hashlib.sha256((output/'03.raw').read_bytes()).hexdigest()
    finally:
        if process.poll() is None:process.kill();process.wait(timeout=3)
