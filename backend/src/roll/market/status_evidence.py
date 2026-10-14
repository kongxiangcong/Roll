"""Read saved status observations at a cutoff without inferring normal trading."""
from datetime import datetime, timezone
from fastapi import HTTPException


def query(post_close, plan_id, known_by):
    if known_by.tzinfo is None:
        raise HTTPException(422,'STATUS_KNOWLEDGE_CUTOFF_REQUIRES_TIMEZONE')
    if known_by > datetime.now(timezone.utc):
        raise HTTPException(422,'STATUS_KNOWLEDGE_CUTOFF_IN_FUTURE')
    plan=post_close.prospective.plan(plan_id)
    company=post_close.company_contracts.receipts(plan_id,known_by)
    suspension=post_close.suspension_receipts(plan_id,known_by)
    stock=post_close.stock_suspensions.receipts(plan_id,known_by)
    # These pinned producers explicitly lack full effective status/negative coverage.
    # Listing descriptions and scheduled end dates remain observations, not grants.
    return {'instrument':plan['instrument'],'plan_id':plan_id,'known_by':known_by.isoformat(),
        'state':'UNKNOWN','effective_at':None,'negative_coverage_verified':False,
        'company_observations':[r['company_fact'] for r in company if r.get('company_fact')],
        'suspension_observations':[e for r in suspension+stock for e in r.get('events',[])],
        'company_receipts':company,'suspension_receipts':suspension,'stock_suspension_receipts':stock,
        'receipt_ids':[r['receipt_id'] for r in company+suspension+stock],
        'gaps':sorted(set(['FULL_EFFECTIVE_STATUS_AND_NEGATIVE_COVERAGE_UNPROVEN']+
            [g for r in company+suspension+stock for g in r.get('gaps',[])])),
        'network_calls':0,'system_usable':False,'capability':'NOT_GRANTED'}
