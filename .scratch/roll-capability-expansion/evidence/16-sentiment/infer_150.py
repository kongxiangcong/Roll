import json, time
from pathlib import Path
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification
base=Path(r"D:\dsh-proj\Roll\.scratch\rce-runtime\sentiment\Erlangshen")
out=Path(r"D:\dsh-proj\Roll\.scratch\roll-capability-expansion\evidence\16-sentiment")
corpus=json.loads((out/"corpus-name-attempt"/"corpus.json").read_text(encoding="utf-8"))
tokenizer=AutoTokenizer.from_pretrained(str(base),local_files_only=True)
model=AutoModelForSequenceClassification.from_pretrained(str(base),local_files_only=True);model.eval();torch.set_num_threads(2)
rows=[];latencies=[]
for i,item in enumerate(corpus["items"][:150]):
    text=((item.get("title") or "")+" "+(item.get("summary") or ""))[:800]
    started=time.monotonic()
    with torch.inference_mode():
        enc=tokenizer(text,return_tensors="pt",truncation=True,max_length=256)
        logits=model(**enc).logits[0];probs=torch.softmax(logits,dim=-1).tolist()
    latencies.append(time.monotonic()-started)
    rows.append({"index":i,"prob_negative":round(probs[0],6),"prob_positive":round(probs[1],6)})
(out/"inference-150.json").write_text(json.dumps({"model":"IDEA-CCNL/Erlangshen-Roberta-110M-Sentiment","weights_sha256":"a1d1328c759c50726db6617c75abb5c260b12377bee7ecd003c8a201b526e38e","rows":rows,"latency_p50":round(sorted(latencies)[len(latencies)//2],4),"latency_p95":round(sorted(latencies)[int(len(latencies)*0.95)-1],4)},indent=2),encoding="utf-8")
print("inference done",len(rows))
