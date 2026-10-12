"""One bounded public BaoStock request for the fixed single-name study context."""
import json,time,hashlib
from pathlib import Path
from datetime import datetime,timezone
from roll.market.baostock import acquire,FIELDS

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'.scratch/roll-p0/evidence/19-reconstruction-2026-10-10/status-collection'
def main():
    OUT.mkdir(parents=True,exist_ok=False)
    command={'group':'DAILY','symbol':'sh.600362','fields':FIELDS,'start_date':'2016-12-01','end_date':'2023-12-31','auth_mode':'PUBLIC'}
    record={'command':command,'started_at':datetime.now(timezone.utc).isoformat(),'purpose':'RECONSTRUCTED_RESEARCH_STATUS_AND_CROSS_SOURCE_CHECK_ONLY','attempt_is_model_fit':False}
    try:
        wire,response=acquire(command,time.monotonic()+60,None,4*1024*1024,10)
        response_body=json.dumps(response,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
        (OUT/'daily.wire').write_bytes(wire);(OUT/'decoded.json').write_bytes(response_body)
        record.update(status='COMPLETE',rows=len(response['rows']),wire_sha256=hashlib.sha256(wire).hexdigest(),decoded_sha256=hashlib.sha256(response_body).hexdigest(),received_at=response['received_at'],calls=response['calls'])
    except Exception as error:record.update(status='FAILED',reason=str(error))
    record['finished_at']=datetime.now(timezone.utc).isoformat()
    (OUT/'receipt.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(record,ensure_ascii=False))
if __name__=='__main__':main()
