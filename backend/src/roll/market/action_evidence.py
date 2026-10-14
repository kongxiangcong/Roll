"""Saved action versions and known obligation audits, never account cash facts."""
from datetime import datetime, timezone
from fastapi import HTTPException


def query(assessments, plan_id, known_by):
    cutoff=known_by or datetime.now(timezone.utc)
    if cutoff.tzinfo is None:
        raise HTTPException(422,'ACTION_KNOWLEDGE_CUTOFF_REQUIRES_TIMEZONE')
    if cutoff>datetime.now(timezone.utc):
        raise HTTPException(422,'ACTION_KNOWLEDGE_CUTOFF_IN_FUTURE')
    plan=assessments.prospective.plan(plan_id)
    saved=assessments.assessments(plan_id,cutoff)
    audits=assessments.prospective.post_close.obligations(plan_id,cutoff)
    return {'plan_id':plan_id,'instrument':plan['instrument'],'known_by':cutoff.isoformat(),
        'assessments':saved,'assessment_ids':[v['assessment_id'] for v in saved],
        'known_obligation_audits':audits,'audit_ids':[a['audit_id'] for a in audits],
        'complete_action_coverage':False,'pending_older_obligations_complete':False,
        'revision_cancellation_inventory_complete':False,'account_events_added':0,
        'gaps':sorted(set(['COMPLETE_ACTION_LIFECYCLE_AND_OLDER_OBLIGATION_COVERAGE_UNPROVEN']+
            [g for v in saved+audits for g in v.get('gaps',[])])),
        'network_calls':0,'system_usable':False,'capability':'NOT_GRANTED'}
