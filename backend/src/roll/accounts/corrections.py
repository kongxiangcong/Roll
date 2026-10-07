"""Concrete append replacements for the supported account facts, never deletes."""
import copy

from fastapi import HTTPException
from roll.accounts.cash_events import EVENT_FIELDS
from roll.accounts.reconcile import DECLARATION_FIELDS,RECONCILIATION_FIELDS

FILL_FIELDS={"effective_at","source","instrument","direction","quantity","price","record_id","fill_id","order_id","behavior_context","fee","broker_available_after"}
FEE_FIELDS={"effective_at","source","target_record_id","actual_fee_amount","basis"}
CORRECTION_FIELDS={"effective_at","source","record_id","target_event_id","reason","replacement"}


def fact_command(event):
    if "replacement_command" in event:
        return copy.deepcopy(event["replacement_command"])
    payload=event["payload"]
    kind="FILL" if event["event_type"] in {"BUY_FILL","SELL_FILL"} else payload.get("kind",event["event_type"]) if isinstance(payload,dict) else event["event_type"]
    if kind=="PERMISSION_CONFIRMATION":
        return {"kind":"PERMISSIONS","payload":{"effective_at":event["effective_at"],"source":event["source"],"permission_profile":[{key:p[key] for key in ["market","board","status","basis"]} for p in payload]}}
    fields=FILL_FIELDS if kind=="FILL" else FEE_FIELDS if kind=="FEE_ADJUSTMENT" else DECLARATION_FIELDS if kind=="ACCOUNT_DECLARATION" else RECONCILIATION_FIELDS if kind=="RECONCILIATION" else EVENT_FIELDS.get(kind)
    if fields is None:
        raise HTTPException(422,"初始基线不能冲正；请以有依据的对账记录说明无法重建的历史")
    return {"kind":kind,"payload":{key:payload[key] for key in fields}}


def active_events(events):
    active={e.get("event_id",f"draft:{i}"):copy.deepcopy(e) for i,e in enumerate(events) if e["event_type"]!="CORRECTION"}
    heads={key:key for key in active}
    chain=[]
    for event in events:
        if event["event_type"]!="CORRECTION":
            continue
        payload=event["payload"]
        root=payload["root_event_id"]
        head=event.get("event_id",f"draft-correction:{len(chain)}")
        prior=heads[root]
        if payload["target_event_id"]!=prior:
            raise HTTPException(422,"更正目标不是当前替代链末端，请查回当前关系")
        chain.append({**payload,"event_id":head,"receipt_id":event.get("receipt_id"),"recorded_at":event["recorded_at"],"account_version":event["account_version"],"previous_correction_id":None if prior==root else prior})
        heads[root]=head
        replacement=payload["replacement"]
        if replacement is None:
            active.pop(root,None)
        else:
            active[root]={**event,"effective_at":replacement["payload"]["effective_at"],"replacement_command":replacement,"root_event_id":root}
    # 04's amount correction restates the original item, not a new refund.
    # Apply it immediately after that item's effective time so later legitimate
    # partial settlements see the corrected claim, without changing raw dates.
    for event in active.values():
        payload=event.get("replacement_command",{}).get("payload",event["payload"])
        kind=event.get("replacement_command",{}).get("kind",event["event_type"])
        if kind=="CASH_CORRECTION":
            target=next((e for e in active.values() if isinstance(e.get("replacement_command",{}).get("payload",e["payload"]),dict) and e.get("replacement_command",{}).get("payload",e["payload"]).get("record_id")==payload["target_record_id"]),None)
            if target is not None:event["effective_at"]=target["effective_at"]
    return list(active.values()),chain,heads


def correction_event(payload,history,text_value,timestamp):
    if set(payload)!=CORRECTION_FIELDS:
        raise HTTPException(422,"更正需要原事件ID、原因与完整替代事实（冲正填null）")
    record=text_value(payload["record_id"],"record_id")
    target=text_value(payload["target_event_id"],"target_event_id")
    source=text_value(payload["source"],"source")
    reason=text_value(payload["reason"],"reason")
    active,chain,heads=active_events(history)
    root=next((key for key,head in heads.items() if head==target),None)
    original=next((e for e in history if e.get("event_id")==root),None)
    if original is None:
        raise HTTPException(422,"找不到当前可更正事件；原目标可能已被后继替代")
    original_command=fact_command(original)
    if any((e["payload"].get("record_id")==record if isinstance(e["payload"],dict) else False) for e in history):
        raise HTTPException(422,"更正材料标识已存在，不能重复入账")
    replacement=copy.deepcopy(payload["replacement"])
    if replacement is not None:
        if not isinstance(replacement,dict) or set(replacement)!={"kind","payload"} or replacement["kind"]!=original_command["kind"] or not isinstance(replacement["payload"],dict):
            raise HTTPException(422,"替代必须是原事实类型的完整命令；不变的原记录身份需保留")
        replacement["payload"]["effective_at"]=timestamp(replacement["payload"].get("effective_at"))
        from datetime import datetime
        baseline=next(e for e in history if e["event_type"]=="INITIAL_CASH")
        if datetime.fromisoformat(replacement["payload"]["effective_at"])<datetime.fromisoformat(baseline["effective_at"]):
            raise HTTPException(422,"替代事实早于初始基线，无法重建基线前历史")
        for identity in ["record_id","target_record_id"]:
            if identity in original_command["payload"] and text_value(replacement["payload"].get(identity),identity)!=text_value(original_command["payload"][identity],identity):
                raise HTTPException(422,"替代事实需保留原记录及关联身份")
    return {"event_type":"CORRECTION","effective_at":timestamp(payload["effective_at"]),"source":source,"payload":{
        **payload,"record_id":record,"target_event_id":target,"reason":reason,"source":source,"root_event_id":root,"replacement":replacement}}
