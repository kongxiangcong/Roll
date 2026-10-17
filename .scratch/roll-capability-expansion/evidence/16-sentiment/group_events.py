import json
from pathlib import Path
from roll.market.news_events import associate,group_facts
out=Path(r"D:\dsh-proj\Roll\.scratch\roll-capability-expansion\evidence\16-sentiment")
corpus=json.loads((out/"corpus-name-attempt"/"corpus.json").read_text(encoding="utf-8"))
identity=[{"instrument":"SSE:600362","name":"江西铜业股份有限公司","code":"600362"}]
facts=[]
for index,item in enumerate(corpus["items"][:150]):
    facts.append({"fact_id":str(index),"instrument":"SSE:600362","title":item.get("title") or "","excerpt":item.get("summary"),
        "url":item.get("url") or f"https://finance.eastmoney.com/a/{index}.html","body_text":None,"available_at":item.get("date") or ""})
associations={f["fact_id"]:associate(f,identity) for f in facts}
memberships,events=group_facts(facts,associations)
report={"total":len(facts),"unique_events":len(events),"events_with_multiple_facts":sum(1 for e in events if len(e["fact_ids"])>1),
    "reprints":sum(e["reprints"] for e in events),"revisions":sum(e["revisions"] for e in events),
    "date_first":min(f["available_at"] for f in facts if f["available_at"]),
    "date_last":max(f["available_at"] for f in facts if f["available_at"]),
    "association_counts":{k:sum(1 for a in associations.values() if a["classification"]==k) for k in sorted({a["classification"] for a in associations.values()})}}
(out/"event-grouping.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(report,ensure_ascii=False,indent=2))
