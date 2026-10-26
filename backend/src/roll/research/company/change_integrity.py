"""Validate frozen context/change-set references at backup and recovery."""
import json
from decimal import Decimal, InvalidOperation
from datetime import datetime
from .calculator import SHANGHAI
from .service import verified, fingerprint, fail


def validate_changes(db, archives):
    names = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if 'company_research_change_sets' not in names:
        return

    def require(condition):
        if not condition:
            fail('RESEARCH_REFERENCE_INVALID', 'Research change set or context binding differs', 409)

    def records(table, key):
        return {r[0]: verified(json.loads(r[1])) for r in db.execute(f'SELECT {key},value FROM company_research_{table}')}

    snapshots = records('snapshots', 'snapshot_id')
    facts = records('facts', 'version_id')
    materials = records('materials', 'material_id')
    checks = records('checks', 'check_id')
    reviews = records('economic_reviews', 'review_id')
    valuations = records('valuations', 'valuation_id')
    valuation_inputs = records('valuation_inputs', 'version_id')
    models = records('operating_models', 'operating_model_id')
    inputs = records('inputs', 'input_id')
    for snapshot in snapshots.values():
        context = snapshot.get('context')
        if not context:
            continue
        archive = snapshot.get('context_archive')
        require(archive and archives.get(archive['sha256']) == archive and fingerprint(context) == archive['sha256'])
        require(snapshot['check_ids'] == [c['check_id'] for c in context['checks']])
        require(snapshot['quote_ids'] == [q['quote_id'] for q in context['quotes']])
        for check in context['checks']:
            require(checks.get(check['check_id']) == check and check['company_id'] == snapshot['company_id'] and check['status'] != 'RUNNING')
            require(check['finished_at'] <= context['bound_at'])
        for quote in context['quotes']:
            row = quote['row']
            listing = next((i for i in inputs[snapshot['input_id']]['payload']['company']['listings'] if i['listing_id'] == row['listing_id']), None)
            require(listing and listing['currency'] == row['currency'])
            try:
                stamp = datetime.fromisoformat(row['priced_at'])
                require(stamp.tzinfo is not None and stamp <= datetime.fromisoformat(context['bound_at']))
                day = stamp.astimezone(SHANGHAI).date().isoformat()
                require(row['shares_as_of'] == day and row['price_basis'] in {'RAW_NOMINAL', 'ADJUSTED', 'UNKNOWN'})

                def match(number, identifiers, unit, currency, scope):
                    require(len(identifiers) == 1)
                    fact = facts.get(identifiers[0])
                    require(fact and fact['kind'] in {'DISCLOSED', 'DERIVED'} and fact['value_type'] == 'NUMBER')
                    require(Decimal(str(number)) == Decimal(fact['value']) and Decimal(str(number)).is_finite() and Decimal(str(number)) > 0)
                    require((unit, currency, scope, day, day) == tuple(fact[k] for k in ['unit', 'currency', 'scope', 'period_start', 'period_end']))
                    require(fact['kind'] != 'DERIVED' or fact.get('derivation'))
                    return fact

                match(row['shares'], row['share_refs'], row['shares_unit'], None, row['listing_id'])
                price = match(row['price'], row['price_refs'], 'price_per_share', row['currency'], row['listing_id'])
                require(row['price_basis'] != 'RAW_NOMINAL' or price['metric'] == 'raw_nominal_price')
                if row.get('fx'):
                    fx = row['fx']
                    require(fx['from_currency'] == row['currency'] and fx['as_of'] == day)
                    match(fx['rate'], fx['source_refs'], 'ratio', None, fx['from_currency'] + '->' + fx['to_currency'])
            except (KeyError, ValueError, TypeError, InvalidOperation):
                require(False)
            refs = quote['row']['share_refs'] + quote['row']['price_refs'] + quote['row'].get('fx', {}).get('source_refs', [])
            require(set(refs) == {f['version_id'] for f in quote['facts']})
            for fact in quote['facts']:
                require(facts.get(fact['version_id']) == fact and fact['company_id'] == snapshot['company_id'] and fact['consumable_at'] <= context['bound_at'])
            require(quote['available_at'] == max(f['consumable_at'] for f in quote['facts']))
            require({m['material_id'] for m in quote['materials']} == {f['material_id'] for f in quote['facts']})
            for material in quote['materials']:
                require(materials.get(material['material_id']) == material and material['company_id'] == snapshot['company_id'])
    for value in records('change_sets', 'change_set_id').values():
        archive = value['archive']
        require(archives.get(archive['sha256']) == archive)
        require(fingerprint({k: v for k, v in value.items() if k not in {'content_sha256', 'archive'}}) == archive['sha256'])
        for side in ['old', 'new']:
            snapshot = snapshots.get(value[side + '_snapshot_id'])
            require(snapshot and snapshot['company_id'] == value['company_id'] and snapshot['content_sha256'] == value[side + '_snapshot_sha256'])
            require(value['request'][side + '_snapshot_id'] == snapshot['snapshot_id'])
            method = value['changes']['VALUATION_ASSUMPTION_OR_METHOD'].get('before' if side == 'old' else 'after')
            if method:
                require(snapshot['valuation_ids'] == [method['valuation_id']])
                valuation = valuations.get(method['valuation_id'])
                require(valuation and method['algorithm'] == valuation['algorithm'])
                require(method['output'] == valuation['result'])
                frozen = valuation_inputs.get(valuation['input_version_id'])
                require(frozen and frozen['config'] == method['config'])
                require(len(snapshot.get('economic_review_ids', [])) == 1)
                review = reviews.get(snapshot['economic_review_ids'][0])
                require(review and review['valuation_id'] == method['valuation_id'])
                model = models.get(review['operating_model_id'])
                require(model and model['request'] == method['model_request'])
        old, new = [snapshots[value[s + '_snapshot_id']] for s in ['old', 'new']]
        operating = value['changes']['OPERATING_EVIDENCE']
        ids = [i for i in new['fact_version_ids'] if i not in old['fact_version_ids']]
        require(operating['new_fact_version_ids'] == ids and operating['facts'] == [facts[i] for i in ids])
        require(operating['removed_fact_version_ids'] == [i for i in old['fact_version_ids'] if i not in new['fact_version_ids']])
        for revision in operating['hypothesis_revisions']:
            for side, field in [('old', 'before'), ('new', 'after')]:
                expected = next((h for h in snapshots[value[side + '_snapshot_id']]['core']['hypotheses'] if h['hypothesis_id'] == revision['hypothesis_id']), None)
                require(revision[field] == expected)
        require({s['path'] for s in value['comparison_policy_sources']} == {'changes.py', 'change_calculator.py'})
        for source in value['comparison_policy_sources']:
            require(archives.get(source['archive']['sha256']) == source['archive'])
