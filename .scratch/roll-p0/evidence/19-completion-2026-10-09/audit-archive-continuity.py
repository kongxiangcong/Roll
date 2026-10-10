"""Coverage-only comparison of public quote dates against archived SSE calendars.

Never constructs labels, opens a runtime database, or grants source qualification.
Calendar literals are read with AST; no ledger or RuleCalendar is instantiated.
"""
import ast
from datetime import date, timedelta, datetime, timezone
import hashlib
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
RULES = ROOT / 'backend/src/roll/market/rules.py'
REFERENCE = RULES.parent / 'reference'
source = RULES.read_bytes()
values = {}
for node in ast.parse(source.decode('utf-8')).body:
    if isinstance(node, ast.Assign):
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id in {
                'SSE_HISTORICAL_HOLIDAYS', 'SSE_CALENDAR_CORRECTIONS'
            }:
                values[target.id] = ast.literal_eval(node.value)
holidays = values['SSE_HISTORICAL_HOLIDAYS']
corrections = values['SSE_CALENDAR_CORRECTIONS']
analysis_path = OUT / 'sina-archive-quote-analysis.json'
quotes = json.loads(analysis_path.read_bytes())['quotes']
dates = sorted({q['quote']['business_date'] for q in quotes})
years = {date.fromisoformat(day).year for day in dates}
sources = {s['id']: s for s in json.loads((REFERENCE / 'sources.json').read_bytes())}
calendar_sources = []
ids = {f'sse-calendar-{year}' for year in years}
ids.update(sid for year in years for _, _, sid in corrections.get(year, []))
for identifier in sorted(ids):
    metadata = sources[identifier]
    path = REFERENCE / metadata['file']
    content = path.read_bytes()
    assert hashlib.sha256(content).hexdigest() == metadata['sha256'], identifier
    calendar_sources.append({'id': identifier, 'sha256': metadata['sha256'],
                             'bytes': len(content), 'file': str(path)})


def trading(day):
    if day.year not in holidays:
        raise ValueError('UNSUPPORTED_CALENDAR_YEAR')
    ranges = list(holidays[day.year]) + [(a, b) for a, b, _ in corrections.get(day.year, [])]
    closed = any(date.fromisoformat(f'{day.year}-{a}') <= day <=
                 date.fromisoformat(f'{day.year}-{b}') for a, b in ranges)
    return day.weekday() < 5 and not closed


def next_day(day):
    candidate = day + timedelta(days=1)
    while not trading(candidate):
        candidate += timedelta(days=1)
    return candidate


def coverage(selected):
    selected = sorted({date.fromisoformat(day) for day in selected})
    runs = []
    for day in selected:
        if not trading(day):
            raise ValueError('QUOTE_BUSINESS_DATE_NOT_A_VERIFIED_SESSION')
        if runs and next_day(runs[-1][-1]) == day:
            runs[-1].append(day)
        else:
            runs.append([day])
    return {'unique_dates': len(selected),
            'longest_consecutive_sessions': max(map(len, runs), default=0),
            'runs': [[day.isoformat() for day in run] for run in runs]}


nominal = [q['quote']['business_date'] for q in quotes
           if q['quote']['completion_class'] == 'AFTER_NOMINAL_CLOSE_NOT_CALENDAR_QUALIFIED']
result = {'checked_at': datetime.now(timezone.utc).isoformat(),
          'analysis_sha256': hashlib.sha256(analysis_path.read_bytes()).hexdigest(),
          'calendar_code_canonical_lf_sha256': hashlib.sha256(source.replace(b'\r\n', b'\n')).hexdigest(),
          'calendar_sources': calendar_sources, 'all_quotes': coverage(dates),
          'after_nominal_close_only': coverage(nominal),
          'required_lookback_rows': 21,
          'basis': 'Calendar-date coverage only; nominal quote clock is not complete-bar, risk-state or historical-publication proof',
          'qualification': 'NONE', 'labels_computed': False, 'models_fitted': False,
          'sealed_read': False, 'runtime_database_read': False}
(OUT / 'archive-continuity.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n',
                                           encoding='utf-8', newline='\n')
print(json.dumps({k: {a: b for a, b in result[k].items() if a != 'runs'}
                  for k in ['all_quotes', 'after_nominal_close_only']}))
