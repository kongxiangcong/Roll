"""Freeze existing, exposed agent labels; no inference or new source acquisition."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from collections import Counter

out = Path(__file__).resolve().parent
assert not (out / 'frozen-dataset.json').exists()
base = out.parent
labels = []
sources = {}
for name in ('labels-120.json', 'labels-holdout-30.json'):
    body = (base / name).read_bytes()
    sources[name] = hashlib.sha256(body).hexdigest()
    labels.extend(json.loads(body)['items'])

# Conservative manual event families, reviewed from all 150 titles before new inference.
# Repeated reporting of the same half-year earnings is one event, even when price
# movement, analyst commentary, a roundup or a later article reuses that event.
families = {
    '2026H1-results-and-recaps': [15,16,18,19,21,22,23,32,33,35,36,37,38,39,40,41,42,43,45,46,47,48,49,50,51,52,53,54,55,56,58,59,60,61,62,63,67,120,133],
    '2027-2029-related-party-contract': [0,1,34,64],
    'secretary-departure-20260831': [24,25,29],
    'copper-foil-spinoff-and-listing-recaps': [9,26,27,72,101],
    'same-etf-demand-story-20260909': [130,131],
}
membership = {}
for family, indexes in families.items():
    for index in indexes:
        assert index not in membership
        membership[index] = family
boundary = '2026-09-16'
rows = []
for item in labels:
    row = dict(item)
    row['group_id'] = membership.get(row['index'], 'market-session-' + row['date'][:10])
    # Non-market corporate facts have a distinct disclosed event identity.
    if row['index'] in (2,3,6,11,12,14,20,28,74,138):
        row['group_id'] = 'corporate-event-' + str(row['index'])
    row['split'] = 'DEVELOPMENT' if row['date'][:10] < boundary else 'HOLDOUT'
    row['input_sha256'] = hashlib.sha256((row['title'] + '\n' + (row['summary'] or '')).encode()).hexdigest()
    rows.append(row)
development_groups = {row['group_id'] for row in rows if row['split'] == 'DEVELOPMENT'}
excluded = []
included = []
for row in rows:
    if row['split'] == 'HOLDOUT' and row['group_id'] in development_groups:
        excluded.append({**row, 'exclusion': 'LATER_RECAP_OF_DEVELOPMENT_EVENT'})
    else:
        included.append(row)
assert len(included) >= 120
assert not ({row['group_id'] for row in included if row['split']=='DEVELOPMENT'} & {row['group_id'] for row in included if row['split']=='HOLDOUT'})
summary = {}
for split in ('DEVELOPMENT', 'HOLDOUT'):
    subset = [row for row in included if row['split']==split]
    summary[split] = {'rows': len(subset), 'event_groups': len({row['group_id'] for row in subset}), 'support': dict(Counter(row['label'] for row in subset)), 'date_min': min(row['date'] for row in subset), 'date_max': max(row['date'] for row in subset)}
result = {'frozen_at': datetime.now(timezone.utc).isoformat(), 'source_sha256': sources, 'boundary': boundary, 'summary': summary, 'included': included, 'excluded': excluded,
    'label_origin': 'Inherited non-independent agent title/summary labels; all previously exposed to Erlangshen and its developer. No fresh independent labels. Not used to train this candidate.',
    'grouping': 'Conservative agent-reviewed event families and shared daily market sessions; later recaps crossing the time boundary embargoed. Groups may contain different relevance labels depending on text role. Grouping is not an independently audited ontology.',
    'limitations': ['SAME_UPSTREAM_HEADLINES_ONLY', 'NON_INDEPENDENT_PREVIOUSLY_EXPOSED_LABELS', 'LOW_UNIQUE_EVENT_SUPPORT', 'NO_VERIFIED_CORRECTION_PAIR', 'MODEL_TRAINING_CUTOFF_UNKNOWN']}
(out / 'frozen-dataset.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'included': len(included), 'excluded': len(excluded), 'summary': summary}, ensure_ascii=False, indent=2))
