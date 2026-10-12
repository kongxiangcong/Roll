"""Verify WorkBuddy's finite public delivery and append a native host snapshot.

Uses the host archive writer without starting workers, recovery or migrations.
The live API registers the committed snapshot; repeated syncs reuse stable IDs.
"""
import argparse
import hashlib
import json
from datetime import date
from decimal import Decimal
from io import BytesIO
from pathlib import Path, PurePosixPath
from uuid import NAMESPACE_URL, uuid5
import zipfile

import httpx
import pyarrow as pa
import pyarrow.parquet as pq

from roll.accounts.ledger import Ledger, encode, now
from roll.market.evidence import EvidenceStore
from roll.market.rules import REFERENCE, SSE_HISTORICAL_HOLIDAYS, SSE_CALENDAR_CORRECTIONS

EXPECTED_ZIP = '9306bef06871062f610c6e3b185a5c68686bc043ba4e1adff9fc124bdcebe7ba'
PREVIOUS_ZIP = '03f6011f8fc7f899f5041a71171844a36cddaab610efa74be8da38d7ee2d7fe5'
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PACKAGE = ROOT / '.scratch/roll-p0/evidence/19-data-request-2026-10-09/ticket19-data-delivery'


def sha(body):
    return hashlib.sha256(body).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def verify(package):
    package = package.resolve()
    zip_body = package.with_suffix('.zip').read_bytes()
    require(sha(zip_body) == EXPECTED_ZIP, 'Unexpected delivery ZIP')
    with zipfile.ZipFile(BytesIO(zip_body)) as bundle:
        require(bundle.testzip() is None, 'ZIP CRC failure')
        prefix = 'ticket19-data-delivery/'
        members = [n for n in bundle.namelist() if not n.endswith('/')]
        require(all(n.startswith(prefix) for n in members), 'ZIP root mismatch')
        names = [n.removeprefix(prefix) for n in members]
        require(len(names) == len(set(names)), 'Duplicate ZIP member')
        zip_contents = {n:bundle.read(prefix+n) for n in names}
    manifest_body = zip_contents['manifest.json']
    manifest = json.loads(manifest_body)
    require(manifest['schema_version'] == 'ticket19-external-evidence-v1', 'Unknown schema')
    require(manifest['instrument'] == 'SSE:600362', 'Wrong instrument')
    contents = {'manifest.json': manifest_body}
    parsed = {}
    for item in manifest['files']:
        name = item['path']
        path = PurePosixPath(name)
        require(not path.is_absolute() and '..' not in path.parts and ':' not in name and '\\' not in name, 'Unsafe path')
        require(name not in contents, 'Duplicate manifest path')
        body = zip_contents[name]
        require(len(body) == item['bytes'] and sha(body) == item['sha256'], f'Bad original: {name}')
        contents[name] = body
        if name.endswith('.jsonl'):
            rows = [json.loads(line) for line in body.decode('utf-8').splitlines() if line.strip()]
            require(len(rows) == item['record_count'], f'Wrong count: {name}')
            parsed[name] = rows
        elif name.endswith('.json') and not name.startswith('evidence/raw/'):
            parsed[name] = json.loads(body)
    unpacked_extras = sorted({p.relative_to(package).as_posix() for p in package.rglob('*') if p.is_file()} - set(contents) - {'README.md'})
    require(set(names) - set(contents) == {'README.md'} and not set(contents) - set(names), 'ZIP/manifest paths differ')
    contents['README.md'] = zip_contents['README.md']
    sources = {r['source_id'] for r in parsed['evidence/sources.jsonl']}
    index_rows = parsed['evidence/evidence_index.jsonl']
    index = {r['evidence_id']: dict(r) for r in index_rows}
    require(len(index) == len(index_rows), 'Duplicate evidence ID')
    host_sources = json.loads((REFERENCE/'sources.json').read_text(encoding='utf-8'))
    supplemental = []
    for r in index.values():
        if r['relative_path'] not in contents:
            candidates = [s for s in host_sources if r['relative_path'] == f'backend/src/roll/market/reference/{s["file"]} (project-archived original; not shipped in this package)']
            require(len(candidates) == 1, 'Unresolved external evidence path')
            s = candidates[0];body = (REFERENCE/s['file']).read_bytes()
            require(sha(body) == s['sha256'] and len(body) == s['bytes'], 'Host supplemental original corrupt')
            r.update(relative_path='host-reference/'+s['file'],sha256=s['sha256'],bytes=s['bytes'],host_resolution='HOST_SUPPLEMENT_NOT_DELIVERED_IN_ZIP')
            contents[r['relative_path']] = body
            supplemental.append({'evidence_id':r['evidence_id'],**s})
        body = contents[r['relative_path']]
        require(sha(body) == r['sha256'] and len(body) == r['bytes'], 'Evidence byte mismatch')
    for name, rows in parsed.items():
        if not name.startswith('data/'):
            continue
        ids = [r['record_id'] for r in rows]
        require(len(ids) == len(set(ids)), f'Duplicate record ID: {name}')
        for r in rows:
            require(r['source_id'] in sources, 'Unknown source')
            require(all(ref['evidence_id'] in index and ref.get('locator') for ref in r['evidence_refs']), 'Broken evidence reference')
    bars = parsed['data/daily_bars.jsonl']
    require(len({(r['source_id'],r['trade_date']) for r in bars}) == len(bars), 'Duplicate source/date')
    raw_cache = {}
    for r in bars:
        ref = index[r['evidence_refs'][0]['evidence_id']]
        if ref['sha256'] not in raw_cache:
            if r['source_id']=='SRC-SOHU':
                payload = json.loads(contents[ref['relative_path']].decode('gbk'))
                require(payload[0]['code'] == 'cn_600362', 'Daily raw object mismatch')
                raw_cache[ref['sha256']] = {v[0]: v for v in payload[0]['hq']}
            else:
                require(r['source_id']=='SRC-WIND','Unknown daily source')
                payload=json.loads(contents[ref['relative_path']])['data']
                require([c['name'] for c in payload['columns'][:7]]==['TIME','OPEN','MATCH','HIGH','LOW','TURNOVER','VOLUME'],'Wind columns changed')
                require(payload['unit']['VOLUME 单位：']=='股' and payload['unit']['TURNOVER 单位：']=='元','Wind unit mismatch')
                require(len({v[0][:10] for v in payload['rows']})==len(payload['rows']),'Duplicate Wind date')
                raw_cache[ref['sha256']]={v[0][:10]:v for v in payload['rows']}
        original = raw_cache[ref['sha256']][r['trade_date']]
        mapping=[('open',1,1),('close',2,1),('low',5,1),('high',6,1),('volume_shares',7,100),('amount_yuan',8,10000)] if r['source_id']=='SRC-SOHU' else [('open',1,1),('close',2,1),('low',4,1),('high',3,1),('volume_shares',6,1),('amount_yuan',5,1)]
        for field, column, multiplier in mapping:
            require((r[field] is None and original[column] is None) or (r[field] is not None and original[column] is not None and Decimal(r[field])==Decimal(original[column])*multiplier),f'Daily original mismatch {r["trade_date"]}/{field}')
        require('2015-10-01'<=r['trade_date']<='2023-12-31','Daily date outside collection/context scope')
        require(r['adjustment'] == 'RAW' and r['evidence_class'] == 'CURRENT_QUERY_ONLY', 'Unsupported price/version basis')
        if r['row_kind']=='SUSPENSION_PLACEHOLDER':
            require(r['source_id']=='SRC-WIND' and '2016-02-16'<=r['trade_date']<'2016-02-26' and r['volume_shares'] is None and r['amount_yuan'] is None,'Bad suspension placeholder')
    calendars = parsed['data/trading_calendar.jsonl']
    require(len({r['calendar_date'] for r in calendars}) == len(calendars), 'Duplicate calendar date')
    corrections = []
    sessions = []
    for r in calendars:
        d = date.fromisoformat(r['calendar_date'])
        ranges = SSE_HISTORICAL_HOLIDAYS[d.year] + [(a,b) for a,b,_ in SSE_CALENDAR_CORRECTIONS.get(d.year, [])]
        trading = d.weekday() < 5 and not any(f'{d.year}-{a}' <= d.isoformat() <= f'{d.year}-{b}' for a,b in ranges)
        if trading != r['is_trading_day']:
            corrections.append({'date':d.isoformat(), 'delivered_is_trading_day':r['is_trading_day'], 'host_is_trading_day':trading})
        if trading:
            sessions.append(d.isoformat())
    require(corrections == [], 'Unexpected calendar conflict')
    source = next(s for s in host_sources if s['id'] == 'sse-calendar-2019')
    correction_body = (REFERENCE/source['file']).read_bytes()
    require(sha(correction_body) == source['sha256'], 'Calendar authority corrupt')
    contents['host-calendar-authority.html'] = correction_body
    revision = next(s for s in host_sources if s['id'] == 'sse-calendar-2019-labor-revision')
    revision_body = (REFERENCE/revision['file']).read_bytes()
    require(sha(revision_body) == revision['sha256'], 'Calendar revision authority corrupt')
    contents['host-reference/'+revision['file']] = revision_body
    dates = {r['trade_date'] for r in bars}
    observed_dates={r['trade_date'] for r in bars if r['row_kind']=='OBSERVED_BAR'}
    placeholders=sorted({r['trade_date'] for r in bars if r['row_kind']=='SUSPENSION_PLACEHOLDER'})
    requested = [r for r in bars if '2016-01-01' <= r['trade_date'] <= '2023-12-31']
    missing = [d for d in sessions if '2016-01-01' <= d <= '2023-12-31' and d not in dates]
    run = longest = candidates = 0
    for d in sessions:
        run = run + 1 if d in observed_dates else 0
        longest = max(longest, run)
        candidates += int(run >= 21 and '2016-01-01' <= d <= '2023-12-31')
    actions = parsed['data/corporate_actions.jsonl']
    states = parsed['data/security_status.jsonl']
    wind_actions=[r for r in actions if r['source_id']=='SRC-WIND']
    if wind_actions:
        action_ref=index[wind_actions[0]['evidence_refs'][0]['evidence_id']]
        table=json.loads(contents[action_ref['relative_path']],parse_float=Decimal)['response']['data']['data'][0]
        columns=[c['name'] for c in table['columns']]
        originals={r[columns.index('内地股票分红报告期')]:r for r in table['rows']}
        action_fields={'announcement_date':'内地股票分红实施公告日','ex_date':'内地股票分红除权除息日','payment_date':'内地股票分红派息日',
                       'share_base_date':'内地股票分红股本基准日','base_shares_wan':'2016到2023年内地股票分红基准股本',
                       'gross_cash_per_eligible_share':'2016到2023年内地股票分红税前每股派息','bonus_share_ratio':'2016到2023年内地股票分红送股比例',
                       'capitalization_ratio':'2016到2023年内地股票分红转增比例'}
        for r in wind_actions:
            original=originals[r['report_period']]
            for field,column in action_fields.items():
                value=original[columns.index(column)]
                require(r[field]==value or (r[field] is not None and value is not None and str(r[field])==str(value)),f'Wind action original mismatch: {r["record_id"]}/{field}')
    cninfo_actions={r['ex_date']:r for r in actions if r['source_id']=='SRC-CNINFO' and r['action_type']=='CASH_DIVIDEND'}
    announcement_disagreements=[]
    for r in wind_actions:
        other=cninfo_actions.get(r['ex_date'])
        if other and r['announcement_date']!=other['announcement_date']:
            announcement_disagreements.append({'ex_date':r['ex_date'],'wind_report_period':r['report_period'],'wind_announcement_date':r['announcement_date'],'cninfo_announcement_date':other['announcement_date']})
    sohu={r['trade_date']:r for r in bars if r['source_id']=='SRC-SOHU'}
    wind={r['trade_date']:r for r in bars if r['source_id']=='SRC-WIND' and r['row_kind']=='OBSERVED_BAR'}
    overlap=sorted(sohu.keys()&wind.keys());strict=[];declared=[];ohlc_mismatch=[];exact=0
    for d in overlap:
        differences={k:format(Decimal(wind[d][k])-Decimal(sohu[d][k]),'f') for k in ['open','close','low','high','volume_shares','amount_yuan']}
        exact+=all(Decimal(v)==0 for v in differences.values())
        if any(Decimal(differences[k])!=0 for k in ['open','close','low','high']):ohlc_mismatch.append(d)
        detail={'trade_date':d,'differences_wind_minus_sohu':differences,'values':{k:{'sohu':sohu[d][k],'wind':wind[d][k]} for k in ['volume_shares','amount_yuan']}}
        if abs(Decimal(differences['volume_shares']))>100 or abs(Decimal(differences['amount_yuan']))>100:strict.append(detail)
        if abs(Decimal(differences['volume_shares']))>100 or abs(Decimal(differences['amount_yuan']))>10000:declared.append(detail)
    delivered_comparison=parsed['reports/cross_source_validation.json']
    require(len(overlap)==delivered_comparison['overlapping_observed_dates'] and [r['trade_date'] for r in declared]==delivered_comparison['mismatch_dates'],'Cross-source report mismatch')
    comparison={'overlapping_observed_dates':len(overlap),'ohlc_mismatch_dates':ohlc_mismatch,'six_fields_exact_equal_dates':exact,
                'delivery_tolerance':{'volume_shares':'100','amount_yuan':'10000'},'delivery_tolerance_agreement_dates':len(overlap)-len(declared),
                'delivery_tolerance_mismatch_details':declared,'host_precision_tolerance':{'volume_shares':'100','amount_yuan':'100'},
                'host_precision_mismatch_details':strict,'host_precision_mismatch_count':len(strict),
                'basis':'Sohu amount is displayed to 0.01 TEN_THOUSAND_CNY = 100 CNY. Tolerance agreement is not exact equality; differences are retained without choosing a source.'}
    requested_sessions=sum('2016-01-01'<=d<='2023-12-31' for d in sessions)
    reported=parsed['reports/coverage.json']
    actuals={'daily_row_count_requested_scope':len(requested),'unique_business_dates':len(dates),
             'unique_business_dates_requested_scope':len({r['trade_date'] for r in requested}),
             'calendar_coverage.trading_days_in_requested_scope':requested_sessions,
             'missing_bar_dates':missing,'corporate_action_coverage_by_type.CASH_DIVIDEND.delivered_count':sum(r.get('action_type')=='CASH_DIVIDEND' for r in actions)}
    report_differences=[]
    for field,value in actuals.items():
        old=reported
        for part in field.split('.'):old=old.get(part) if isinstance(old,dict) else None
        if old!=value:report_differences.append({'field':field,'reported':old,'host_recomputed':value})
    out_of_scope_actions=[r['record_id'] for r in actions if r.get('action_type')=='CASH_DIVIDEND' and r.get('ex_date') and not '2016-01-01'<=r['ex_date']<='2023-12-31']
    audit = {'zip_sha256':EXPECTED_ZIP, 'zip_bytes':len(zip_body), 'manifest_files_verified':len(manifest['files']),
             'supersedes_delivery_zip_sha256':PREVIOUS_ZIP,
             'hash_length_mismatches':0, 'daily_original_value_mismatches':0,
             'manifest_omitted_files_verified_against_zip':['README.md'],
             'unpacked_extra_files_excluded_from_this_delivery':unpacked_extras,
             'host_supplemented_missing_calendar_originals':supplemental,
             'record_counts':{n:len(v) for n,v in parsed.items() if n.endswith('.jsonl')},
             'requested_daily_rows':len(requested), 'context_daily_rows':len(bars)-len(requested),
             'source_daily_row_counts':{s:sum(r['source_id']==s for r in bars) for s in sorted({r['source_id'] for r in bars})},
             'requested_observed_dates':len({r['trade_date'] for r in requested if r['row_kind']=='OBSERVED_BAR'}),
             'unique_business_dates':len(dates),'suspension_placeholder_dates':placeholders,
             'unexplained_missing_observed_dates':[d for d in sessions if '2016-01-01'<=d<='2023-12-31' and d not in observed_dates and d not in placeholders],
             'corrected_requested_exchange_sessions':sum('2016-01-01' <= d <= '2023-12-31' for d in sessions),
             'calendar_corrections':corrections, 'calendar_correction_authority':source,
             'calendar_revision_authority':revision,
             'missing_bar_dates':missing, 'suspension_explained_missing_dates':[d for d in missing if '2016-02-16' <= d < '2016-02-26'],
             'unexplained_missing_dates':[d for d in missing if not '2016-02-16' <= d < '2016-02-26'],
             'explicit_status_dates':sorted({r['trade_date'] for r in states if r.get('trade_date')}),
             'unknown_requested_status_date_count':sum('2016-01-01' <= d <= '2023-12-31' for d in sessions)-len({r['trade_date'] for r in states if r.get('trade_date')}),
             'cash_dividend_events':len({r['ex_date'] for r in actions if r.get('action_type')=='CASH_DIVIDEND'}),
             'cash_dividend_record_versions':sum(r.get('action_type') == 'CASH_DIVIDEND' for r in actions),
             'unique_cash_dividend_ex_dates':len({r['ex_date'] for r in actions if r.get('action_type')=='CASH_DIVIDEND'}),
             'out_of_requested_scope_action_record_ids':out_of_scope_actions,
             'dividend_announcement_date_disagreements':announcement_disagreements,
             'reported_coverage_discrepancies':report_differences,'cross_source_validation':comparison,
             'st_negative_basis':'Two query results from the SAME vendor; absence of a returned ST event and a scalar history-enabled name do not establish complete ST history or per-day NORMAL status.',
             'wind_clock_basis':'Delivered Wind received_at is date-at-midnight without a tool receipt clock in the shipped response. Preserve as reported, use actual host imported_at for current knowledge; never historical availability.',
             'longest_consecutive_exchange_session_run':longest, 'metadata_candidate_21_row_windows':candidates,
             'historical_point_in_time_proven':False, 'revision_chain_complete':False,
             'qualification':'BLOCKED', 'labels_calculated':False, 'training_performed':False, 'sealed_payloads_read':False}
    contents['host-verification.json'] = (json.dumps(audit,ensure_ascii=False,indent=2)+'\n').encode()
    contents['host-resolved-evidence-index.jsonl'] = ''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in index.values()).encode()
    contents['host-cross-source-validation.json']=(json.dumps(comparison,ensure_ascii=False,indent=2)+'\n').encode()
    contents['delivery.zip'] = zip_body
    return manifest, parsed, index, contents, audit


class ExistingLedger:
    """Use existing connection policy without bootstrap or recovery mutations."""
    connection = Ledger.connection

    def __init__(self, directory):
        self.path = directory.resolve() / 'roll.sqlite3'
        require(self.path.is_file(), 'Existing host database required')


class ArchiveWriter:
    archive = EvidenceStore.archive
    raw = EvidenceStore.raw

    def __init__(self, ledger):
        self.ledger = ledger
        self.directory = ledger.path.parent


def sync(directory, api, parsed, index, contents, audit, source_id='SRC-SOHU'):
    ledger = ExistingLedger(directory)
    writer = ArchiveWriter(ledger)
    with httpx.Client(base_url=api.rstrip('/'),timeout=60,trust_env=False) as client:
        response = client.get('/api/research/datasets'); response.raise_for_status()
        datasets = response.json()
        response = client.get('/api/research/protocols'); response.raise_for_status()
        protocols = response.json()
        previous_comparison={'previous_delivery_present':False}
        for previous in datasets:
            if previous['dataset_id']!='65e34799-6e46-49b7-bcee-f7955bce927d':continue
            response=client.get('/api/data/snapshots/'+previous['source_snapshot_id']);response.raise_for_status()
            old=response.json()
            require(old.get('external_delivery_zip_sha256')==PREVIOUS_ZIP,'Previous delivery identity mismatch')
            old_rows={r['record_id']:r for r in old['facts'] if r.get('source_id')=='SRC-SOHU' and r['group'] in {'DAILY','CONTEXT_DAILY'}}
            new_rows=[r for r in parsed['data/daily_bars.jsonl'] if r['source_id']=='SRC-SOHU']
            fields=['trade_date','open','close','low','high','volume_shares','amount_yuan','row_kind','adjustment','evidence_class']
            require(len(old_rows)==len(new_rows) and all(all(old_rows[r['record_id']][k]==r[k] for k in fields) for r in new_rows),'Previous Sohu values changed')
            old_day=next(r for r in old['facts'] if r['record_id']=='CAL-2018-12-31')
            new_day=next(r for r in parsed['data/trading_calendar.jsonl'] if r['record_id']=='CAL-2018-12-31')
            require(old_day['is_trading_day']==new_day['is_trading_day']==False,'Calendar correction differs from previous host')
            previous_comparison={'previous_delivery_present':True,'previous_dataset_id':previous['dataset_id'],
                                 'previous_daily_values_unchanged':len(new_rows),'calendar_2018_12_31_matches_previous_host':True,
                                 'old_dataset_and_archives_retained':True}
        before_manifests = {}
        for p in protocols:
            response = client.get(f'/api/research/protocols/{p["protocol_id"]}/attempt-manifest');response.raise_for_status()
            before_manifests[p['protocol_id']] = response.json()
        with ledger.connection() as db:
            require({r[0] for r in db.execute('SELECT id FROM research_datasets')} == {r['dataset_id'] for r in datasets}, 'API/database mismatch')
            require(not any(json.loads(r[0])['status'] == 'RUNNING' for r in db.execute('SELECT value FROM retrieval_runs')), 'Acquisition active; retry later')
            protected = {name:list(db.execute(f'SELECT * FROM {name} ORDER BY rowid')) for name in ['account_versions','account_events','account_audit','research_protocols','research_attempts','research_events','research_datasets']}
        require(source_id in audit['source_daily_row_counts'],'No daily records for source view')
        ids = {k:str(uuid5(NAMESPACE_URL, f'roll:workbuddy:{EXPECTED_ZIP}:{source_id}:{k}')) for k in ['request','run','snapshot']}
        with ledger.connection() as db:
            saved = db.execute('SELECT value FROM market_evidence_snapshots WHERE id=?',(ids['snapshot'],)).fetchone()
        if saved:
            snapshot = json.loads(saved[0])
            require(snapshot['external_delivery_zip_sha256'] == EXPECTED_ZIP, 'Stable ID mismatch')
            for original in snapshot['archives']+[snapshot['parquet']]:writer.raw(original['sha256'])
        else:
            archives = []
            refs = {}
            for name, body in contents.items():
                ref = writer.archive(body,'EXTERNAL_PUBLIC_DELIVERY',delivery_zip_sha256=EXPECTED_ZIP,delivery_path=name)
                refs[name] = ref
                if ref['sha256'] not in {r['sha256'] for r in archives}:archives.append(ref)
            acquired = now()
            corrections = {r['date']:r for r in audit['calendar_corrections']}
            precision_conflict_dates={r['trade_date'] for r in audit['cross_source_validation']['host_precision_mismatch_details']}
            facts = []
            for name, rows in parsed.items():
                if not name.startswith('data/'):
                    continue
                for row in rows:
                    fact = {**row, 'instrument':row.get('instrument'), 'available_at':acquired,
                            'received_at':row.get('received_at'), 'host_imported_at':acquired,
                            'raw_hash':refs[name]['sha256'], 'evidence_kind':'REAL_ACQUISITION',
                            'model_daily_input_allowed':False, 'limitations':['EXTERNAL_PUBLIC_COLLECTION_NOT_PIT_OR_TRAINING_ADMISSION']}
                    if name.endswith('daily_bars.jsonl'):
                        fact['group'] = 'DAILY' if row['source_id']==source_id else 'ALTERNATE_SOURCE_DAILY'
                        if not '2016-01-01'<=row['trade_date']<='2023-12-31':fact['group']='CONTEXT_DAILY'
                        if row['row_kind']=='SUSPENSION_PLACEHOLDER':fact['group']='SUSPENSION_PLACEHOLDER'
                        fact['volume_unit'] = 'SHARE'
                        if row['trade_date'] in precision_conflict_dates:
                            fact['limitations'].append('HOST_CROSS_SOURCE_AMOUNT_PRECISION_DIFFERENCE_UNRESOLVED')
                        if row['source_id']=='SRC-WIND':fact['received_at_basis']='REPORTED_DATE_AT_MIDNIGHT; PRECISE_TOOL_RECEIPT_NOT_PROVEN'
                    elif name.endswith('trading_calendar.jsonl'):
                        fact['group'] = 'CALENDAR'
                        if row['calendar_date'] in corrections:
                            fact.update(reported_is_trading_day=row['is_trading_day'],is_trading_day=corrections[row['calendar_date']]['host_is_trading_day'],
                                        host_correction=corrections[row['calendar_date']],host_correction_raw_hash=refs['host-calendar-authority.html']['sha256'])
                    elif name.endswith('security_status.jsonl'):
                        fact['group'] = 'STATUS' if row.get('trade_date') else 'STATUS_COVERAGE_NOTE'
                    elif name.endswith('corporate_actions.jsonl'):
                        fact['group'] = 'ADJUSTMENTS' if row['action_type'] == 'CASH_DIVIDEND' else 'EXTERNAL_ACTION_METADATA'
                        if row['action_type']=='CASH_DIVIDEND':
                            if not '2016-01-01'<=row['ex_date']<='2023-12-31':fact['group']='OUT_OF_SCOPE_ACTION_VERSION'
                            elif row['source_id']!=('SRC-WIND' if source_id=='SRC-WIND' else 'SRC-CNINFO'):fact['group']='ALTERNATE_ACTION_VERSION'
                    elif name.endswith('historical_rules.jsonl'):
                        fact['group'] = 'HISTORICAL_RULES'
                    else:
                        fact['group'] = 'REVISION_STATEMENT'
                    fact['original_evidence_hashes'] = [index[r['evidence_id']]['sha256'] for r in row['evidence_refs']]
                    facts.append(fact)
            buffer = BytesIO(); pq.write_table(pa.Table.from_pylist([{'payload':encode(f)} for f in facts]),buffer)
            parquet = writer.archive(buffer.getvalue(),'NORMALIZED_PARQUET',extension='parquet',adapter_version='ticket19-external-delivery-v1')
            # Reuse only the host's already registered identity; no account or list writes.
            identity = next(d['scope']['identity_context']['SSE:600362'] for d in datasets if 'SSE:600362' in d['scope']['instruments'])
            view_count=sum(f['group']=='DAILY' for f in facts)
            coverage = [{**audit,'instrument':'SSE:600362','group':'DAILY','source_id':source_id,'returned_rows':view_count,
                         'source_view_policy':'SOURCE_SPECIFIC_NO_PRIORITY; both source views preserve the full delivery; never merge two sources into one daily sequence',
                         'request_start':'2016-01-01','request_end':'2023-12-31','full_history_verified':False,
                         'delivery_reported_coverage':parsed['reports/coverage.json']}]
            gaps = parsed['reports/gaps.json']['gaps'] + parsed['reports/conflicts.json']['conflicts']
            gaps += [{'code':'HOST_CALENDAR_TRANSCRIPTION_CORRECTED',**r} for r in audit['calendar_corrections']]
            gaps += [{'code':'HOST_COVERAGE_REPORT_STALE',**r} for r in audit['reported_coverage_discrepancies']]
            gaps += [{'code':'HOST_CROSS_SOURCE_AMOUNT_PRECISION_DIFFERENCE',**r} for r in audit['cross_source_validation']['host_precision_mismatch_details']]
            request = {'request_id':ids['request'],'purpose':'RESEARCH','instruments':['SSE:600362'],
                       'groups':['DAILY','CALENDAR','STATUS','ADJUSTMENTS'],'start_date':'2016-01-01','end_date':'2023-12-31',
                       'identity_context':{'SSE:600362':identity},'created_at':acquired,'cutoff':acquired,
                       'origin':'USER_AUTHORIZED_EXTERNAL_PUBLIC_DELIVERY','external_delivery_zip_sha256':EXPECTED_ZIP,'external_source_view':source_id}
            run = {'run_id':ids['run'],'request_id':ids['request'],'snapshot_id':ids['snapshot'],'status':'PARTIAL',
                   'started_at':acquired,'finished_at':acquired,'gaps':gaps,'network_calls':0,
                   'external_delivery_zip_sha256':EXPECTED_ZIP,'evidence_kind':'REAL_ACQUISITION'}
            snapshot = {'snapshot_id':ids['snapshot'],'run_id':ids['run'],'request_id':ids['request'],
                        'facts':facts,'archives':archives,'parquet':parquet,'coverage':coverage,'observations':[],
                        'gaps':gaps,'requested_instruments':request['instruments'],'requested_groups':request['groups'],
                        'created_at':acquired,'requested_cutoff':acquired,'namespace':'HISTORICAL','evidence_kind':'REAL_ACQUISITION',
                        'formal_judgment':'DISABLED','adapter_version':'ticket19-external-delivery-v1',
                        'external_delivery_zip_sha256':EXPECTED_ZIP,'external_source_view':source_id,'host_verification':audit}
            with ledger.connection() as db:
                db.execute('BEGIN IMMEDIATE')
                db.execute('INSERT INTO data_requests VALUES(?,?)',(ids['request'],encode(request)))
                db.execute('INSERT INTO retrieval_runs VALUES(?,?,?)',(ids['run'],ids['request'],encode(run)))
                db.execute('INSERT INTO market_evidence_snapshots VALUES(?,?,?)',(ids['snapshot'],ids['run'],encode(snapshot)))
                db.commit()
        existing = next((d for d in datasets if d.get('source_run_id') == ids['run']),None)
        if existing:
            dataset = existing
        else:
            response = client.post('/api/research/datasets',json={'source_run_id':ids['run'],
                'basis':'用户授权同步WorkBuddy ticket19真实公开交付；SHA/逐行原体核对及官方日历校正；仅登记覆盖，PIT/窗口/训练仍BLOCKED'})
            response.raise_for_status();dataset = response.json()
        response = client.post(f'/api/data/runs/{ids["run"]}/replay')
        response.raise_for_status(); replay = response.json()
        require(replay['facts'] == snapshot['facts'] and replay['network_calls'] == 0,'Live replay mismatch')
        for pid, value in before_manifests.items():
            response = client.get(f'/api/research/protocols/{pid}/attempt-manifest');response.raise_for_status()
            require(response.json() == value,'Attempt budget/manifest changed')
        with ledger.connection() as db:
            for name, rows in protected.items():
                current = list(db.execute(f'SELECT * FROM {name} ORDER BY rowid'))
                if name == 'research_datasets':
                    current = [r for r in current if r[0] != dataset['dataset_id'] or existing]
                require(current == rows,f'Protected state changed: {name}')
            require(db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok','Database integrity failure')
        require(dataset['coverage']['session_count']==sum(r['source_id']==source_id and r['row_kind']=='OBSERVED_BAR' and '2016-01-01'<=r['trade_date']<='2023-12-31' for r in parsed['data/daily_bars.jsonl']),'Dataset count mismatch')
        require(dataset['training_readiness']['state'] == 'BLOCKED','Unexpected training admission')
        return {'data_directory':str(directory.resolve()),'dataset_id':dataset['dataset_id'],'source_run_id':ids['run'],
                'snapshot_id':ids['snapshot'],'external_source_view':source_id,'normalized_fact_rows':len(snapshot['facts']),
                'previous_delivery_comparison':previous_comparison,
                'unique_archived_files':len(snapshot['archives'])+1,'dataset_coverage':dataset['coverage'],
                'training_readiness':dataset['training_readiness'],'replay_network_calls':0,
                'account_and_old_research_state_unchanged':True,'attempt_manifests_unchanged':True,
                'database_integrity':'ok','idempotent_reuse':existing is not None,'audit':audit}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--package',type=Path,default=DEFAULT_PACKAGE)
    parser.add_argument('--data-dir',type=Path)
    parser.add_argument('--api',default='http://127.0.0.1:8010')
    parser.add_argument('--report',type=Path,required=True)
    args = parser.parse_args()
    _,parsed,index,contents,audit = verify(args.package)
    result = {'delivery_zip_sha256':EXPECTED_ZIP,'source_views':[sync(args.data_dir,args.api,parsed,index,contents,audit,source_id=s) for s in sorted(audit['source_daily_row_counts'])],'audit':audit} if args.data_dir else audit
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:result[k] for k in ['dataset_id','requested_daily_rows','context_daily_rows','database_integrity','idempotent_reuse'] if k in result},ensure_ascii=False))
    if 'source_views' in result:print(json.dumps([{'source':v['external_source_view'],'dataset_id':v['dataset_id'],'rows':v['dataset_coverage']['session_count'],'idempotent_reuse':v['idempotent_reuse'],'integrity':v['database_integrity']} for v in result['source_views']],ensure_ascii=False))


if __name__ == '__main__':
    main()
