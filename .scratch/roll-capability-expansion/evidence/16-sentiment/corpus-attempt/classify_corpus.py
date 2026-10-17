import json
from pathlib import Path
from roll.market.news_events import associate
corpus=json.loads((Path(r"D:\dsh-proj\Roll\.scratch\roll-capability-expansion\evidence\16-sentiment\corpus-attempt")/"corpus.json").read_text(encoding="utf-8"))
identity=[{"instrument":"SSE:600362","name":"江西铜业股份有限公司","code":"600362"}]
counts={}
for index,item in enumerate(corpus["items"]):
    fact={"fact_id":str(index),"instrument":"SSE:600362","title":item.get("title") or "","excerpt":item.get("summary"),
          "url":item.get("url") or "https://finance.eastmoney.com/a/1.html","body_text":None}
    decision=associate(fact,identity)
    counts[decision["classification"]]=counts.get(decision["classification"],0)+1
print(json.dumps({"total":len(corpus["items"]),"counts":counts},ensure_ascii=False,indent=2))
