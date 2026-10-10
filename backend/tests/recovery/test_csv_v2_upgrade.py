"""Real 04 v2 service creates a paid-rights draft; 05 confirms after upgrade."""
import csv
import io
import subprocess
from pathlib import Path
from test_account_process import Server
from test_fill_process import BASELINE


def test_existing_v2_paid_rights_archive_and_draft_keep_meaning_after_v3_upgrade(tmp_path):
    repo=Path(__file__).resolve().parents[3]
    source=tmp_path/'v2-source'
    paths=subprocess.run(['git','ls-tree','-r','--name-only','ada6cfb','backend/src/roll'],cwd=repo,capture_output=True,check=True).stdout.decode().splitlines()
    for name in paths:
        data=subprocess.run(['git','show',f'ada6cfb:{name}'],cwd=repo,capture_output=True,check=True).stdout
        destination=source/name.removeprefix('backend/src/')
        destination.parent.mkdir(parents=True,exist_ok=True)
        destination.write_bytes(data)
    old=Server(tmp_path/'data',source_directory=source)
    try:
        d=old.client.post('/api/account/drafts',json=BASELINE).json()
        old.client.post('/api/account/confirm',json={'draft_id':d['draft_id'],'idempotency_key':'baseline'}).raise_for_status()
        header=next(csv.reader(io.StringIO(old.client.get('/api/account/csv/template').text.lstrip('\ufeff'))))
        output=io.StringIO(newline='');writer=csv.DictWriter(output,header);writer.writeheader()
        writer.writerow({'template_version':'ROLL-CSV-2','kind':'RIGHTS_SUBSCRIPTION','effective_at':'2026-10-07T12:00:00+08:00','source':'原v2实际配股文件','record_id':' v2-rights ','exchange':'SSE','code':'600000','quantity':'100','amount':'501.00','basis':'总支付与新增股数有据，费用分拆未知'})
        raw=output.getvalue().encode('utf-8')
        draft=old.client.post('/api/account/csv/drafts',params={'filename':'v2.csv','encoding':'utf-8','expected_account_version':1},content=raw).json()
        assert draft['status']=='READY'
    finally:old.stop()
    new=Server(tmp_path/'data')
    try:
        client=new.client
        assert client.get('/api/account/csv/drafts/'+draft['draft_id']).json()==draft
        assert client.get('/api/account/csv/files/'+draft['file']['sha256']).content==raw
        receipt=client.post('/api/account/confirm',json={'draft_id':draft['draft_id'],'idempotency_key':'v2-upgrade'}).json()
        assert receipt['account_version']==2
        account=client.get('/api/account').json()
        assert account['cash_balance']=='99499.00'
        assert account['positions'][0]['acquisition_cost']=='501.00'
        assert account['lots'][0]['lot_id']=='v2-rights'
        assert account['rights_fee_breakdown_pending']==['v2-rights']
    finally:new.stop()
