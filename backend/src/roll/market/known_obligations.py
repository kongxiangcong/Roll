"""Known published cash schedules, never evidence of entitlement or fulfillment."""
from datetime import date


def notice_audit(inventory,window,cutoff):
    start=date.fromisoformat(window['start_date'])
    end=date.fromisoformat(window['end_date']) if window['end_date'] else None
    local_day=date.fromisoformat(cutoff[:10])
    notices=[]
    for event in inventory['events']:
        source=event['source']
        record=date.fromisoformat(event['record_date']);ex=date.fromisoformat(event['ex_date'])
        payment=date.fromisoformat(event['cash_payment_date'])
        if not record<=ex<=payment:raise ValueError('KNOWN_NOTICE_SCHEDULE_DATE_ORDER_UNPROVEN')
        dates=(record,ex,payment)
        relation=('OLDER_SCHEDULE_WITH_RESOLUTION_UNKNOWN' if max(dates)<start else
            'WINDOW_END_UNKNOWN' if end is None else
            'SCHEDULE_INTERSECTS_REFERENCE_WINDOW' if any(start<=day<=end for day in dates) else
            'SCHEDULE_OUTSIDE_REFERENCE_WINDOW_WITH_RESOLUTION_UNKNOWN')
        payment_relation=('BEFORE_CUTOFF_DATE' if payment<local_day else
            'AFTER_CUTOFF_DATE' if payment>local_day else 'ON_CUTOFF_DATE_TIME_UNKNOWN')
        notices.append({'announcement_id':event['event_identity'],'instrument':event['instrument'],
            'record_date':record.isoformat(),'ex_date':ex.isoformat(),'scheduled_payment_date':payment.isoformat(),
            'date_precision':'DATE','published_date':source['publication_date'],
            'publication_precision':source['publication_precision'],'first_available_at':None,
            'source_received_at':source['received_at'],'pdf_raw_hash':source['sha256'],'pdf_bytes':source['bytes'],
            'pdf_source_url':source['url'],'pdf_field_source_locator':event['field_source_locator'],
            'cash_mapping_hash':inventory['mapping_hash'],'window_relation':relation,
            'payment_schedule_relation_to_cutoff':payment_relation,
            'scheduled_obligation':{'kind':'DECLARED_CASH_DISTRIBUTION',
                'gross_cash_yuan_per_eligible_share':event['gross_cash_yuan_per_eligible_share'],
                'actual_owned_amount_yuan':None,'is_actual_cash_event':False},
            'fulfillment_state':'UNKNOWN','cancellation_state':'UNKNOWN','deferral_state':'UNKNOWN',
            'owned_entitlement':'UNKNOWN','resolved_at':None,'resolution_evidence':[],
            'fulfillment_evidence':[],'cancellation_evidence':[],'deferral_evidence':[],
            'actual_account_receipt':None,'historical_pit_claim':False})
    return {'notices':notices,'known_notice_count':len(notices),'confirmed_pending_count':0,
        'resolution_unknown_count':len(notices),'scope':'KNOWN_PUBLISHED_SCHEDULES_NOT_ALL_OLDER_OBLIGATIONS',
        'cash_mapping_hash':inventory['mapping_hash'],'pending_older_obligations_complete':False,
        'complete_action_coverage':False,'historical_pit_claim':False,'account_events_added':0,
        'confirmatory_checkpoints_added':0,'gaps':['KNOWN_OBLIGATION_FULFILLMENT_CANCELLATION_DEFERRAL_UNPROVEN',
            'ALL_OLDER_OBLIGATION_COVERAGE_UNPROVEN','NOTICE_FIRST_AVAILABILITY_AND_REVISION_CHAIN_UNPROVEN'],
        'network_calls':0}
