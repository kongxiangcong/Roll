"""Fault injection runs a real HTTP server, SQLite file and OS process.

All assertions observe public HTTP APIs after restarting the process.
"""
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1",0))
        return sock.getsockname()[1]


class Server:
    def __init__(self, directory, fault=None):
        port = free_port()
        env = {**os.environ,"ROLL_DATA_DIR":str(directory),"ROLL_ENV":"test"}
        env.pop("ROLL_TEST_CRASH_POINT",None)
        if fault:
            env["ROLL_TEST_CRASH_POINT"] = fault
        self.log = open(directory.parent/f"server-{port}.log","w",encoding="utf-8")
        self.process = subprocess.Popen([sys.executable,"-m","uvicorn","roll.app:create_app","--factory","--host","127.0.0.1","--port",str(port)],
                                        cwd=Path(__file__).resolve().parents[2],env=env,stdout=self.log,stderr=subprocess.STDOUT)
        self.client = httpx.Client(base_url=f"http://127.0.0.1:{port}",timeout=10)
        deadline = time.monotonic()+20
        while time.monotonic()<deadline:
            try:
                if self.client.get("/api/health").status_code==200:
                    return
            except httpx.TransportError:
                pass
            if self.process.poll() is not None:
                break
            time.sleep(.1)
        self.stop()
        raise AssertionError("real server did not start")

    def stop(self):
        if self.process.poll() is None:
            self.process.kill()
            self.process.wait(timeout=10)
        self.client.close()
        self.log.close()


@pytest.mark.parametrize("fault,expected_version",[("before_commit",0),("after_commit",1),("after_receipt",1)])
def test_confirmed_facts_and_receipt_survive_real_process_fault(tmp_path,fault,expected_version):
    directory = tmp_path/"data"
    server = Server(directory,None if fault=="after_receipt" else fault)
    client = server.client
    draft_input = {"kind":"BASELINE","expected_account_version":0,"payload":{
        "effective_at":"2026-10-07T10:00:00+08:00","source":"脱敏恢复验收快照",
        "cash_balance":"100000.10","broker_available":None,"broker_frozen":None,"withdrawable":None,
        "positions":[{"instrument":"SSE:600000","quantity":"300","sellable_quantity":None,"reference_cost":"10.00"}],
        "permission_profile":[]}}
    draft = client.post("/api/account/drafts",json=draft_input).json()
    command = {"draft_id":draft["draft_id"],"idempotency_key":"crash-proof"}
    original = None
    try:
        if fault=="after_receipt":
            response = client.post("/api/account/confirm",json=command)
            assert response.status_code==200
            original = response.json()
            server.stop()  # Abrupt OS termination immediately after receiving durable success.
        else:
            with pytest.raises(httpx.TransportError):
                client.post("/api/account/confirm",json=command)
            assert server.process.wait(timeout=10)==86
    finally:
        server.stop()
    recovered = Server(directory)
    try:
        client = recovered.client
        assert client.get("/api/account").json()["version"]==expected_version
        events_before = client.get("/api/account/events").json()
        assert len(events_before)==(0 if expected_version==0 else 3)
        replay = client.post("/api/account/confirm",json=command)
        assert replay.status_code==200
        receipt = replay.json()
        if original:
            assert receipt==original
        assert client.get(f"/api/account/receipts/{receipt['receipt_id']}").json()==receipt
        assert client.post("/api/account/confirm",json=command).json()==receipt
        assert client.get("/api/account").json()["cash_balance"]=="100000.10"
        assert client.get("/api/account").json()["version"]==1
        events_after = client.get("/api/account/events").json()
        assert len(events_after)==3
        if expected_version==1:
            assert events_after==events_before
        assert len(client.get("/api/account/audit").json())==1
    finally:
        recovered.stop()
