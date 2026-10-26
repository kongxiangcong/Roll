"""Immutable research comparisons. Calculation differences are not market causes."""
import copy
import json
from uuid import uuid4
from datetime import datetime, date
from decimal import Decimal
import hashlib
from pathlib import Path
from .calculator import market_equity, calculate, CalculationError, SHANGHAI
from .valuation import source_files
from .valuation_reference import fundamental_valuation as algorithm
from roll.accounts.ledger import encode, now
from .service import record, verified, fingerprint, fail


class ChangeState:
    def __init__(self, research):
        self.research = research
        with research.transaction() as db:
            db.execute('CREATE TABLE IF NOT EXISTS company_research_change_sets(change_set_id TEXT PRIMARY KEY, company_id TEXT NOT NULL, value TEXT NOT NULL)')

    def freeze_context(self, command):
        r = self.research
        if len(encode(command.model_dump()).encode()) > 131072:
            fail('CONTEXT_INPUT_TOO_LARGE', 'Research quote/check context is bounded to128 KiB')
        parent = r.analysis_snapshot(command.snapshot_id)
        with r.transaction() as db:
            if r.analysis.latest(parent['company_id'], db)['snapshot_id'] != parent['snapshot_id']:
                fail('INPUT_CHANGED', 'Context must extend the current immutable snapshot', 409)
            checks = []
            for identifier in dict.fromkeys(command.check_ids):
                row = db.execute('SELECT value FROM company_research_checks WHERE check_id=?', (identifier,)).fetchone()
                if not row:
                    fail('CHECK_NOT_FOUND', 'Selected source check does not exist')
                check = verified(json.loads(row[0]))
                if check['company_id'] != parent['company_id'] or check['status'] == 'RUNNING':
                    fail('CHECK_REFERENCE_INVALID', 'Checks must be completed and belong to this company')
                checks.append(check)
            bound_at = now()
            quotes = self.verify_quotes(command.quotes, parent, bound_at)
            context = dict(bound_at=bound_at, checks=checks, quotes=quotes, change_reason=command.change_reason)
            archive = r.valuations.archive(encode(context).encode(), 'COMPANY_RESEARCH_CONTEXT', db)
            child = {k: copy.deepcopy(v) for k, v in parent.items() if k != 'content_sha256'}
            child.update(snapshot_id=str(uuid4()), parent_snapshot_id=parent['snapshot_id'], generated_at=now(),
                         enrichment_kind='RESEARCH_CONTEXT', context=context, context_archive=archive,
                         as_of=bound_at, research_basis_as_of=parent.get('research_basis_as_of', parent['as_of']),
                         research_basis_generated_at=parent.get('research_basis_generated_at', parent['generated_at']),
                         check_ids=[c['check_id'] for c in checks], quote_ids=[q['quote_id'] for q in quotes])
            child = record(child)
            r.analysis.insert(db, 'snapshots', 'snapshot_id', child)
            return child

    def verify_quotes(self, quotes, snapshot, bound_at):
        packet = self.research.analysis_input(snapshot['input_id'])
        listings = {i['listing_id']: i for i in packet['payload']['company']['listings']}
        output, seen = [], set()
        for supplied in quotes:
            try:
                required = {'listing_id', 'shares', 'shares_unit', 'shares_as_of', 'price', 'currency', 'priced_at', 'share_refs', 'price_refs', 'price_basis'}
                if not required <= set(supplied) or set(supplied) - required - {'fx'}:
                    raise ValueError('Quote requires explicit listing, dated share/price sources and price basis')
                row = copy.deepcopy(supplied)
                lid = row['listing_id']
                if lid not in listings or lid in seen or row['currency'] != listings[lid]['currency']:
                    raise ValueError('Duplicate, foreign listing or wrong currency')
                seen.add(lid)
                stamp = datetime.fromisoformat(row['priced_at'])
                if stamp.tzinfo is None or stamp > datetime.fromisoformat(bound_at):
                    raise ValueError('Quote time must be aware and actually available at binding')
                day = stamp.astimezone(SHANGHAI).date().isoformat()
                if row['shares_as_of'] != day or row['price_basis'] not in {'RAW_NOMINAL', 'ADJUSTED', 'UNKNOWN'}:
                    raise ValueError('Share date or declared price basis is invalid')
                facts = []
                def match(value, refs, unit, currency, scope, metric=None):
                    if not isinstance(refs, list) or len(refs) != 1:
                        raise ValueError('Exactly one numeric fact is required for each quote component')
                    fact = self.research.fact(refs[0], snapshot['company_id'])
                    if fact['kind'] not in {'DISCLOSED', 'DERIVED'} or fact['value_type'] != 'NUMBER' or fact['value'] is None or (fact['kind'] == 'DERIVED' and not fact['derivation']):
                        raise ValueError('Quote component must be sourced numeric evidence')
                    if Decimal(str(value)) != Decimal(fact['value']) or (unit, currency, scope, day, day) != tuple(fact[k] for k in ['unit', 'currency', 'scope', 'period_start', 'period_end']):
                        raise ValueError('Quote value, units, currency, listing or date differs from fact')
                    if metric and fact['metric'] != metric:
                        raise ValueError('Nominal market price requires an explicitly raw nominal price source fact')
                    if datetime.fromisoformat(fact['consumable_at']) > datetime.fromisoformat(bound_at):
                        raise ValueError('Quote source is not yet available')
                    algorithm.number(value, 'quote component', 0, True)
                    facts.append(fact)
                match(row['shares'], row['share_refs'], row['shares_unit'], None, lid)
                match(row['price'], row['price_refs'], 'price_per_share', row['currency'], lid,
                      'raw_nominal_price' if row['price_basis'] == 'RAW_NOMINAL' else None)
                if row.get('fx'):
                    fx = row['fx']
                    if set(fx) != {'rate', 'from_currency', 'to_currency', 'as_of', 'source_refs'} or fx['from_currency'] != row['currency'] or fx['as_of'] != day:
                        raise ValueError('FX direction/date invalid')
                    match(fx['rate'], fx['source_refs'], 'ratio', None, fx['from_currency'] + '->' + fx['to_currency'])
                materials = [self.research.material(i, snapshot['company_id']) for i in dict.fromkeys(f['material_id'] for f in facts)]
                output.append(dict(quote_id=str(uuid4()), row=row, facts=facts, materials=materials,
                                   available_at=max(f['consumable_at'] for f in facts), source_kind='FROZEN_REFERENCED_EVIDENCE'))
            except (ValueError, KeyError, TypeError, ArithmeticError) as exc:
                fail('QUOTE_BASIS_INVALID', str(exc))
        return output

    def pinned(self, snapshot):
        ids, reviews = snapshot.get('valuation_ids', []), snapshot.get('economic_review_ids', [])
        if len(ids) != 1 or len(reviews) != 1:
            raise ValueError('Exactly one valuation and controlled review must be pinned by each snapshot')
        review = self.research.economic_review(reviews[0])
        value = self.research.valuation(ids[0])
        if review['valuation_id'] != ids[0] or review['valuation_sha256'] != value['content_sha256'] or review['company_id'] != snapshot['company_id']:
            raise ValueError('Pinned valuation/review binding differs')
        frozen = self.research.valuation_input(value['input_version_id'])
        installed = {name: hashlib.sha256(raw).hexdigest() for name, raw in source_files()}
        if any(installed.get(f['path']) != f['archive']['sha256'] for f in frozen['algorithm']['files']):
            raise ValueError('Frozen valuation method source version is unavailable')
        model = self.research.operating_model(review['operating_model_id'])
        return dict(snapshot_id=snapshot['snapshot_id'], valuation_id=ids[0], review_id=reviews[0],
                    input=frozen, model=model, algorithm=frozen['algorithm'])

    def market(self, snapshot, pinned):
        context = snapshot.get('context', {})
        quotes = context.get('quotes', [])
        if any(q['row']['price_basis'] != 'RAW_NOMINAL' for q in quotes):
            raise ValueError('Adjusted or unknown quote basis cannot be a nominal market price')
        frozen = pinned['input']
        metadata = dict(frozen['config']['metadata'], as_of=context.get('bound_at', snapshot['as_of']))
        return market_equity(dict(market_basis=[q['row'] for q in quotes]), frozen['company_identity'], metadata, frozen['config']['shares'])

    def compare_values(self, old, new, unavailable):
        price, method = copy.deepcopy(unavailable), copy.deepcopy(unavailable)
        counter = dict(status='NOT_COMPARABLE', order=['OPERATING_PATH', 'PRICE', 'VALUATION_PARAMETERS_OR_METHOD'], market_cause_identified=False)
        try:
            a, b = self.pinned(old), self.pinned(new)
            x, y = a['input']['config'], b['input']['config']
            method.update(before=dict(valuation_id=a['valuation_id'], algorithm=a['algorithm'], config=x, model_request=a['model']['request'], output=self.research.valuation(a['valuation_id'])['result']),
                          after=dict(valuation_id=b['valuation_id'], algorithm=b['algorithm'], config=y, model_request=b['model']['request'], output=self.research.valuation(b['valuation_id'])['result']),
                          diagnostic_only=True, usable_range=False, economic_review_upgraded=False)
            signature = lambda p: (p['algorithm'], p['input']['config']['cash_flow_basis'],
                tuple(p['input']['config']['metadata'][k] for k in ['currency', 'amount_unit', 'shares_unit']),
                [(s['name'], len(algorithm.cashflows(s))) for s in p['input']['config']['scenarios']],
                [[r['period'] for r in s['years']] for s in p['model']['cashflows']],
                sorted({v['scope'] for v in p['input']['provenance'].values()}),
                sorted({v['scope'] for v in p['model']['request']['drivers']['provenance'].values()}))
            if signature(a) != signature(b):
                raise ValueError('Method/source version, units, currency, scope or forecast horizon is incompatible')
            params = lambda c: {k: v for k, v in c.items() if k not in {'scenarios', 'reverse', 'metadata'}}
            method.update(status='COMPARABLE', changed=params(x) != params(y) or a['model']['request']['economic_basis'] != b['model']['request']['economic_basis'],
                reason='Parameter/model changes are not operating evidence', old_parameters=params(x), new_parameters=params(y))
            market_old, rows_old = self.market(old, a)
            market_new, rows_new = self.market(new, a)  # old shares/currency remain fixed
            shares_by_class = lambda rows: {r['listing_id']: r['shares'] for r in rows}
            if shares_by_class(rows_old) != shares_by_class(rows_new):
                raise ValueError('Price-only comparison requires the old share count for every listing')
            quote_values = lambda rows: {r['listing_id']: (r['price'], r['currency'], r['fx_to_model']) for r in rows}
            debt = algorithm.equity_adjustment(x)[0]
            def conditions(market):
                return [dict(scenario=s['name'], fixed_explicit_fcff=algorithm.cashflows(s),
                    **algorithm.reverse(1, x['shares'], debt, x['wacc'], x['terminal_g'], algorithm.cashflows(s), [], 1, market)) for s in x['scenarios']]
            price.update(status='COMPARABLE', changed=quote_values(rows_old) != quote_values(rows_new), fixed_old_config=x,
                diagnostic_only=True, usable_range=False, economic_review_upgraded=False,
                old_market_equity=market_old, new_market_equity=market_new, old_market_basis=rows_old, new_market_basis=rows_new,
                old_conditions=conditions(market_old), new_conditions=conditions(market_new), market_cause_identified=False,
                reason='All operating paths, bridge and valuation parameters fixed at the old version; conditional requirements are not unique market beliefs')
            # Sequential replacement retains each complete input and its output.
            steps = []
            def step(label, cfg, market):
                cfg = copy.deepcopy(cfg); cfg.pop('reverse', None)
                output = calculate(cfg, a['input']['company_identity'])
                gaps = {s['name']: s['equity_value'] - market for s in output['scenarios']}
                steps.append(dict(replacement=label, config=cfg, market_equity=market, output=output,
                                  model_equity_minus_market=gaps))
            step('BASELINE', x, market_old)
            operating = dict(copy.deepcopy(x), scenarios=copy.deepcopy(y['scenarios']))
            step('OPERATING_PATH', operating, market_old)
            step('PRICE', operating, market_new)
            step('VALUATION_PARAMETERS_OR_METHOD', y, market_new)
            for previous, current in zip(steps, steps[1:]):
                current['gap_change'] = {k: v - previous['model_equity_minus_market'][k] for k, v in current['model_equity_minus_market'].items()}
            rate_only = dict(copy.deepcopy(y), scenarios=copy.deepcopy(x['scenarios'])); rate_only.pop('reverse', None)
            standalone = calculate(rate_only, a['input']['company_identity'])
            interaction = {s['name']: steps[3]['output']['scenarios'][i]['equity_value'] - steps[1]['output']['scenarios'][i]['equity_value'] - s['equity_value'] + steps[0]['output']['scenarios'][i]['equity_value'] for i, s in enumerate(standalone['scenarios'])}
            counter.update(status='COMPARABLE', steps=steps, interaction=interaction,
                interaction_reference=dict(config=rate_only, output=standalone), diagnostic_only=True,
                meaning='Model-internal counterfactual; allocation depends on replacement order, is not unique market causation, and does not upgrade economic review')
        except (ValueError, KeyError, TypeError, CalculationError) as exc:
            reason = exc.reason if isinstance(exc, CalculationError) else str(exc)
            if method['status'] != 'COMPARABLE':
                method['reason'] = reason
            price.update(status='NOT_COMPARABLE', reason=reason)
            counter['reason'] = reason
        return price, method, counter

    def information(self, snapshot, evaluated_at, maximum_age):
        checks = []
        for check in snapshot.get('context', {}).get('checks', []):
            age = max(0, (datetime.fromisoformat(evaluated_at) - datetime.fromisoformat(check['finished_at'])).total_seconds())
            checks.append(dict(check_id=check['check_id'], source_id=check['source_id'], status=check['status'],
                outcome='SUCCESS_NO_NEW' if check['status'] == 'SUCCESS' and not check['new_material_count'] else check['status'],
                aging_status='STALE' if age > maximum_age else 'FRESH', age_seconds=age,
                requested_scopes=check['requested_scopes'], completed_scopes=check['completed_scopes'], failed_scopes=check['failed_scopes'],
                last_checked_at=check['finished_at'], last_success_at=check['last_success_at'],
                new_material_count=check['new_material_count'], meaning=check['meaning']))
        materials = [self.research.material(i, snapshot['company_id']) for i in snapshot['material_ids']]
        day = datetime.fromisoformat(evaluated_at).astimezone(SHANGHAI).date()
        material_dates = []
        for material in materials:
            report_age = (day - date.fromisoformat(material['period_end'])).days if material['period_end'] else None
            disclosed = datetime.fromisoformat(material['disclosed_at']).astimezone(SHANGHAI).date() if material['disclosed_at'] else None
            material_dates.append(dict(material_id=material['material_id'], period_start=material['period_start'], period_end=material['period_end'],
                disclosed_at=material['disclosed_at'], received_at=material['received_at'], consumable_at=material['consumable_at'],
                age_basis='REPORT_PERIOD_END' if material['period_end'] else 'UNKNOWN', material_age_days=report_age,
                disclosure_age_days=(day-disclosed).days if disclosed else None,
                meaning='Report-period and disclosure ages; acquisition/check time does not refresh source content'))
        return dict(research_as_of=snapshot.get('research_basis_as_of', snapshot['as_of']), knowledge_as_of=snapshot['as_of'],
            context_bound_at=snapshot.get('context', {}).get('bound_at'),
            research_basis_generated_at=snapshot.get('research_basis_generated_at', snapshot['generated_at']),
            checks=checks, check_state='BOUND' if checks else 'NOT_CHECKED',
            material_dates=material_dates,
            research_verification_refreshed=False)

    def read(self, identifier):
        with self.research.ledger.connection() as db:
            row = db.execute('SELECT value FROM company_research_change_sets WHERE change_set_id=?', (identifier,)).fetchone()
        if not row:
            fail('CHANGE_SET_NOT_FOUND', 'Research change set is not registered', 404)
        value = verified(json.loads(row[0]))
        raw = self.research.evidence.raw(value['archive']['sha256']).read_bytes()
        if json.loads(raw) != {k: v for k, v in value.items() if k not in {'archive', 'content_sha256'}}:
            fail('ARTIFACT_CORRUPT', 'Research comparison differs from canonical archive', 409)
        for side in ['old', 'new']:
            snapshot = self.research.analysis_snapshot(value[side + '_snapshot_id'])
            if snapshot['company_id'] != value['company_id'] or snapshot['content_sha256'] != value[side + '_snapshot_sha256']:
                fail('RESEARCH_REFERENCE_INVALID', 'Comparison snapshot binding differs', 409)
        return value

    def replay(self, identifier):
        value = self.read(identifier)
        if {s['path'] for s in value['comparison_policy_sources']} != {'changes.py', 'change_calculator.py'}:
            fail('RESEARCH_REFERENCE_INVALID', 'Comparison policy source list differs', 409)
        for source in value['comparison_policy_sources']:
            installed = Path(__file__).parent / source['path']
            if hashlib.sha256(installed.read_bytes()).hexdigest() != source['archive']['sha256']:
                fail('COMPARISON_VERSION_UNAVAILABLE', 'Install the frozen comparison version; bundle code is never executed', 409)
        old, new = [self.research.analysis_snapshot(value[s + '_snapshot_id']) for s in ['old', 'new']]
        unavailable = {k: value['changes']['PRICE'][k] for k in ['status', 'reason', 'old_snapshot_id', 'new_snapshot_id']}
        unavailable['status'] = 'NOT_COMPARABLE'
        price, method, counter = self.compare_values(old, new, unavailable)
        return dict(change_set_id=identifier, matches_saved_comparison=price == value['changes']['PRICE'] and method == value['changes']['VALUATION_ASSUMPTION_OR_METHOD'] and counter == value['counterfactual'],
                    network_calls=0, model_calls=0, information_state_replayed_at_saved_time=True)

    def compare(self, command):
        r = self.research
        old, new = [r.analysis_snapshot(i) for i in [command.old_snapshot_id, command.new_snapshot_id]]
        if old['company_id'] != new['company_id']:
            fail('CROSS_COMPANY_REFERENCE', 'Comparison requires two snapshots of the same company')
        request = command.model_dump()
        scope = 'change-set:' + old['company_id']
        with r.ledger.connection() as db:
            prior = db.execute('SELECT request_hash,result FROM company_research_commands WHERE scope=? AND key=?', (scope, command.idempotency_key)).fetchone()
        if prior:
            if prior[0] != fingerprint(request):
                fail('IDEMPOTENCY_CONFLICT', 'Comparison key was used for another pair', 409)
            return self.read(verified(json.loads(prior[1]))['change_set_id'])
        old_h = {h['hypothesis_id']: h for h in old['core']['hypotheses']}
        new_h = {h['hypothesis_id']: h for h in new['core']['hypotheses']}
        revisions = [dict(hypothesis_id=i, before=old_h.get(i), after=new_h.get(i)) for i in sorted(set(old_h) | set(new_h)) if old_h.get(i) != new_h.get(i)]
        ids = [i for i in new['fact_version_ids'] if i not in old['fact_version_ids']]
        facts = [r.fact(i, old['company_id']) for i in ids]
        op = dict(new_fact_version_ids=ids, removed_fact_version_ids=[i for i in old['fact_version_ids'] if i not in new['fact_version_ids']],
                  facts=facts, hypothesis_revisions=revisions, evidence_changed=bool(ids or set(old['fact_version_ids']) - set(new['fact_version_ids'])),
                  hypothesis_revision_changed=bool(revisions),
                  reference_conflicts=dict(old=r.analysis_input(old['input_id'])['payload']['conflicts'], new=r.analysis_input(new['input_id'])['payload']['conflicts']),
                  meaning='Evidence and hypothesis revisions only; absence of new evidence is not proof of unchanged operations')
        unavailable = dict(status='NOT_COMPARABLE', reason='Pinned compatible valuation and complete verified nominal quote bases required',
                           old_snapshot_id=old['snapshot_id'], new_snapshot_id=new['snapshot_id'])
        views = [r.valuation_presentation(s['economic_review_ids'][0], command.presentation_purpose) if len(s.get('economic_review_ids', [])) == 1 else None for s in [old, new]]
        price, method, counter = self.compare_values(old, new, unavailable)
        evaluated_at = now()
        payload = record(dict(change_set_id=str(uuid4()), company_id=old['company_id'], request=request,
            old_snapshot_id=old['snapshot_id'], new_snapshot_id=new['snapshot_id'], old_snapshot_sha256=old['content_sha256'], new_snapshot_sha256=new['content_sha256'],
            changes=dict(OPERATING_EVIDENCE=op, PRICE=price, VALUATION_ASSUMPTION_OR_METHOD=method),
            information_state=dict(evaluated_at=evaluated_at, old=self.information(old, evaluated_at, command.source_max_age_seconds), new=self.information(new, evaluated_at, command.source_max_age_seconds)),
            pinned_presentations=views,
            quick_summary=dict(valuation_scenarios=copy.deepcopy(views[1]['scenarios']) if views[1] and command.presentation_purpose == 'BASELINE_RESEARCH' else [],
                purpose=command.presentation_purpose, market_cause_identified=False),
            counterfactual=counter))
        payload.pop('content_sha256')
        with r.transaction() as db:
            prior = db.execute('SELECT request_hash,result FROM company_research_commands WHERE scope=? AND key=?', (scope, command.idempotency_key)).fetchone()
            if prior:
                if prior[0] != fingerprint(request):
                    fail('IDEMPOTENCY_CONFLICT', 'Comparison key was used for another pair', 409)
                return self.read(verified(json.loads(prior[1]))['change_set_id'])
            payload['comparison_policy_sources'] = [dict(path=name, archive=r.valuations.archive((Path(__file__).parent / name).read_bytes(), 'COMPANY_COMPARISON_POLICY', db)) for name in ['changes.py', 'change_calculator.py']]
            archive = r.valuations.archive(encode(payload).encode(), 'COMPANY_RESEARCH_CHANGE_SET', db)
            value = record({**payload, 'archive': archive})
            db.execute('INSERT INTO company_research_change_sets VALUES(?,?,?)', (value['change_set_id'], value['company_id'], encode(value)))
            r.save_command(db, scope, command.idempotency_key, request, value)
        return value
