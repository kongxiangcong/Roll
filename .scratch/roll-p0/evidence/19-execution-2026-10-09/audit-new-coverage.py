"""Audit public provenance and date coverage without loading research partitions."""
from pathlib import Path
from datetime import date, timedelta
import ast
import hashlib
import json

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
OLD = OUT.parent/'19-completion-2026-10-09'
rules = ROOT/'backend/src/roll/market/rules.py'
values = {}
for node in ast.parse(rules.read_text(encoding='utf-8')).body:
    if isinstance(node,ast.Assign):
        for target in node.targets:
            if isinstance(target,ast.Name) and target.id in {'SSE_HISTORICAL_HOLIDAYS','SSE_CALENDAR_CORRECTIONS'}:
                values[target.id] = ast.literal_eval(node.value)

def trading(day):
    if day.year not in values['SSE_HISTORICAL_HOLIDAYS']:
        raise ValueError('UNSUPPORTED_YEAR')
    spans = list(values['SSE_HISTORICAL_HOLIDAYS'][day.year]) + [
        (a,b) for a,b,_ in values['SSE_CALENDAR_CORRECTIONS'].get(day.year,[])]
    return day.weekday()<5 and not any(date.fromisoformat(f'{day.year}-{a}')<=day<=date.fromisoformat(f'{day.year}-{b}') for a,b in spans)

def coverage(dates):
    runs=[]
    for day in sorted({date.fromisoformat(d) for d in dates}):
        if not trading(day):
            raise ValueError('NONTRADING_BUSINESS_DATE')
        nxt=runs[-1][-1]+timedelta(days=1) if runs else None
        if nxt:
            while not trading(nxt):
                nxt+=timedelta(days=1)
        if day==nxt:
            runs[-1].append(day)
        else:
            runs.append([day])
    return {'business_days':sum(map(len,runs)), 'longest_run':max(map(len,runs),default=0),
            'runs':[[d.isoformat() for d in run] for run in runs]}

sources=json.loads((rules.parent/'reference/sources.json').read_bytes())
old=json.loads((OLD/'sina-archive-quote-analysis.json').read_bytes())['quotes']
receipts=[json.loads((OUT/name).read_bytes()) for name in ['exact-index-receipts.json','exact-payload-receipts.json','exact-payload-retry-receipts.json']]
new=[row for report in receipts for row in report['requests'] if 'quote' in row]
mismatches=[]
verified=[]
references=[{'path':q['wire_path'],'sha256':q['wire_sha256'],'bytes':q['wire_bytes'],'kind':'REUSED_OLD_QUOTE'} for q in old]
references.extend({'path':r['path'],'sha256':r['sha256'],'bytes':r['bytes'],'kind':'NEW_HTTP_RESPONSE'} for report in receipts for r in report['requests'] if 'path' in r)
years={int(q['quote']['business_date'][:4]) for q in old+new}
ids={f'sse-calendar-{y}' for y in years}
ids.update(sid for y in years for _,_,sid in values['SSE_CALENDAR_CORRECTIONS'].get(y,[]))
for source in sources:
    if source['id'] in ids:
        path=rules.parent/'reference'/source['file']
        references.append({'path':str(path),'sha256':source['sha256'],'bytes':path.stat().st_size,'kind':'OFFICIAL_CALENDAR'})
for reference in references:
    body=Path(reference['path']).read_bytes()
    if len(body)!=reference['bytes'] or hashlib.sha256(body).hexdigest()!=reference['sha256']:
        mismatches.append(reference['path'])
    else:
        verified.append(reference)
dates=[q['quote']['business_date'] for q in old+new]
nominal=[q['quote']['business_date'] for q in old+new if q['quote']['business_time']>='15:00:00']
unique={r['sha256']:r for r in verified}
result={'references':verified,'reference_count':len(references),'unique_sha256':len(unique),
        'unique_bytes':sum(r['bytes'] for r in unique.values()),'hash_length_mismatches':mismatches,
        'reused_quote_captures':len(old),'new_quote_captures':len(new),
        'all_quotes':coverage(dates),'nominal_after_close':coverage(nominal),
        'required_lookback_rows':21,'qualified_training_rows':0,
        'notes':['Quote business clock>=15:00 is not proof of complete trading phase/status/schema.',
                 'New2016-02-19 zeroOHLC quote is consistent with known suspension; not a trading bar.',
                 'New2018-10-23 versions are intraday; never substitute either for a completed bar.',
                 'Archive capture is availability bound, not exact first publication; no live fallback.'],
        'labels_computed':False,'models_fitted':0,'sealed_read':False,'runtime_db_opened':False}
(OUT/'coverage-and-integrity.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:result[k] for k in ['reference_count','unique_sha256','hash_length_mismatches','new_quote_captures','qualified_training_rows']} |
                 {'business_days':result['all_quotes']['business_days'],'longest_run':result['all_quotes']['longest_run']}))
