import json, os, time
from pathlib import Path
import httpx

out = Path(r"D:\dsh-proj\Roll\.scratch\roll-capability-expansion\evidence\16-sentiment\corpus-name-attempt")
receipt = {"attempt_id":"SENTIMENT-CORPUS-02","requests":0,"status":"RUNNING","pages":[],"retries":0}
rows_all=[]
try:
    with httpx.Client(proxy=os.environ.get("HTTPS_PROXY"), follow_redirects=False, timeout=10, trust_env=False) as client:
        for index in (1,2,3):
            param = {"uid":"","keyword":"江西铜业","type":["cmsArticleWebOld"],"client":"web","clientType":"web","clientVersion":"curr",
                     "param":{"cmsArticleWebOld":{"searchScope":"default","sort":"default","pageIndex":index,"pageSize":50,"preTag":"<em>","postTag":"</em>"}}}
            query = {"cb":"jQuery35101792940631092459_1764599530165","param":json.dumps(param,ensure_ascii=False,separators=(',',':')),"_":str(int(time.time()*1000))}
            started=time.monotonic();receipt["requests"]+=1
            response=client.get("https://search-api-web.eastmoney.com/search/jsonp",params=query,headers={"Referer":"https://so.eastmoney.com/","User-Agent":"Mozilla/5.0"})
            body=response.content;(out/f"{index:02}.raw").write_bytes(body)
            text=body.decode("utf-8-sig");data=json.loads(text[text.find("(")+1:text.rfind(")")])
            rows=data["result"]["cmsArticleWebOld"];rows_all.extend(rows)
            receipt["pages"].append({"page":index,"http_status":response.status_code,"bytes":len(body),"rows":len(rows),"seconds":round(time.monotonic()-started,3)})
    seen=set();unique=[]
    for row in rows_all:
        key=(row.get("url") or row.get("code") or "").strip()
        if key in seen:continue
        seen.add(key)
        unique.append({"title":row.get("title"),"summary":row.get("content"),"url":row.get("url"),"media":row.get("mediaName"),"date":row.get("date"),"code":row.get("code")})
    (out/"corpus.json").write_text(json.dumps({"upstream":"search-api-web.eastmoney.com/search/jsonp","keyword":"江西铜业","instrument":"SSE:600362","returned":len(rows_all),"unique":len(unique),"items":unique},ensure_ascii=False,indent=2),encoding="utf-8")
    receipt.update(status="CAPTURED",returned=len(rows_all),unique=len(unique),bytes_total=sum(p["bytes"] for p in receipt["pages"]))
except Exception as error:
    receipt.update(status="FAILED_CLOSED",error=type(error).__name__+": "+str(error)[:200])
(out/"receipt.json").write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(receipt,ensure_ascii=False,indent=2))
