import json, time, statistics
from pathlib import Path
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification

base = Path(r"D:\dsh-proj\Roll\.scratch\rce-runtime\sentiment\Erlangshen")
out = Path(r"D:\dsh-proj\Roll\.scratch\roll-capability-expansion\evidence\16-sentiment")
labels = json.loads((out/"labels-120.json").read_text(encoding="utf-8"))
tokenizer = AutoTokenizer.from_pretrained(str(base), local_files_only=True)
model = AutoModelForSequenceClassification.from_pretrained(str(base), local_files_only=True)
model.eval()
torch.set_num_threads(2)
results=[];latencies=[]
for item in labels["items"]:
    text = (item["title"] + " " + (item["summary"] or ""))[:800]
    started=time.monotonic()
    with torch.inference_mode():
        encoded = tokenizer(text, return_tensors="pt", truncation=True, max_length=256)
        logits = model(**encoded).logits[0]
        probs = torch.softmax(logits, dim=-1).tolist()
    latencies.append(time.monotonic()-started)
    predicted = "POSITIVE" if probs[1] >= probs[0] else "NEGATIVE"
    confidence = max(probs)
    abstain = None
    if confidence < 0.65: abstain = "ABSTAIN_LOW_CONFIDENCE"
    results.append({"index":item["index"],"title":item["title"],"label":item["label"],"predicted":predicted,
                    "confidence":round(confidence,6),"abstain":abstain,"probabilities":[round(p,6) for p in probs]})
def metrics(pairs):
    labels_set=("POSITIVE","NEGATIVE")
    tp={c:0 for c in labels_set};fp={c:0 for c in labels_set};fn={c:0 for c in labels_set}
    for truth,pred in pairs:
        if truth in labels_set:
            if pred==truth:tp[truth]+=1
            else:fn[truth]+=1
        if pred in labels_set and pred!=truth:fp[pred]+=1
    recalls={c:(tp[c]/(tp[c]+fn[c]) if tp[c]+fn[c] else None) for c in labels_set}
    precisions={c:(tp[c]/(tp[c]+fp[c]) if tp[c]+fp[c] else None) for c in labels_set}
    f1={c:(2*precisions[c]*recalls[c]/(precisions[c]+recalls[c]) if precisions[c] and recalls[c] and precisions[c]+recalls[c] else 0.0) for c in labels_set}
    return {"recall":recalls,"precision":precisions,"f1":f1,"macro_f1":sum(f1.values())/2}
usable=[(r["label"],r["predicted"]) for r in results if r["abstain"] is None]
binary=[(r["label"],r["predicted"]) for r in results if r["label"] in ("POSITIVE","NEGATIVE") and r["abstain"] is None]
confusion={}
for r in results:
    key=r["label"]+"->"+(r["abstain"] or r["predicted"])
    confusion[key]=confusion.get(key,0)+1
summary={"model":"IDEA-CCNL/Erlangshen-Roberta-110M-Sentiment","license":"apache-2.0",
    "weights_sha256":"a1d1328c759c50726db6617c75abb5c260b12377bee7ecd003c8a201b526e38e",
    "labels_total":len(results),"binary_labeled":sum(1 for r in results if r["label"] in ("POSITIVE","NEGATIVE")),
    "abstain":sum(1 for r in results if r["abstain"]),
    "metrics_all_binary":metrics(binary),"metrics_all_usable":metrics(usable),
    "confusion":confusion,"latency_p50":round(statistics.median(latencies),4),
    "latency_p95":round(sorted(latencies)[max(0,int(len(latencies)*0.95)-1)],4),
    "frozen_thresholds":{"macro_f1":0.60,"positive_recall":0.55,"negative_recall":0.55,"abstain_coverage":0.35,"p95_seconds":3.0}}
summary["passed"]=bool(summary["metrics_all_binary"]["macro_f1"]>=0.60 and
    summary["metrics_all_binary"]["recall"]["POSITIVE"]>=0.55 and summary["metrics_all_binary"]["recall"]["NEGATIVE"]>=0.55 and
    summary["abstain"]/len(results)<=0.35 and summary["latency_p95"]<=3.0)
(out/"eval-results.json").write_text(json.dumps({"summary":summary,"items":results},ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(summary,ensure_ascii=False,indent=2))
