"""Dated source arithmetic diagnostics, never manufacture an all-session bar."""
import json
from datetime import datetime, time
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext
from pathlib import Path

from fastapi import HTTPException
from roll.market.rules import SHANGHAI

REFERENCE = Path(__file__).parent / 'reference/daily-session-20261020'
MANIFEST = 'be39539e657c7497026230899f853252b71baf289ac531580a83fdd7f101afd1'


def number(value):
    if isinstance(value, bool) or value is None: raise HTTPException(409, 'SESSION_NUMERIC_FIELD_MISSING')
    try:
        value = Decimal(str(value))
    except InvalidOperation as exc:
        raise HTTPException(409, 'SESSION_NUMERIC_FIELD_INVALID') from exc
    if not value.is_finite() or value < 0: raise HTTPException(409, 'SESSION_NUMERIC_FIELD_INVALID')
    return value


def statistic(body, day):
    value = json.loads(body)
    rows = value.get('result')
    if value.get('sqlId') != 'COMMON_SSE_CP_GPJCTPZ_GPLB_CJGK_MRGK_C' or value.get('actionErrors') or value.get('fieldErrors'):
        raise HTTPException(409, 'SESSION_STATISTIC_CONTRACT_MISMATCH')
    if not isinstance(rows, list) or len(rows) != 1 or rows[0].get('SEC_CODE') != '600362' or rows[0].get('TX_DATE') != day.replace('-', ''):
        raise HTTPException(409, 'SESSION_STATISTIC_DATE_OR_SECURITY_MISMATCH')
    return rows[0]


def assess(rows, bodies, catalog):
    if len({r['trade_date'] for r in rows}) != len(rows): raise HTTPException(409, 'SESSION_DUPLICATE_PROVIDER_DATE')
    results = []
    with localcontext() as context:
        context.prec = 40
        for fact in rows:
            if fact.get('source_id') != 'baostock-daily' or fact.get('adjustment') != 'RAW' or fact.get('instrument') != 'SSE:600362' or fact.get('errors'):
                raise HTTPException(409, 'SESSION_PROVIDER_ROW_SCOPE_OR_QUALITY_UNPROVEN')
            day = fact['trade_date']; case = catalog['cases'].get(day)
            role = case['statistic'] if case else catalog['other_statistics'].get(day)
            if not role: raise HTTPException(409, 'SESSION_DATE_NOT_IN_FIXED_SOURCE_BATCH')
            reported = statistic(bodies[role], day)
            volume, amount = number(fact['volume_shares']), number(fact['amount_yuan'])
            total_volume, total_amount = number(reported['TRADE_VOL']) * 10000, number(reported['TRADE_AMT']) * 10000
            received = datetime.fromisoformat(fact['received_at']).astimezone(SHANGHAI)
            row = {'trade_date': day, 'bao_volume_shares': str(volume), 'bao_amount_cny': str(amount),
                   'sse_stat_volume_shares_display': str(total_volume), 'sse_stat_amount_cny_display': str(total_amount),
                   'display_minus_bao_volume': str(total_volume-volume), 'display_minus_bao_amount': str(total_amount-amount),
                   'bao_original_completion_state': fact['completion_state'],
                   'provider_declared_ingestion_boundary_reached': day < received.date().isoformat() or (day == received.date().isoformat() and received.time() >= time(17, 30)),
                   'all_session_daily_allowed': False, 'model_daily_input_allowed': False,
                   'explanation': 'SAME_DAY_COMPONENTS_NOT_SAVED', 'gaps': ['ALL_SESSION_SOURCE_ADMISSION_NOT_ESTABLISHED']}
            if case:
                snap = json.loads(bodies[case['snapshot']], parse_float=Decimal)
                if snap.get('code') != '600362' or str(snap.get('date')) != day.replace('-', '') or len(snap.get('snap', [])) != 24:
                    raise HTTPException(409, 'SESSION_SNAPSHOT_DATE_OR_SELECT_MISMATCH')
                fields = snap['snap']
                ordinary_volume, ordinary_amount = number(fields[5]), number(fields[4])
                fp_volume, fp_amount = number(fields[19]), number(fields[20])
                price = number(fields[1])
                if fp_volume * price != fp_amount: raise HTTPException(409, 'SESSION_FIXED_PRICE_COMPONENT_CONFLICT')
                ordinary_closed = isinstance(fields[12], str) and fields[12][:1] == 'E'
                fp_closed = isinstance(fields[23], str) and fields[23][:1] == 'D'
                volume_sum, amount_sum = volume+fp_volume, amount+fp_amount
                compatible = ((volume_sum/10000).quantize(Decimal('.01'), rounding=ROUND_HALF_UP) == number(reported['TRADE_VOL']) and
                              (amount_sum/10000).quantize(Decimal('.01'), rounding=ROUND_HALF_UP) == number(reported['TRADE_AMT']))
                row.update(sse_ordinary_volume_shares=str(ordinary_volume), sse_ordinary_amount_cny=str(ordinary_amount),
                           bao_minus_ordinary_volume=str(volume-ordinary_volume), bao_minus_ordinary_amount=str(amount-ordinary_amount),
                           fp_volume_shares=str(fp_volume), fp_amount_cny=str(fp_amount), fp_price_cny=str(price),
                           bao_plus_fp_volume_diagnostic=str(volume_sum), bao_plus_fp_amount_diagnostic=str(amount_sum),
                           display_minus_component_volume=str(total_volume-volume_sum), display_minus_component_amount=str(total_amount-amount_sum),
                           ordinary_phase_original=fields[12], fp_phase_original=fields[23],
                           ordinary_closed_display=ordinary_closed, fp_closed_display=fp_closed,
                           two_decimal_presentation_compatible=compatible,
                           comparison_policy='LOCAL_HALF_UP_2DP_DIAGNOSTIC_NOT_SERVER_PRECISION_CONTRACT',
                           explanation='POST_CLOSE_COMPONENTS_PRESENTATION_COMPATIBLE' if compatible and volume == ordinary_volume and ordinary_closed and fp_closed else 'COMPONENT_RELATION_NOT_ESTABLISHED')
                source = catalog['sources'][case['block']]
                if source.get('original_complete') and source.get('status') == 200 and not source.get('error'):
                    block = json.loads(bodies[case['block']]); page = block.get('pageHelp', {})
                    if block.get('sqlId') != 'COMMON_SSE_XXPL_JYXXPL_DZJYXX_L_1' or page.get('data') != block.get('result'):
                        raise HTTPException(409, 'SESSION_BLOCK_RESPONSE_CONFLICT')
                    row.update(block_query_state='SOURCE_REPORTED_EMPTY_PAGE' if page.get('total') == 0 and block.get('result') == [] else 'REPORTED_ROWS_REQUIRE_SEPARATE_SCOPE_REVIEW',
                               block_reported_total=page.get('total'), block_negative_coverage_verified=False)
                else:
                    row.update(block_query_state='SOURCE_FAILED_NOT_ZERO', block_reported_total=None, block_negative_coverage_verified=False)
                    row['gaps'].append('BLOCK_SOURCE_FAILURE_NOT_ZERO:' + str(source.get('error')))
                row['gaps'] += ['BAOSTOCK_SESSION_SCOPE_UNDECLARED', 'SSE_STATISTIC_SERVER_QUANTIZATION_UNDECLARED',
                                'ALL_REQUIRED_TRANSACTION_CATEGORY_COVERAGE_UNPROVEN']
            results.append(row)
    return {'session_rows': results, 'rule_effective_from': catalog['effective_from'],
            'rule_summary': 'From2026-07-06 A-share afterclose15:05-15:30, fixedprice volume/amount enter daily totals afterend (3.7.10); block separate (3.6.12)',
            'source_independence': 'UNPROVEN_SAME_SSE_UPSTREAM', 'qualified_total_bar': None,
            'gaps': ['LOCAL_SUM_IS_DIAGNOSTIC_NOT_SUPPLIER_FULL_SESSION_KLINE', 'TICKET02_FULL_SESSION_ADMISSION_STILL_PARTIAL']}
