"""Explicit agent annotations, source-bound; never loads model probabilities."""
import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from object_contract import project

out = Path(__file__).resolve().parent
assert not (out/'labels-draft.json').exists()
sources = {}
for prefix,name in (('03','corpus.json'),('04','corpus04.json')):
    for row in json.loads((out/name).read_bytes())['items']:
        sources[prefix+'-'+str(row['index'])] = {**row,'id':prefix+'-'+str(row['index']),'source_file':name}
for row in json.loads((out/'corpus06.json').read_bytes())['items']:
    sources[row['id']] = {**row,'source_file':'corpus06.json'}

positive = ['04-'+str(i) for i in (12,25,38,46,47,79,82,137,167,198,199,206,251,244,283,343,353,271,332,409,418,421,426,470,13,18,55,75,87)] + ['03-701']
negative = ['03-686'] + ['04-'+str(i) for i in (11,31,36,108,118,128,174,180,193,293,294,313,314,395,406)]
negative += ['CNI-'+i for i in ('1205949979','1206730940','1207432726','1207667974','1208325593','1208662992','1209481070','1210900078','1212685857','1214405245','1216220924','1217649497','1219426052','1221024137')]
neutral = ['CNI-'+i for i in ('1202351798','1202351800','1202552172','1203572165','1203572166','1203572167','1203572168','1203897243','1205099331','1205099333','1205099335','1205613239','1205781833','1205781834','1206094729','1207208058','1208664534','1209410530','1209410536','1209410539','1210301354','1224607184','1224607190','1224607191','1224607192','1224607195','1224607196','1224607197','1224607198','1224607199')]
irrelevant = ['03-'+str(i) for i in (0,1,3,5,7,9,12,13,19,20,23,24,26,27,28)]
irrelevant += ['04-'+str(i) for i in (39,49,67,68,71,72,73,74,76,77,80,105,32,40,50)]
assert all(len(items)==30 for items in (positive,negative,neutral,irrelevant))

funds = {i:'FUND-'+sources[i]['title'].split('：')[0]+'-2026Q2' for i in irrelevant if i.startswith('04-') and any(k in sources[i]['summary'] for k in ('重仓股','持仓'))}
overrides = {**funds,'04-39':'ETF-517520-20260730','04-40':'ETF-517520-20260730','04-49':'ETF-159157-20260723','04-50':'ETF-159157-20260723',
             '04-32':'SUPPLIER-SENHE-IPO-20260805','04-105':'FUND-FLOW-20260722','03-20':'OTHER-民生健康-2026Q3',
             'CNI-63213186':'ISSUER-2013Q3-CORRECTION','CNI-63261941':'ISSUER-2013Q3-CORRECTION','CNI-63261942':'ISSUER-2013Q3-CORRECTION',
             'CNI-62261185':'YONGPING-2013-STOP-RECOVERY','CNI-62318978':'YONGPING-2013-STOP-RECOVERY',
             'CNI-62430657':'AGM-2012-RESCHEDULE','CNI-62516096':'AGM-2012-RESCHEDULE','CNI-62583965':'AGM-2012-RESCHEDULE'}
for index in ('1202351798','1202351800','1203572165','1203572166','1203572167','1203572168'):
    overrides['CNI-'+index] = 'ISSUER-2016-FUNDRAISING-REVISIONS'
for index in ('1205099331','1205099333','1205099335'):
    overrides['CNI-'+index] = 'ISSUER-2018-REPORT-REVISION-BUNDLE'


def event_id(row):
    if row['id'] in overrides:
        return overrides[row['id']]
    if row['id'].startswith('CNI-'):
        return 'ISSUER-EVENT-'+row['date'][:10]
    if row['id'] in irrelevant and row['id'].startswith('03-'):
        return 'OTHER-'+row['title'].split('：')[0]+'-2026Q3'
    # Use the event session stated in the excerpt, retaining original publication date.
    match = re.search(r'(?:截至|截止)\s*(2026)年\s*(\d{1,2})月\s*(\d{1,2})日', row['summary'])
    day = f'{match[1]}-{int(match[2]):02}-{int(match[3]):02}' if match else row['date'][:10]
    return 'COMPANY-MARKET-SESSION-'+day


def labeled(identifier, label, split, reason):
    row = dict(sources[identifier])
    row.update(label=label,split=split,label_rationale=reason,event_id=event_id(row),label_origin='AGENT_NON_INDEPENDENT_BEFORE_MODEL_OUTPUT')
    row['projection'] = project(row['title'],row['summary'])
    row['input_sha256'] = hashlib.sha256(row['projection']['text'].encode()).hexdigest()
    return row

rows = []
for ids,label,reason in ((positive,'POSITIVE','Explicit target-company price rise; no inference about future returns.'),
                        (negative,'NEGATIVE','Explicit target price fall or disclosed asset impairment; independent opinions are not treated as new impairment events.'),
                        (neutral,'NEUTRAL','Governance/procedural/report-text revision without a stated favorable or adverse financial delta.'),
                        (irrelevant,'IRRELEVANT','Other-company outcome or target only in constituent/holding/customer list; no target-company directional assertion.')):
    for identifier in ids:
        rows.append(labeled(identifier,label,'HOLDOUT_PRIMARY',reason))

development = [('CNI-62261185','NEGATIVE','Accident-caused production suspension.'),('CNI-62318978','POSITIVE','Resumption after production suspension.'),
               ('CNI-62167749','NEUTRAL','Issuer denial of accident/ordered shutdown; normal operation rather than an invented positive financial delta.'),
               ('CNI-62182678','NEUTRAL','Board resolution procedure.'),('CNI-62430657','NEUTRAL','Meeting notice.'),
               ('CNI-62516096','NEUTRAL','Meeting rescheduling.'),('CNI-62583965','NEUTRAL','Meeting resolution/factual dividend procedure, no future-return implication.'),
               ('CNI-63041127','NEUTRAL','Investor communication event.'),('CNI-63213186','NEUTRAL','Report title without financial delta.'),
               ('CNI-63261941','NEUTRAL','Revised report; underlying corrected shareholder table is not a new earnings delta.'),
               ('CNI-63261942','NEUTRAL','Shareholder table correction.'),('CNI-1200654155','NEUTRAL','Office address change.'),
               ('CNI-1201010731','NEUTRAL','Meeting agenda correction; other original matters unchanged.')]
for identifier,label,reason in development:
    rows.append(labeled(identifier,label,'DEVELOPMENT',reason))

# Visual transcription from the actual rendered source page; broken embedded text is retained separately.
denial = next(row for row in rows if row['id']=='CNI-62167749')
denial['visual_source'] = {'pdf':'source-pdf07/62167749.pdf','page':1,'image':'denial-page.png',
                         'original_spans':['近期无任何突发性环境保护事故发生。','从未有过被要求停业整顿的事实。'],
                         'method':'AGENT_VISUAL_TRANSCRIPTION_NON_INDEPENDENT; no OCR-success claim'}
denial['summary'] = '江西铜业：近期无任何突发性环境保护事故发生。江西铜业：从未有过被要求停业整顿的事实。'
denial['projection'] = project(denial['title'],denial['summary'])
denial['input_sha256'] = hashlib.sha256(denial['projection']['text'].encode()).hexdigest()

stress = labeled('04-145','POSITIVE','HOLDOUT_STRESS','Same verbatim archived summary as04-137, different URL/title; paragraph-level republication evidence, not full-article identity.')
stress['paired_with'] = '04-137'
assert sources['04-145']['summary']==sources['04-137']['summary']
assert sources['04-145']['url']!=sources['04-137']['url']
stress['event_id'] = next(row['event_id'] for row in rows if row['id']=='04-137')
rows.append(stress)

primary = [row for row in rows if row['split']=='HOLDOUT_PRIMARY']
dev = [row for row in rows if row['split']=='DEVELOPMENT']
assert len(primary)==120 and len({row['id'] for row in rows})==len(rows)
assert all(row['date'][:10]>='2016-01-01' for row in primary)
assert all(row['date'][:10]<'2016-01-01' for row in dev)
assert not ({row['event_id'] for row in primary}&{row['event_id'] for row in dev})
support = {label:{'rows':sum(row['label']==label for row in primary),'event_groups':len({row['event_id'] for row in primary if row['label']==label})} for label in ('POSITIVE','NEGATIVE','NEUTRAL','IRRELEVANT')}
assert all(value['rows']==30 and value['event_groups']>=10 for value in support.values()),support
result = {'labeled_at':datetime.now(timezone.utc).isoformat(),'labeler':'AGENT_NON_INDEPENDENT','boundary':'2016-01-01',
          'source_sha256':{name:hashlib.sha256((out/name).read_bytes()).hexdigest() for name in ('corpus.json','corpus04.json','corpus06.json')},
          'support':support,'development_count':len(dev),'stress_count':1,'rows':rows,
          'rubric':'Target-specific textual financial sentiment on finite presented input, not investment value. Procedural/governance corrections neutral unless actual directional financial assertion; incidental target mention irrelevant.',
          'limitations':['NON_INDEPENDENT_AGENT_LABELS','STRATIFIED_CHALLENGE_NOT_NATURAL_FEED_COVERAGE','UNKNOWN_PRIVATE_TRAINING_OVERLAP','CORRELATED_SINGLE_COMPANY_EVENTS','TITLE_SUMMARY_OR_LOCATED_PDF_SPAN_ONLY']}
(out/'labels-draft.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'primary':len(primary),'development':len(dev),'stress':1,'support':support},ensure_ascii=False,indent=2))
