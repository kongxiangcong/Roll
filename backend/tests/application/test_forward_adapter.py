"""Agreed pure consumer adapter seam, synthetic facts never real qualification."""
from datetime import date, datetime, timedelta
import pytest
from roll.research.forward import forward_features


def rows():
    return [{'trade_date':(date(2026,7,1)+timedelta(days=i)).isoformat(),'instrument':'SSE:600362',
        'adjustment':'RAW','volume_unit':'SHARE','volume_shares':'10000','close':'100','open':'100','low':'99','high':'101',
        'completion_state':'COMPLETE_REPORTED_HISTORICAL','errors':[],'raw_hash':'method-original',
        'available_at':'2026-07-21T15:10:00+08:00','received_at':'2026-07-21T15:10:00+08:00',
        'known_at':'2026-07-21T15:10:00+08:00','cash_events_effective':[]} for i in range(21)]


def test_current_feature_consumer_preserves_real_receipt_and_economic_cash_semantics():
    facts = rows(); cutoff = datetime.fromisoformat('2026-07-21T16:00:00+08:00')
    result = forward_features(facts,'2026-07-21',cutoff,['a','b','c','d'],True)
    assert result['values'] == [0,0,0,0]
    assert result['availability_basis'] == 'ACTUAL_HOST_RECEIPT_AT_FORWARD_CONSUMER'
    # A 1 yuan effective cash distribution offsets the RAW ex-dividend drop.
    facts[-1]['close']='99'
    facts[-1]['cash_events_effective']=[{'ex_date':'2026-07-21','gross_cash_yuan_per_eligible_share':'1',
        'available_at':'2026-07-21T15:10:00+08:00','source':{'sha256':'method-cash','received_at':'2026-07-21T15:10:00+08:00'}}]
    assert forward_features(facts,'2026-07-21',cutoff,['a','b','c','d'],True)['values'] == [0,0,0,0]
    facts[-1]['cash_events_effective'][0]['source']['received_at']='2026-07-21T17:00:00+08:00'
    with pytest.raises(ValueError,match='CASH_EVENT_NOT_AVAILABLE'):
        forward_features(facts,'2026-07-21',cutoff,['a','b','c','d'],True)


@pytest.mark.parametrize('field,value,reason',[
    ('available_at','2026-07-21T17:00:00+08:00','FORWARD_INPUT_NOT_AVAILABLE'),
    ('received_at','2026-07-21T17:00:00+08:00','FORWARD_INPUT_NOT_AVAILABLE'),
    ('known_at','2026-07-21T17:00:00+08:00','FORWARD_INPUT_NOT_AVAILABLE'),
    ('completion_state','UNCONFIRMED_CURRENT_DAY','FORWARD_INPUT_NOT_COMPLETE'),
    ('volume_shares','NaN','FORWARD_NUMERIC_INPUT_INVALID'),
])
def test_forward_adapter_rejects_unavailable_or_incomplete_external_inputs(field,value,reason):
    facts=rows(); facts[-1][field]=value
    with pytest.raises(ValueError,match=reason):
        forward_features(facts,'2026-07-21',datetime.fromisoformat('2026-07-21T16:00:00+08:00'),['a','b','c','d'],True)
