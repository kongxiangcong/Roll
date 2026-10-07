import json
import os
import sys
from pathlib import Path

from test_account_process import Server

sys.path.insert(0,str(Path(__file__).resolve().parents[3]/"scripts"))
from account_confirmation_performance import measure_confirmations


def test_single_fill_confirmation_p95_on_real_http_process_and_sqlite(tmp_path):
    server=Server(tmp_path/"data")
    try:
        command={"kind":"BASELINE","expected_account_version":0,"payload":{
            "effective_at":"2026-10-07T10:00:00+08:00","source":"30持仓合成性能基线","cash_balance":"1000000.00",
            "broker_available":"1000000.00","broker_frozen":"0.00","withdrawable":None,"permission_profile":[],
            "positions":[{"instrument":f"SSE:{600000+i}","quantity":"300","sellable_quantity":None,"reference_cost":None} for i in range(30)]}}
        draft=server.client.post("/api/account/drafts",json=command).json()
        assert server.client.post("/api/account/confirm",json={"draft_id":draft["draft_id"],"idempotency_key":"performance-baseline"}).status_code==200
        report=measure_confirmations(server.client,samples=100,warmup=10)
        report["sqlite_file_bytes"]=(tmp_path/"data"/"roll.sqlite3").stat().st_size
        report["archive_configuration"]="独立临时目录；02无附件/行情归档引用"
        if output:=os.environ.get("ROLL_EVIDENCE_DIR"):
            destination=Path(output)
            destination.mkdir(parents=True,exist_ok=True)
            (destination/"confirmation-performance.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
        assert report["p95_ms"]<=2000
        assert report["position_count"]==30
        assert report["event_count"]==142
    finally:
        server.stop()
