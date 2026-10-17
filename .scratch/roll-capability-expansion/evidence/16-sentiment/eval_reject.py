import json
from pathlib import Path
from roll.market.news_events import associate

out=Path(r"D:\dsh-proj\Roll\.scratch\roll-capability-expansion\evidence\16-sentiment")
layer=json.loads((out/"reject-layer.json").read_text(encoding="utf-8"))
inference={row["index"]:row for row in json.loads((out/"inference-150.json").read_text(encoding="utf-8"))["rows"]}
design=json.loads((out/"labels-120.json").read_text(encoding="utf-8"))["items"]
holdout=json.loads((out/"labels-holdout-30.json").read_text(encoding="utf-8"))["items"]
identity=[{"instrument":"SSE:600362","name":"江西铜业股份有限公司","code":"600362"}]

def decide(item):
    title=item["title"] or "";text=title+" "+(item.get("summary") or "")
    has_company=any(alias in title for alias in layer["company_aliases"])
    if not has_company and any(marker in title for marker in ["ETF","指数","收评","午评"]):return "ABSTAIN_MARKET_INDEX"
    if not has_company and any(marker in title for marker in ["资金流入","资金流出","资金流向","主力资金"]):return "ABSTAIN_FUND_FLOW"
    if not any(cue in text for cue in layer["directional_cues"]):return "ABSTAIN_NO_DIRECTIONAL_CUE"
    fact={"fact_id":str(item["index"]),"instrument":"SSE:600362","title":title,"excerpt":item.get("summary"),"url":"https://finance.eastmoney.com/a/1.html","body_text":None}
    if associate(fact,identity)["classification"] in ("INDUSTRY_BACKGROUND","UNRELATED"):return "ABSTAIN_RELEVANCE"
    row=inference[item["index"]];confidence=max(row["prob_negative"],row["prob_positive"])
    if confidence<0.65:return "ABSTAIN_LOW_CONFIDENCE"
    return "POSITIVE" if row["prob_positive"]>=row["prob_negative"] else "NEGATIVE"

def evaluate(items):
    rows=[]
    for item in items:
        row=inference[item["index"]];prediction=decide(item)
        rows.append({"index":item["index"],"label":item["label"],"prediction":prediction,
                     "confidence":round(max(row["prob_negative"],row["prob_positive"]),6)})
    binary=[r for r in rows if r["label"] in ("POSITIVE","NEGATIVE")]
    non=[r for r in rows if r["label"] in ("NEUTRAL","IRRELEVANT")]
    tp={c:0 for c in ("POSITIVE","NEGATIVE")};fp={c:0 for c in ("POSITIVE","NEGATIVE")};fn={c:0 for c in ("POSITIVE","NEGATIVE")}
    for r in binary:
        if r["prediction"]==r["label"]:tp[r["label"]]+=1
        elif r["prediction"] in ("POSITIVE","NEGATIVE"):fn[r["label"]]+=1;fp[r["prediction"]]+=1
    recall={c:(tp[c]/(tp[c]+fn[c]) if tp[c]+fn[c] else None) for c in tp}
    precision={c:(tp[c]/(tp[c]+fp[c]) if tp[c]+fp[c] else None) for c in tp}
    f1={c:(2*precision[c]*recall[c]/(precision[c]+recall[c]) if precision[c] and recall[c] else 0.0) for c in tp}
    confusion={}
    for r in rows:
        key=r["label"]+"->"+r["prediction"];confusion[key]=confusion.get(key,0)+1
    return {"total":len(rows),"binary":len(binary),"non_directional":len(non),
        "recall":recall,"precision":precision,"f1":f1,"macro_f1":sum(f1.values())/2,
        "abstain":sum(1 for r in rows if r["prediction"].startswith("ABSTAIN")),
        "abstain_coverage":round(sum(1 for r in rows if r["prediction"].startswith("ABSTAIN"))/len(rows),4),
        "non_directional_rejected":sum(1 for r in non if r["prediction"].startswith("ABSTAIN")),
        "non_directional_rejection_rate":round(sum(1 for r in non if r["prediction"].startswith("ABSTAIN"))/len(non),4) if non else None,
        "confusion":confusion}
report={"layer_version":layer["version"],"design":evaluate(design),"holdout":evaluate(holdout),"combined":evaluate(design+holdout),
    "latency_p95":json.loads((out/"inference-150.json").read_text(encoding="utf-8"))["latency_p95"]}
c=report["combined"]
report["gates"]={"macro_f1":0.60,"positive_recall":0.55,"negative_recall":0.55,"non_directional_rejection":0.80,"abstain_coverage":0.35,"p95_seconds":3.0}
report["passed"]=bool(c["macro_f1"]>=0.60 and c["recall"]["POSITIVE"]>=0.55 and c["recall"]["NEGATIVE"]>=0.55 and
    c["non_directional_rejection_rate"]>=0.80 and c["abstain_coverage"]<=0.35 and report["latency_p95"]<=3.0)
(out/"eval-reject-results.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps({k:report[k] for k in ("design","holdout","combined","gates","passed")},ensure_ascii=False,indent=2))
