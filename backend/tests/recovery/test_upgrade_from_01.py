"""Start actual ancestral 01 code through HTTP, then upgrade the same files.

No direct SQL setup/assertions: the old service creates the legacy schema.
"""
import subprocess
from pathlib import Path

from test_account_process import Server
from test_fill_process import BASELINE


def test_existing_01_draft_receipt_and_history_survive_migration_2(tmp_path):
    repo=Path(__file__).resolve().parents[3]
    old_src=tmp_path/"01-source"
    files=["__init__.py","config.py","app.py","accounts/__init__.py","accounts/ledger.py"]
    for name in files:
        source=subprocess.run(["git","show",f"17ca07d:backend/src/roll/{name}"],cwd=repo,check=True,capture_output=True).stdout.decode("utf-8")
        destination=old_src/"roll"/name
        destination.parent.mkdir(parents=True,exist_ok=True)
        destination.write_text(source,encoding="utf-8")
    directory=tmp_path/"data"
    old=Server(directory,source_directory=old_src)
    try:
        draft=old.client.post("/api/account/drafts",json=BASELINE).json()
        receipt=old.client.post("/api/account/confirm",json={"draft_id":draft["draft_id"],"idempotency_key":"old-01"}).json()
        snapshot=old.client.get("/api/account").json()
        permission={"kind":"PERMISSIONS","expected_account_version":1,"payload":{
            "effective_at":"2026-10-07T11:00:00+08:00","source":"旧程序权限草稿","permission_profile":[]}}
        pending=old.client.post("/api/account/drafts",json=permission).json()
    finally:
        old.stop()
    new=Server(directory)
    try:
        assert new.client.get("/api/account").json()==snapshot
        assert new.client.get("/api/account/versions/1").json()==snapshot
        assert new.client.get("/api/account/receipts/"+receipt["receipt_id"]).json()==receipt
        saved=new.client.get("/api/account/drafts/"+pending["draft_id"]).json()
        assert saved["status"]=="READY"
        assert saved["command"]==permission
        result=new.client.post("/api/account/confirm",json={"draft_id":pending["draft_id"],"idempotency_key":"post-upgrade"})
        assert result.status_code==200
        assert new.client.get("/api/account").json()["version"]==2
    finally:
        new.stop()
