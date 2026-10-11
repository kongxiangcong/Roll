"""Current actions from host evidence, separate from actual account events."""
import hashlib
import json
import time
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field
from roll.accounts.ledger import encode, now, timestamp
from roll.accounts.reconcile import UseCheck, use_check
from roll.decisions.funding import LossFacts, evaluate_loss
from roll.research.shadow import calculate_policy
from roll.research.risk_policy import calculate as calculate_risk


def fingerprint(value):
    return hashlib.sha256(encode(value).encode()).hexdigest()


def code():
    return hashlib.sha256(Path(__file__).read_bytes().replace(b'\r\n', b'\n')).hexdigest()


class EvaluationCommand(BaseModel):
    model_config = ConfigDict(extra='forbid')
    freeze_id: str | None = None
    forecast_ids: list[str] = Field(default_factory=list, max_length=35)
    risk_evaluation_id: str | None = None
    required_as_of: str | None = None


class Actions:
    def __init__(self, ledger, funding, capabilities, evidence, shadow, risk_policies, valuations):
        self.ledger, self.funding, self.capabilities = ledger, funding, capabilities
        self.evidence, self.shadow, self.risk_policies, self.valuations = evidence, shadow, risk_policies, valuations
        with ledger.connection() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS action_evaluations(id TEXT PRIMARY KEY, fingerprint TEXT UNIQUE, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS action_events(id TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS action_invalidations(decision_id TEXT, reason_fingerprint TEXT, value TEXT NOT NULL, PRIMARY KEY(decision_id,reason_fingerprint));
                CREATE TABLE IF NOT EXISTS action_loss_state(scope TEXT PRIMARY KEY, value TEXT NOT NULL);
            ''')

    def capture(self, command):
        with self.ledger.connection() as db:
            db.execute('BEGIN')
            account, funding = self.ledger.account(db=db), self.funding.current(db=db)
            capabilities = self.capabilities.current(db=db)
            pending = [self.ledger.get_draft(r[0], db) for r in db.execute("SELECT d.id FROM account_drafts d WHERE status IN ('READY','QUARANTINED') AND NOT EXISTS(SELECT 1 FROM account_receipts r WHERE json_extract(r.receipt,'$.draft_id')=d.id)")]
            events = self.ledger.events(db=db)
            previous = db.execute('SELECT value FROM action_loss_state WHERE scope=?', (encode([funding.get('scope_kind'), funding.get('scope_id'), funding.get('loss_origin_at')]),)).fetchone()
            db.rollback()
        bound_cutoffs = [s['grant']['command']['required_as_of'] for s in capabilities['grant_statuses'] if not s['reasons']]
        required = timestamp(command.required_as_of or max(bound_cutoffs, default=account.get('effective_at') or '1970-01-01T00:00:00+00:00'))
        listing = self.evidence.market.listing()
        members = [*listing['members'], *listing['background_indices']]
        observations = []
        for member in members:
            snapshots = self.evidence.snapshots(member['instrument'], 'QUOTE')
            facts = [f for s in snapshots for f in s['facts']]
            quote = max(facts, key=lambda f: f.get('available_at', ''), default=None)
            observations.append({'instrument': member['instrument'], 'identity': member.get('identity'), 'quote': quote})
        packet = None
        method = self.capabilities.method_package
        freeze_id = command.freeze_id
        forecast_ids = command.forecast_ids
        if method is None and freeze_id is None:
            profit = next((s['grant'] for s in capabilities['grant_statuses'] if not s['reasons'] and s['grant']['candidate_kind'] == 'PROFIT_MODEL'), None)
            if profit:
                with self.ledger.connection() as db:
                    frozen_row = next((json.loads(r[0]) for r in db.execute('SELECT value FROM research_complete_freezes')
                                       if json.loads(r[0])['complete_protocol_fingerprint'] == profit['complete_protocol_fingerprint']), None)
                    if frozen_row:
                        freeze_id = frozen_row['freeze_id']
                        found = [json.loads(r[0]) for r in db.execute('SELECT value FROM research_forecasts ORDER BY rowid DESC')]
                        forecast_ids = [next((f['forecast_id'] for f in found if f['model_run_id'] == frozen_row['model_run_id'] and f['instrument'] == i), None)
                                        for i in profit['scope']['instruments']]
                        forecast_ids = [f for f in forecast_ids if f]
        if method is not None:
            packet = method.get('action_packet')
        elif freeze_id:
            frozen = self.shadow.get(freeze_id)
            forecasts = self.shadow.forecasts(frozen, forecast_ids)
            opportunities = []
            for forecast in forecasts:
                observation = next((r for r in observations if r['instrument'] == forecast['instrument']), {})
                quote, identity = observation.get('quote') or {}, observation.get('identity') or {}
                rule = self.evidence.market.rules.rule(identity.get('exchange'), identity.get('board'), identity.get('instrument_type'))
                upper = str(Decimal(quote['last']) * (1 + Decimal(rule.get('normal_price_limit_percent', '0')) / 100)) if quote.get('last') else None
                opportunities.append({'instrument': forecast['instrument'], 'forecast_id': forecast['forecast_id'],
                    'probability': forecast['probability'], 'quantity': frozen['policy']['quantity'],
                    'price_lower_yuan': quote.get('last'), 'price_upper_yuan': upper, 'fees_yuan': None,
                    'quote_at': quote.get('upstream_at'), 'quote_available_at': quote.get('available_at'),
                    'cumulative_volume': quote.get('volume'), 'forecast_cutoff': forecast['observation_cutoff'],
                    'forecast_horizon': forecast['horizon_sessions'], 'daily_completion': 'COMPLETE' if forecast['feature_snapshot'].get('complete') is True else 'UNVERIFIED',
                    'rule_id': rule.get('rule_id'), 'rule_status': rule['implementation_status'],
                    'market_status': quote.get('current_status'), 'market': identity.get('exchange'), 'board': identity.get('board'),
                    'calendar_open': self.evidence.market.rules.calendar(identity.get('exchange'), datetime.fromisoformat(required).date()).get('is_trading_day'),
                    'input_gaps': ['ACTUAL_BROKER_COST_NOT_CONFIRMED'], 'forecast_namespace': forecast['namespace'],
                    'artifact_fingerprints': forecast['artifact_fingerprints']})
            try:
                valuation = self.valuations.get()
                facts = valuation['facts'] if valuation['account_version'] == account['version'] else None
            except HTTPException:
                facts = None
            packet = {'namespace': 'ACTUAL', 'policy': frozen['policy'], 'complete_protocol_fingerprint': frozen['complete_protocol_fingerprint'],
                      'as_of': required, 'expires_at': required, 'loss_facts': facts, 'opportunities': opportunities,
                      'model_run_id': frozen['model_run_id'], 'fingerprints': frozen['fingerprints']}
        if command.risk_evaluation_id:
            risk = self.risk_policies.get_evaluation(command.risk_evaluation_id)
            risk_inputs = self.shadow.checked_archive(risk['input_archive'])
            packet = dict(packet or {'namespace': 'ACTUAL', 'opportunities': [], 'as_of': required, 'expires_at': required})
            packet['risk_inputs'] = risk_inputs
            packet['risk_policy_id'] = risk['policy_id']
        return {'command': command.model_dump(), 'account': account, 'funding': funding, 'capabilities': capabilities,
                'previous_loss': json.loads(previous[0]) if previous else None,
                'required_as_of': required, 'observations': observations,
                'new_risk_check': use_check(account, pending, UseCheck(purpose='NEW_RISK', required_as_of=required), timestamp, events),
                'reduction_check': use_check(account, pending, UseCheck(purpose='REDUCTION', required_as_of=required), timestamp, events),
                'packet': packet, 'code_fingerprint': code()}

    @staticmethod
    def calculate(inputs):
        caps = inputs['capabilities']
        base = {'decisions': [], 'refusals': [], 'holding_risks': [{'instrument': p['instrument'], 'sellable_quantity': p['sellable_quantity'], 'reasons': ['INDEPENDENT_RISK_POLICY_INPUT_NOT_AVAILABLE']} for p in inputs['account']['positions']], 'observations': inputs['observations'], 'holdings': inputs['account']['positions'],
                'limitations': ['TECHNICAL_CAPABILITY_UNGRANTED'] if not caps['allowed_actions'] else ['FROZEN_ACTION_INPUT_NOT_AVAILABLE'],
                'namespace': 'ACTUAL', 'system_usable': False, 'probabilities': [], 'joint_budget': None}
        packet = inputs['packet']
        if not packet: return base
        method = packet['namespace'] == 'METHOD_ENGINEERING'
        base.update(namespace=packet['namespace'], limitations=[], system_usable=not method)
        account, funding = inputs['account'], inputs['funding']
        statuses = caps['grant_statuses']
        def grant_for(kind, instrument, action):
            return next((s['grant'] for s in statuses if not s['reasons'] and s['grant']['candidate_kind'] == kind
                         and instrument in s['grant']['scope']['instruments'] and action in s['allowed_actions']
                         and (method or s['grant']['system_usable'])
                         and (kind != 'PROFIT_MODEL' or s['grant']['complete_protocol_fingerprint'] == packet.get('complete_protocol_fingerprint'))), None)
        loss = None
        if packet.get('loss_facts'):
            try: loss = evaluate_loss(funding, LossFacts(**packet['loss_facts']), inputs.get('previous_loss'))
            except (HTTPException, ValueError, KeyError): pass
        global_gaps = []
        bound_times = [s['grant']['command']['required_as_of'] for s in statuses if not s['reasons']]
        if bound_times and datetime.fromisoformat(inputs['required_as_of']) < max(datetime.fromisoformat(t) for t in bound_times): global_gaps.append('CURRENT_CUTOFF_NOT_BOUND')
        if funding['state'] != 'CONFIRMED' or not funding.get('enabled') or funding.get('pause_latched'): global_gaps.append('FUNDING_NOT_ENABLED')
        if not inputs['new_risk_check']['allowed']: global_gaps.extend(['ACCOUNT_FACTS_NOT_RECONCILED', *inputs['new_risk_check']['reasons']])
        if not loss or loss['status'] != 'WITHIN_BOUNDARY': global_gaps.append('LOSS_BOUNDARY_UNAVAILABLE_OR_PAUSED')
        if packet.get('as_of') is None or datetime.fromisoformat(packet['as_of']) < datetime.fromisoformat(inputs['required_as_of']): global_gaps.append('PURPOSE_DATA_STALE')
        holdings = {r['instrument']: r for r in account['positions']}
        prices = {r['instrument']: r.get('price_lower_yuan') for r in packet.get('opportunities', [])}
        exposure = Decimal('0')
        for holding in holdings.values():
            if prices.get(holding['instrument']) is None or holding['quantity'] is None:
                global_gaps.append('PORTFOLIO_EXPOSURE_UNKNOWN')
            else: exposure += Decimal(prices[holding['instrument']]) * Decimal(holding['quantity'])
        available = account.get('conservative_available', account.get('broker_available'))
        if available is None: global_gaps.append('BROKER_AVAILABLE_UNKNOWN')
        cash = max(Decimal('0'), min(Decimal(available or '0'), Decimal(funding.get('capital_amount', '0'))) - Decimal(funding.get('cash_reserve', '0')))
        nav = Decimal(packet['loss_facts']['net_assets']) if loss and loss['status'] == 'WITHIN_BOUNDARY' else None
        opportunities = []
        for original in packet.get('opportunities', []):
            row = dict(original)
            reasons = [*global_gaps, *row.get('input_gaps', [])]
            grant = grant_for('PROFIT_MODEL', row['instrument'], 'BUY')
            if grant is None: reasons.append('PROFIT_CAPABILITY_NOT_CURRENT_IN_SCOPE')
            if not any(p['market'] == row.get('market') and p['board'] == row.get('board') and p['status'] == 'OPEN' for p in account['permission_profile']): reasons.append('MARKET_PERMISSION_NOT_OPEN')
            if row.get('rule_status') != 'ADAPTED' or not row.get('rule_id'): reasons.append('RULE_UNKNOWN_OR_UNSUPPORTED')
            if row.get('market_status') != 'CONFIRMED_NORMAL': reasons.append('CURRENT_SPECIAL_STATUS_UNKNOWN_OR_NOT_NORMAL')
            if row.get('calendar_open') is not True: reasons.append('CALENDAR_CLOSED_OR_UNKNOWN')
            if row.get('daily_completion') != 'COMPLETE': reasons.append('DAILY_INPUT_INCOMPLETE_INTRADAY_VOLUME_EXCLUDED')
            if row.get('forecast_horizon') != 20: reasons.append('FORECAST_HORIZON_OUTSIDE_POLICY')
            if not method and row.get('forecast_namespace') in {'HISTORICAL', 'SHADOW', 'ACCOUNT_CONDITIONAL'}: reasons.append('RESEARCH_FORECAST_NOT_CURRENT_FORMAL_INPUT')
            if row.get('quote_at') is None or datetime.fromisoformat(row['quote_at']) < datetime.fromisoformat(inputs['required_as_of']): reasons.append('QUOTE_STALE_FOR_PURPOSE')
            if row.get('fees_yuan') is None or row.get('price_upper_yuan') is None: reasons.append('PRICE_OR_FEES_UNKNOWN')
            required = Decimal(row.get('price_upper_yuan') or '0') * Decimal(packet['policy']['quantity']) + Decimal(row.get('fees_yuan') or '0')
            if required > Decimal(funding.get('single_exposure', '0')): reasons.append('AUTHORIZED_SINGLE_EXPOSURE')
            if exposure + required > Decimal(funding.get('total_exposure', '0')): reasons.append('AUTHORIZED_TOTAL_EXPOSURE')
            row.update(required_cash_yuan=format(required, '.2f'), input_gaps=list(dict.fromkeys(reasons)), grant_id=grant['grant_id'] if grant else None)
            opportunities.append(row)
        if opportunities:
            policy = packet['policy']
            if policy.get('version') != '20-policy-v1' or policy.get('quantity') != '200' or policy.get('probability_threshold') != '0.60' or policy.get('exit') != 'HORIZON_SESSION20_CLOSE':
                base['limitations'].append('FROZEN_POLICY_NOT_SUPPORTED')
            else:
                rows = calculate_policy(opportunities, cash, Decimal('0'), exposure, nav, set(holdings), policy)
                accepted = 0
                for row in rows:
                    if row['action'] == 'BUY' and accepted:
                        row.update(action='REFUSE', reasons=['ONE_NEW_ENTRY_LIMIT'])
                    if row['action'] == 'BUY':
                        accepted += 1
                        row.update(current_quantity='0', target_quantity=policy['quantity'], quantity=policy['quantity'],
                            basis_type='PROFIT_MODEL', expires_at=packet['expires_at'], data_cutoff=row['quote_at'],
                            trigger_conditions=['PRICE_WITHIN_FROZEN_INTERVAL', 'CURRENT_DEPENDENCIES_VALID'],
                            invalidation_conditions=['ACCOUNT_VERSION_CHANGE', 'FUNDING_CHANGE', 'DATA_CHANGE', 'GRANT_RESTRICTION', 'EXPIRY'],
                            uncertainty='NEXT_PRICE_AND_FILL_NOT_GUARANTEED; no ledger event until explicit actual confirmation')
                        base['decisions'].append(row)
                    else:
                        if not method and row.get('forecast_namespace') in {'HISTORICAL', 'SHADOW', 'ACCOUNT_CONDITIONAL'}:
                            row.pop('probability', None)
                            row['probability_visibility'] = 'RESEARCH_VIEW_ONLY'
                        base['refusals'].append(row)
        base['joint_budget'] = {'available_after_user_reserve_yuan': format(cash, '.2f'),
            'reserved_yuan': format(sum((Decimal(r['required_cash_yuan']) for r in base['decisions']), Decimal('0')), '.2f'),
            'broker_frozen_deducted_again': False, 'existing_exposure_yuan': format(exposure, '.2f'), 'loss': loss,
            'account_version': account['version'], 'funding_version': funding['version']}
        base['limitations'].extend(list(dict.fromkeys(global_gaps)))
        if packet.get('risk_inputs'):
            risk_inputs = {**packet['risk_inputs'], 'account': account, 'authorization': funding,
                           'account_use_check': inputs['reduction_check'], 'loss_result': loss,
                           'capture_consistent': True}
            risk = calculate_risk(risk_inputs)
            base['holding_risks'] = risk['positions']
            for holding in risk['positions']:
                grant = grant_for('RISK_POLICY', holding['instrument'], 'EXIT' if holding.get('target_quantity') == '0' else 'REDUCE')
                bound = grant and grant['deployment_fingerprints'].get('policy') == risk_inputs['policy'].get('policy_fingerprint')
                if not method and risk_inputs.get('evidence_kind') == 'METHOD_CASE': bound = False
                if holding.get('executable_quantity') is not None and bound and risk_inputs['required_as_of'] == inputs['required_as_of']:
                    base['decisions'].append({'instrument': holding['instrument'], 'action': 'EXIT' if holding['target_quantity'] == '0' else 'REDUCE',
                        'basis_type': 'RISK_POLICY', 'grant_id': grant['grant_id'], 'policy_id': risk_inputs['policy']['policy_id'],
                        'quantity': holding['executable_quantity'], 'current_quantity': holding['quantity'], 'target_quantity': holding['target_quantity'],
                        'price_lower_yuan': holding['price_window']['reference_yuan'], 'price_upper_yuan': holding['price_window']['reference_yuan'],
                        'expires_at': min(packet['expires_at'], grant['expires_at']), 'data_cutoff': risk_inputs['required_as_of'],
                        'required_cash_yuan': '0.00', 'rule_id': holding['rule'].get('rule_id'), 'reasons': holding['reasons'],
                        'trigger_conditions': ['CONFIRMED_AUTHORIZED_EXPOSURE_EXCESS', 'CONFIRMED_SELLABLE_QUANTITY'],
                        'invalidation_conditions': ['ACCOUNT_VERSION_CHANGE', 'FUNDING_CHANGE', 'RULE_OR_DATA_CHANGE', 'GRANT_RESTRICTION', 'EXPIRY'],
                        'uncertainty': 'PARTIAL_OR_NO_FILL_LEAVES_RISK; profit model advantage is not required', 'stress': holding['stress']})
                elif holding.get('executable_quantity') is not None:
                    holding['reasons'].append('RISK_CAPABILITY_OR_CURRENT_INPUT_BINDING_NOT_VERIFIED')
        else:
            base['holding_risks'] = [{'instrument': p['instrument'], 'quantity': p['quantity'], 'sellable_quantity': p['sellable_quantity'],
                                      'reasons': ['INDEPENDENT_RISK_POLICY_INPUT_NOT_AVAILABLE']} for p in account['positions']]
        for row in base['decisions']:
            row['decision_id'] = fingerprint({'input': fingerprint(inputs), 'instrument': row['instrument'], 'basis': row['basis_type']})
            row['dependencies'] = {'account_version': account['version'], 'funding_version': funding['version'],
                'grant_id': row['grant_id'], 'policy_fingerprint': fingerprint(packet.get('policy')),
                'data_fingerprint': fingerprint(inputs['observations']), 'complete_protocol_fingerprint': packet.get('complete_protocol_fingerprint'),
                'code_fingerprint': inputs['code_fingerprint'], 'rule_id': row.get('rule_id')}
        base['system_usable'] = bool(base['decisions']) and not method
        return base

    def evaluate(self, command):
        inputs = self.capture(command)
        key = fingerprint({k: v for k, v in inputs.items() if k != 'previous_loss'})
        result = self.calculate(inputs)
        if self.capabilities.method_package is not None:
            delay = (inputs['packet'] or {}).get('method_publish_delay_ms', 0)
            if type(delay) is not int or not 0 <= delay <= 5000: raise HTTPException(422, 'METHOD_PUBLISH_DELAY_INVALID')
            time.sleep(delay / 1000)
        archive = self.evidence.archive(encode(inputs).encode(), 'CURRENT_ACTION_INPUT')
        with self.ledger.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            prior = db.execute('SELECT value FROM action_evaluations WHERE fingerprint=?', (key,)).fetchone()
            if prior:
                db.rollback()
                return json.loads(prior[0])
            if self.ledger.account(db=db)['version'] != inputs['account']['version'] or self.funding.current(db=db)['version'] != inputs['funding']['version']:
                result.update(decisions=[], limitations=['CURRENT_VERSION_CHANGED_BEFORE_PUBLICATION'])
            else:
                latest = self.capabilities.current(db=db)
                if latest != inputs['capabilities']:
                    result.update(decisions=[], limitations=['CURRENT_CAPABILITY_CHANGED_BEFORE_PUBLICATION'])
            if any(datetime.fromisoformat(d['expires_at']) <= datetime.fromisoformat(now()) for d in result['decisions']):
                result.update(decisions=[], limitations=['ACTION_EXPIRED_BEFORE_PUBLICATION'])
            predecessor = db.execute('SELECT id,value FROM action_evaluations ORDER BY rowid DESC LIMIT 1').fetchone()
            value = {'evaluation_id': str(uuid4()), 'registered_at': now(), 'input_fingerprint': key,
                     'input_archive': archive, 'code_fingerprint': code(), 'predecessor_id': predecessor[0] if predecessor else None,
                     'account_version': inputs['account']['version'], 'funding_version': inputs['funding']['version'], **result}
            value['publication_check'] = {'account_version': self.ledger.account(db=db)['version'], 'funding_version': self.funding.current(db=db)['version'],
                                        'refusal': result['limitations'] if any(r.endswith('BEFORE_PUBLICATION') for r in result['limitations']) else None}
            db.execute('INSERT INTO action_evaluations VALUES(?,?,?)', (value['evaluation_id'], key, encode(value)))
            loss = (result.get('joint_budget') or {}).get('loss')
            if loss and loss.get('peak_loss') is not None:
                scope = encode([inputs['funding']['scope_kind'], inputs['funding']['scope_id'], inputs['funding']['loss_origin_at']])
                db.execute('INSERT OR REPLACE INTO action_loss_state VALUES(?,?)', (scope, encode(loss)))
            event = {'event_id': str(uuid4()), 'event_type': 'ACTION_EVALUATED', 'evaluation_id': value['evaluation_id'],
                     'recorded_at': value['registered_at'], 'input_fingerprint': key, 'limitations': value['limitations'],
                     'account_version': value['account_version'], 'funding_version': value['funding_version']}
            db.execute('INSERT INTO action_events VALUES(?,?)', (event['event_id'], encode(event)))
            if predecessor:
                for old in json.loads(predecessor[1])['decisions']:
                    new = next((d for d in value['decisions'] if d['instrument'] == old['instrument']), None)
                    changed = {'event_id': str(uuid4()), 'event_type': 'ACTION_SUPERSEDED', 'decision_id': old['decision_id'],
                               'successor_evaluation_id': value['evaluation_id'], 'recorded_at': value['registered_at'],
                               'account_version': value['account_version'], 'funding_version': value['funding_version']}
                    db.execute('INSERT INTO action_events VALUES(?,?)', (changed['event_id'], encode(changed)))
                    if new and old['action'] != new['action']:
                        changed.update(event_id=str(uuid4()), event_type='ACTION_FLIPPED', old_action=old['action'], new_action=new['action'])
                        db.execute('INSERT INTO action_events VALUES(?,?)', (changed['event_id'], encode(changed)))
            db.commit()
        return value

    def get(self, identifier):
        with self.ledger.connection() as db:
            row = db.execute('SELECT value FROM action_evaluations WHERE id=?', (identifier,)).fetchone()
        if not row: raise HTTPException(404, '动作评估不存在')
        return json.loads(row[0])

    def current(self, instrument=None):
        with self.ledger.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT value FROM action_evaluations ORDER BY rowid DESC LIMIT 1').fetchone()
            value = json.loads(row[0]) if row else None
            current = self.ledger.account(db=db), self.funding.current(db=db), self.capabilities.current(db=db)
            active, invalidated = [], []
            for decision in value['decisions'] if value else []:
                if instrument and decision['instrument'] != instrument: continue
                reasons = []
                if current[0]['version'] != value['account_version']: reasons.append('ACCOUNT_VERSION_CHANGE')
                if current[1]['version'] != value['funding_version']: reasons.append('FUNDING_VERSION_CHANGE')
                status = next((s for s in current[2]['grant_statuses'] if s['grant']['grant_id'] == decision['grant_id']), None)
                if not status or status['reasons'] or decision['action'] not in status['allowed_actions']: reasons.append('GRANT_RESTRICTED')
                if datetime.fromisoformat(decision['expires_at']) <= datetime.fromisoformat(now()): reasons.append('EXPIRED')
                if value['code_fingerprint'] != code(): reasons.append('ACTION_CODE_CHANGED')
                if reasons:
                    reason_key = fingerprint(reasons)
                    event = {'event_id': str(uuid4()), 'event_type': 'ACTION_INVALIDATED', 'evaluation_id': value['evaluation_id'],
                             'decision_id': decision['decision_id'], 'recorded_at': now(), 'reasons': reasons,
                             'account_version': current[0]['version'], 'funding_version': current[1]['version']}
                    inserted = db.execute('INSERT OR IGNORE INTO action_invalidations VALUES(?,?,?)', (decision['decision_id'], reason_key, encode(event))).rowcount
                    if inserted: db.execute('INSERT INTO action_events VALUES(?,?)', (event['event_id'], encode(event)))
                    invalidated.append({'decision': decision, 'reasons': reasons})
                else: active.append(decision)
            db.commit()
        return {'evaluation': value, 'instrument': instrument, 'decisions': active, 'invalidated': invalidated}

    def replay(self, identifier):
        value = self.get(identifier)
        if value['code_fingerprint'] != code(): raise HTTPException(409, 'ACTION_CODE_VERSION_CHANGED')
        inputs = json.loads(self.evidence.raw(value['input_archive']['sha256']).read_text(encoding='utf-8'))
        result = self.calculate(inputs)
        if value['publication_check']['refusal']:
            result.update(decisions=[], limitations=value['publication_check']['refusal'])
        return {'evaluation_id': identifier, 'matches_original': all(value[k] == v for k, v in result.items()), 'network_calls': 0, 'result': result}

    def events(self):
        with self.ledger.connection() as db:
            return [json.loads(r[0]) for r in db.execute('SELECT value FROM action_events ORDER BY rowid')]

    def metrics(self):
        events = self.events()
        return {'invalidated_actions': {'status': 'CHECKED', 'value': len({e['decision_id'] for e in events if e['event_type'] in {'ACTION_INVALIDATED', 'ACTION_SUPERSEDED'}})},
                'action_flips': {'status': 'CHECKED', 'value': sum(e['event_type'] == 'ACTION_FLIPPED' for e in events)}}
