"""Measure real HTTP confirmations on an explicitly isolated test account.

08/13 can run this while their actual retrieval/model task is waiting, with the
same running test application/client. It does not mock a retrieval task.
"""
import argparse
import json
import math
import platform
import sqlite3
import statistics
import time
from uuid import uuid4

import httpx


def measure_confirmations(client,samples=100,warmup=10):
    if client.get("/api/health").json().get("environment")!="test":
        raise ValueError("确认性能测量仅可连接 ROLL_ENV=test 的隔离账户服务")
    run_id=str(uuid4())
    measurements=[]
    for i in range(samples+warmup):
        account=client.get("/api/account").json()
        if account["version"]==0:
            raise ValueError("请先在隔离测试账户建立合成基线")
        record=f"performance-{run_id}-{i}"
        command={"kind":"FILL","expected_account_version":account["version"],"payload":{
            "effective_at":"2026-10-07T11:00:00+08:00","source":"合成确认性能样例","instrument":"SSE:600000",
            "direction":"BUY","quantity":"100","price":"10.00","record_id":record,"fill_id":record,"order_id":None,
            "behavior_context":"NO_RECOMMENDATION","broker_available_after":None,
            "fee":{"status":"KNOWN","amount":"5.00","reserve_amount":None,"basis":"合成固定费用5元"}}}
        draft=client.post("/api/account/drafts",json=command)
        draft.raise_for_status()
        start=time.perf_counter()
        receipt=client.post("/api/account/confirm",json={"draft_id":draft.json()["draft_id"],"idempotency_key":record})
        receipt.raise_for_status()
        result=receipt.json()
        elapsed=(time.perf_counter()-start)*1000
        if result["account_version"]!=account["version"]+1:
            raise AssertionError("确认未推进一次版本")
        if i>=warmup:
            measurements.append(elapsed)
    account=client.get("/api/account").json()
    return {"measurement":"POST /api/account/confirm HTTP round-trip + JSON decode, warm persistent TCP client",
            "samples":samples,"warmup":warmup,"p95_method":"nearest rank ceil(0.95*n)",
            "p95_ms":sorted(measurements)[math.ceil(.95*samples)-1],"median_ms":statistics.median(measurements),
            "max_ms":max(measurements),"samples_ms":measurements,"position_count":len(account["positions"]),
            "event_count":len(client.get("/api/account/events").json()),"account_version":account["version"],
            "platform":platform.platform(),"processor":platform.processor(),"python":platform.python_version(),
            "sqlite":sqlite3.sqlite_version,"external_task_integration":"pending actual 08/13 execution"}


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url",required=True,help="ROLL_ENV=test isolated application URL")
    parser.add_argument("--samples",type=int,default=100)
    parser.add_argument("--warmup",type=int,default=10)
    parser.add_argument("--output",required=True)
    args=parser.parse_args()
    if args.samples<1 or args.warmup<0:
        parser.error("samples须正数，warmup须非负")
    with httpx.Client(base_url=args.api_url,timeout=10) as client:
        report=measure_confirmations(client,args.samples,args.warmup)
    with open(args.output,"w",encoding="utf-8") as file:
        json.dump(report,file,ensure_ascii=False,indent=2)
    print(f"P95: {report['p95_ms']:.3f} ms ({report['samples']} confirmations)")
