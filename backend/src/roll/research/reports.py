"""Read-only research reports from saved results, never a new scoring authority."""
from fastapi import HTTPException
from roll.accounts.ledger import encode
import json
from datetime import datetime
from decimal import Decimal


class ResearchReports:
    def __init__(self, shadow, valuations, intents, notifications, monitoring):
        self.shadow, self.valuations = shadow, valuations
        self.intents, self.notifications, self.monitoring = intents, notifications, monitoring

    def get(self, freeze_id, valuation_id=None, decision_id=None, evaluation_id=None, intent_id=None, monitoring_check_id=None):
        if bool(decision_id) != bool(evaluation_id) or (intent_id and not decision_id):
            raise HTTPException(422, 'REPORT_REQUIRES_DECISION_AND_EVALUATION_PAIR')
        frozen = self.shadow.get(freeze_id)
        saved = self.shadow.results(freeze_id)
        if saved['SHADOW'].get('input_archive'):
            self.shadow.checked_archive(saved['SHADOW']['input_archive'])
        for diagnostic in saved['ACCOUNT_CONDITIONAL']:
            self.shadow.checked_archive(diagnostic['archive'])
        valuation = self.valuations.get(valuation_id) if valuation_id else None
        actual = {'account_version': valuation['account_version'] if valuation else saved['ACTUAL']['version'],
                  'valuation': valuation, 'net_assets': valuation['facts']['net_assets'] if valuation else None,
                  'status': valuation['facts']['valuation_status'] if valuation else 'NO_SAVED_VALUATION_SELECTED'}
        execution, deviations = self.execution(frozen, decision_id, evaluation_id, intent_id)
        historical = {**saved['HISTORICAL'], 'counterfactual_diagnostics': [
            {'forecast_id': row['forecast_id'], 'action': row['action'], 'reasons': row['reasons'],
             'counterfactual': row['counterfactual'], 'performance_included': False}
            for row in saved['SHADOW']['opportunities'] if row.get('counterfactual')]}
        checks = [self.monitoring.get(monitoring_check_id)] if monitoring_check_id else []
        corrections = [r for r in self.monitoring.corrections() if r['monitoring_check_id'] == monitoring_check_id] if checks else []
        return {'report_version': '29-saved-results-v1', 'source_kind': 'RESEARCH',
                'freeze_id': freeze_id, 'protocol_id': frozen['protocol_id'],
                'model_run_id': frozen['model_run_id'], 'evidence_kind': frozen['evidence_kind'],
                'complete_protocol_fingerprint': frozen['complete_protocol_fingerprint'],
                'original_fingerprints': frozen['fingerprints'],
                'system_usable': False, 'prepare_allowed': False,
                'notification_allowed': False, 'research_link': '/#research=' + frozen['freeze_id'],
                'qualification': {'capability': 'NOT_GRANTED', 'calibrator_fit_status': frozen['calibrator_fit_status'],
                                  'validation_gaps': frozen['validation_gaps']},
                'namespaces': {'ACTUAL': actual, 'HISTORICAL': historical,
                               'SHADOW': saved['SHADOW'], 'ACCOUNT_CONDITIONAL': saved['ACCOUNT_CONDITIONAL']},
                'platform': {'baseline': frozen['baseline'], 'policy': frozen['policy'],
                             'execution': frozen['design']['execution'], 'costs': frozen['design']['costs'],
                             'state': saved['SHADOW'], 'recomputed': False},
                'actual': actual, 'execution': execution, 'execution_deviations': deviations,
                'monitoring': {'checks': checks, 'corrections': corrections, 'recomputed': False,
                               'same_strategy': checks[0]['complete_protocol_fingerprint'] == frozen['complete_protocol_fingerprint'] if checks else None,
                               'qualification_issued': False},
                'curves': {'SHADOW': {'continuous_performance': True, 'points': saved['SHADOW']['curve']},
                           'ACTUAL': {'continuous_performance': False, 'points': [] if valuation is None else [
                               {'as_of': valuation['as_of'], 'net_assets': valuation['facts']['net_assets'],
                                'valuation_id': valuation['valuation_id'], 'origin_at': valuation['origin_at']}]},
                           'HISTORICAL': {'continuous_performance': False, 'points': [], 'reason': 'PREDICTION_DIAGNOSTICS_ONLY'},
                           'ACCOUNT_CONDITIONAL': {'continuous_performance': False, 'points': [], 'reason': 'ONE_SNAPSHOT_NOT_CONTINUOUS_NAV'}},
                'comparison': {'status': 'NOT_COMPARABLE', 'reasons': ['COMPARABILITY_NOT_ESTABLISHED' if valuation else 'NO_SAVED_VALUATION_SELECTED'],
                               'window': {'shadow': [frozen['baseline'], saved['SHADOW']['through_date']],
                                          'actual': [valuation['origin_at'], valuation['as_of']] if valuation else None},
                               'conditions': {'baseline': 'NOT_ESTABLISHED', 'cash_flows': 'NOT_ESTABLISHED',
                                              'positions': 'NOT_ESTABLISHED', 'scope': 'NOT_ESTABLISHED', 'execution': 'NOT_ESTABLISHED'},
                               'return_difference': None, 'causal_attribution': False}}

    @staticmethod
    def interval(row, start, end):
        result = {'start_event': start, 'end_event': end, 'start_at': row.get(start), 'end_at': row.get(end),
                  'start_source': row.get(start.replace('_at', '_source')),
                  'end_source': row.get(end.replace('_at', '_source')), 'seconds': None, 'status': 'UNKNOWN'}
        if result['start_at'] and result['end_at']:
            delta = (datetime.fromisoformat(result['end_at']) - datetime.fromisoformat(result['start_at'])).total_seconds()
            result.update(seconds=delta if delta >= 0 else None,
                          status='DESCRIPTIVE_RECORDED_TIMES' if delta >= 0 else 'CLOCK_ORDER_NOT_ESTABLISHED')
        return result

    def execution(self, frozen, decision_id, evaluation_id, intent_id):
        if not decision_id:
            return {'status': 'NO_REGISTERED_ACTION_SELECTED', 'notification_chain': None,
                    'response_seconds': None, 'unlinked_fills': []}, []
        chain = self.notifications.time_chain(decision_id, evaluation_id, intent_id)
        rows = [r for r in self.intents.listing()['intents'] if r['decision_id'] == decision_id
                and r['evaluation_id'] == evaluation_id and (not intent_id or r['intent_id'] == intent_id)]
        allocations = self.intents.allocations()
        account = self.shadow.ledger.account()
        deviations = []
        for row in rows:
            linked = [r for r in allocations if r['intent_id'] == row['intent_id']]
            diagnostics = [{'allocation_id': r['allocation_id'],
                'reported_after_occurrence': self.interval(r, 'occurred_at', 'reported_at'),
                'known_after_report': self.interval(r, 'reported_at', 'known_at'),
                'price_in_proposal_window': Decimal(row['decision']['price_lower_yuan']) <= Decimal(r['price']) <= Decimal(row['decision']['price_upper_yuan']),
                'proposal_fees_yuan': row['decision']['fees_yuan'], 'actual_full_fill_fee': r['fee'],
                'fee_comparison': 'PARTIAL_FILL_NOT_FULL_PROPOSAL' if Decimal(r['allocated_quantity']) != Decimal(row['decision']['quantity']) else 'FULL_FILL_COMPONENTS_NOT_ASSUMED',
                'causal_pnl': None} for r in linked]
            deviations.append({'intent_id': row['intent_id'], 'decision_id': decision_id,
                'evaluation_id': evaluation_id, 'proposal': row['decision'], 'status': row['status'],
                'remaining_quantity': row['remaining_quantity'], 'synced_quantity': row['synced_quantity'],
                'unexecuted_reason': row['resolution'], 'allocations': linked,
                'allocation_diagnostics': diagnostics,
                'fee_resolutions': {r['fill_record_id']: account.get('fee_resolutions', {}).get(r['fill_record_id']) for r in linked},
                'same_strategy': row['decision']['dependencies']['complete_protocol_fingerprint'] == frozen['complete_protocol_fingerprint'],
                'causal_pnl': None, 'time_chain': row['time_chain']})
        associated = {r['fill_record_id'] for r in allocations if r['association_status'] == 'USER_CONFIRMED'}
        unlinked = [r for r in account.get('fills', []) if r['record_id'] not in associated]
        return {'status': 'SAVED_ACTUAL_ACTION', 'notification_chain': chain,
                'response_seconds': None, 'response_reason': 'DELIVERY_AND_ACTION_RESPONSE_ASSOCIATION_NOT_ESTABLISHED',
                'unlinked_fills': unlinked, 'unlinked_association': 'UNKNOWN',
                'fee_allocation': 'FULL_FILL_FEE_NOT_SUMMED_ACROSS_INTENT_ALLOCATIONS'}, deviations

    def metrics(self, db=None):
        if db is None:
            with self.shadow.ledger.connection() as owned:
                return self.metrics(owned)
        records = [json.loads(row[0]) for row in db.execute(
            'SELECT value FROM research_shadow_runs ORDER BY freeze_id,revision')]
        locators = [{key: row[key] for key in ['freeze_id', 'revision', 'through_date', 'input_archive']}
                    | {'namespace': 'SHADOW', 'report_url': '/api/research/reports/' + row['freeze_id']}
                    for row in records]
        conditional = db.execute('SELECT COUNT(*) FROM research_conditional_runs').fetchone()[0]
        return {'shadow_records': {'status': 'CHECKED', 'value': len(records), 'records': locators,
                                   'account_conditional_records': conditional}}

    def text(self, report):
        lines = ['Roll 研究报告 · RESEARCH · 无正式执行或行动推送入口',
                 f"实验 {report['freeze_id']} · 协议 {report['protocol_id']} · 运行 {report['model_run_id']}",
                 f"资格 {report['qualification']['capability']} · {report['evidence_kind']}",
                 '原保存版本未用当前代码重算；未经人工独立复核。',
                 f"比较 {report['comparison']['status']} · {'; '.join(report['comparison']['reasons'])}",
                 '实际与影子差值只能描述，不能归因为执行造成的损益。']
        for namespace, value in report['namespaces'].items():
            lines += [namespace, encode(value)]
        lines += ['原指纹及完整来源', encode({'complete_protocol_fingerprint': report['complete_protocol_fingerprint'], 'original_fingerprints': report['original_fingerprints']}),
                  '资格与验证缺口', encode(report['qualification']), '比较时段与条件限制', encode(report['comparison']),
                  '平台策略结果', encode(report['platform']), '实际用户结果', encode(report['actual']),
                  '执行偏差（不作因果损益归因）', encode(report['execution_deviations']),
                  '原出站与成交时间依据', encode(report['execution']), '保存的监测与修正', encode(report['monitoring']),
                  '分列曲线', encode(report['curves'])]
        return '\n'.join(lines) + '\n'
