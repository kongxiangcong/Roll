import json, os, time
from pathlib import Path
import httpx

out = Path(r"D:\dsh-proj\Roll\.scratch\roll-capability-expansion\evidence\16-sentiment\corpus-attempt")
param = {"uid":"","keyword":"600362","type":["cmsArticleWebOld"],"client":"web","clientType":"web","clientVersion":"curr",
         "param":{"cmsArticleWebOld":{"searchScope":"default","sort":"default","pageIndex":1,"pageSize":50,"preTag":"<em>","postTag":"</em>"}}}
url = "https://search-api-web.eastmoney.com/search/jsonp"
query = {"cb":"jQuery35101792940631092459_1764599530165","param":json.dumps(param,ensure_ascii=False,separators=(',',':')),"_":str(int(time.time()*1000))}
started=time.monotonic(); receipt={"attempt_id":"SENTIMENT-CORPUS-01","requests":0,"status":"PLANNED"}
try:
    with httpx.Client(proxy=os.environ.get("HTTPS_PROXY"), follow_redirects=False, timeout=10, trust_env=False) as client:
        receipt["requests"]+=1
        response=client.get(url,params=query,headers={"Referer":"https://so.eastmoney.com/","User-Agent":"Mozilla/5.0"})
    body=response.content
    receipt.update(status="FETCHED",http_status=response.status_code,bytes=len(body),elapsed_seconds=round(time.monotonic()-started,3))
    (out/"01.raw").write_bytes(body)
    text=body.decode("utf-8-sig")
    start=text.find("("); end=text.rfind(")")
    data=json.loads(text[start+1:end])
    rows=data["result"]["cmsArticleWebOld"]
    receipt["rows"]=len(rows)
    receipt["titles"]=[row.get("title") for row in rows[:5]]
except Exception as error:
    receipt.update(status="FAILED_CLOSED",error=type(error).__name__+": "+str(error)[:200],elapsed_seconds=round(time.monotonic()-started,3))
(out/"receipt.json").write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(receipt,ensure_ascii=False,indent=2))
