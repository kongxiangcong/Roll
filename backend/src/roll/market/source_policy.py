"""Purpose-specific routing. Explicit supplier choices never imply fallback consent."""
import json
import os
import time
from datetime import datetime, timedelta, timezone

from roll.accounts.ledger import encode, now

VERSION = 'official-first-v1'
FIELDS = {'DAILY': 'daily_source', 'QUOTE': 'quote_source', 'ADJUSTMENTS': 'adjustment_source'}
CHAINS = {
    'DAILY': ['FUYAO', 'EASTMONEY', 'BAOSTOCK', 'SOHU', 'TENCENT'],
    'BACKGROUND_DAILY': ['FUYAO', 'TENCENT'],
    'QUOTE': ['SINA', 'TENCENT', 'FUYAO'],
    'ADJUSTMENTS': ['FUYAO', 'EASTMONEY', 'BAOSTOCK'],
}


def describe():
    return dict(version=VERSION, default=os.environ.get('ROLL_DATA_SOURCE_POLICY', 'LEGACY'),
                chains=CHAINS, research=['MIAOXIANG', 'FUYAO_REFERENCE', 'ISSUER_ORIGINAL_OR_EXISTING_PUBLIC_COLLECTOR'],
                comparison='OPT_IN_SAME_DATE_ADJUSTMENT_UNIT; INDEPENDENCE_UNPROVEN',
                quote_limit='FUYAO_PER_INSTRUMENT_TIME_UNKNOWN', cooldown_seconds=300)


def resolve(command):
    official = os.environ.get('ROLL_DATA_SOURCE_POLICY', 'LEGACY') == 'OFFICIAL_FIRST'
    routing = {}
    for group, field in FIELDS.items():
        value = getattr(command, field)
        if value == 'AUTO' or (official and field not in command.model_fields_set):
            chain = CHAINS['BACKGROUND_DAILY' if group == 'DAILY' and command.purpose == 'BACKGROUND' else group]
            routing[group] = chain
    return routing


def health(store, provider, reason=None):
    with store.ledger.connection() as db:
        db.execute('CREATE TABLE IF NOT EXISTS data_provider_health(provider TEXT PRIMARY KEY,value TEXT NOT NULL)')
        if reason:
            value = dict(provider=provider, reason=reason, checked_at=now(),
                         retry_after=(datetime.now(timezone.utc)+timedelta(seconds=300)).isoformat())
            db.execute('INSERT OR REPLACE INTO data_provider_health VALUES(?,?)', (provider, encode(value)))
            return value
        row = db.execute('SELECT value FROM data_provider_health WHERE provider=?', (provider,)).fetchone()
    value = json.loads(row[0]) if row else None
    return value if value and datetime.fromisoformat(value['retry_after']) > datetime.now(timezone.utc) else None


def usable(facts, request, instrument, group):
    rows = [f for f in facts if f['instrument'] == instrument and f['group'] == group
            and not f.get('errors') and not f.get('missing_required_fields')]
    rows = [f for f in rows if all(f.get(field.split('.')[-1]) is not None
            for field in request['required_fields'] if '.' not in field or field.split('.')[0] == group)]
    if group == 'QUOTE':
        return any(f.get('last') is not None and f.get('upstream_at') for f in rows)
    if group == 'DAILY':
        variants = {'RAW'} if request['purpose'] == 'BACKGROUND' else {'RAW', 'FORWARD_CURRENT_VERSION'}
        days=[{f.get('trade_date') for f in rows if f.get('adjustment')==variant} for variant in sorted(variants)]
        return all(days) and all(day_set==days[0] for day_set in days)
    return bool(rows)


def compare(before, after):
    checks = []
    keyed = {(f['instrument'], f['group'], f.get('trade_date'), f.get('adjustment')): f for f in before}
    for other in after:
        key = (other['instrument'], other['group'], other.get('trade_date'), other.get('adjustment'))
        first = keyed.get(key)
        if not first:
            continue
        aligned = (not first.get('errors') and not other.get('errors') and
                   first.get('currency') == other.get('currency') and first.get('currency') is not None and
                   (other['group'] == 'DAILY' and other.get('trade_date') is not None or
                    other['group'] == 'QUOTE' and first.get('upstream_at') == other.get('upstream_at') and other.get('upstream_at') is not None))
        fields = ['open', 'high', 'low', 'close'] if other['group'] == 'DAILY' else ['last']
        from decimal import Decimal
        tolerances={field:'.01' for field in fields}
        if first.get('volume_unit')==other.get('volume_unit')=='SHARE':
            fields+=['volume_shares','amount_yuan']
            tolerances.update(volume_shares='0',amount_yuan='.01')
        compared_fields=[field for field in fields if first.get(field) is not None and other.get(field) is not None]
        differences = [field for field in compared_fields
                       if abs(Decimal(first[field])-Decimal(other[field])) > Decimal(tolerances[field])]
        checks.append(dict(instrument=other['instrument'], group=other['group'], trade_date=other.get('trade_date'),
                           adjustment=other.get('adjustment'), basis_raw_hashes=[first['raw_hash'], other['raw_hash']],
                           result='NOT_COMPARABLE' if not aligned else 'DIFFERENT' if differences else 'MATCHED_AVAILABLE_PRICES',
                           differing_fields=differences, independence='UNPROVEN',
                           compared_fields=compared_fields,absolute_tolerances=tolerances,
                           meaning='Reference comparison only; matching prices do not establish PIT or independent production'))
    return checks


def complete(store, request, run, facts, archives, coverage, *, deadline, cancel_event,
             total_bytes, total_decoded_bytes, limits, collection_source_policy):
    """Try each allowed alternate once, sharing the original request's total budgets."""
    from roll.market.evidence import DataRequest
    routing = request.get('source_routing', {})
    run['source_attempts'] = []
    run['source_comparisons'] = []
    for instrument in request['instruments']:
        if instrument.startswith('BSE:'):
            continue  # No adapted supplier mapping; preserve native scope gaps.
        for group, chain in routing.items():
            if group not in request['groups']:
                continue
            original = [f for f in facts if f['instrument'] == instrument and f['group'] == group]
            ready = usable(facts, request, instrument, group)
            compared = False
            for provider in chain[1:]:
                if ready and (not request.get('compare_sources') or compared or group not in {'DAILY', 'QUOTE'}):
                    break
                calls = sum(t.get('network_calls', 1) for t in run['tools'])
                remaining = request['max_calls']-calls
                if remaining < (2 if provider == 'BAOSTOCK' else 1) or time.monotonic() >= deadline or (cancel_event and cancel_event.is_set()):
                    break
                if total_bytes >= limits['max_total_bytes'] or total_decoded_bytes >= limits['max_total_decoded_bytes']:
                    break
                payload = {name: request[name] for name in DataRequest.model_fields if name in request}
                payload.update(instruments=[instrument], groups=[group], research_source='ORIGINAL', compare_sources=False,
                               max_calls=remaining, timeout_seconds=max(1, int(deadline-time.monotonic())),
                               required_fields=[f for f in request['required_fields'] if '.' not in f or f.split('.')[0] == group],
                               baostock_auth_mode='PUBLIC')
                # Materialize all source fields: no environment-driven recursion.
                for routed_group, field in FIELDS.items():
                    payload[field] = provider if routed_group == group else request[field]
                child_request = store.request(DataRequest(**payload))
                child = store.retrieve(child_request['request_id'], cancel_event=cancel_event,
                                       collection_source_policy=collection_source_policy,
                                       acquisition_limits={**limits, 'deadline': deadline,
                                           'max_total_bytes': limits['max_total_bytes']-total_bytes,
                                           'max_total_decoded_bytes': limits['max_total_decoded_bytes']-total_decoded_bytes})
                snapshot = store.get('market_evidence_snapshots', child['snapshot_id'])
                run['source_attempts'].append(dict(provider=provider, instrument=instrument, group=group,
                    request_id=child_request['request_id'], run_id=child['run_id'], status=child['status'], gaps=child['gaps'],
                    role='COMPARISON' if ready else 'FALLBACK'))
                run['tools'].extend({**tool, 'child_run_id': child['run_id']} for tool in child['tools'])
                total_bytes += child.get('retrieved_bytes', 0)
                total_decoded_bytes += child.get('retrieved_decoded_bytes', 0)
                archives.extend(snapshot['archives'])
                coverage.extend(snapshot['coverage'])
                incoming = snapshot['facts']
                run['source_comparisons'].extend(compare(original, incoming))
                if ready:
                    compared = bool(incoming)
                elif usable(incoming, request, instrument, group):
                    facts[:] = [f for f in facts if not (f['instrument'] == instrument and f['group'] == group)] + incoming
                    recovered = [g for g in run['gaps'] if g['instrument'] == instrument and g['group'] == group]
                    run['source_attempts'][-1]['resolved_primary_gaps'] = recovered
                    run['gaps'][:] = [g for g in run['gaps'] if g not in recovered]
                    ready = True
                elif not original and incoming:
                    # Retain partial truth (e.g. RAW-only Sohu) without claiming a complete group.
                    facts.extend(incoming)
                    original = incoming
            if not ready:
                run['gaps'].append(dict(instrument=instrument,group=group,code='AUTO_GROUP_INCOMPLETE',
                    reason='No complete usable variant set within original shared budget; partial source facts retained'))
    return total_bytes, total_decoded_bytes
