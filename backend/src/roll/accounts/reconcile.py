"""User declarations and field-specific reconciliation in the existing ledger."""
import copy
from datetime import datetime
from decimal import Decimal
from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel,ConfigDict
from roll.accounts.fills import money,update_fee_state

SCOPES=["TRADES","ORDERS","CASH","EQUITY"]
DECLARATION_FIELDS={"effective_at","source","record_id","scope","changes","basis"}
RECONCILIATION_FIELDS={"effective_at","source","record_id","reason","snapshot","resolved_draft_ids"}


class UseCheck(BaseModel):
    model_config=ConfigDict(extra="forbid")
    purpose: Literal["MARKET_OBSERVATION","ACCOUNT_ANALYSIS","NEW_RISK","REDUCTION"]
    required_as_of: str


def declare(payload,account,text_value):
    if set(payload)!=DECLARATION_FIELDS:
        raise HTTPException(422,"账户声明需要明确范围、截至时点、变化状态及核对依据")
    scope=payload["scope"]
    if not isinstance(scope,list) or not scope or any(s not in SCOPES for s in scope) or len(set(scope))!=len(scope):
        raise HTTPException(422,"声明范围为TRADES/ORDERS/CASH/EQUITY的不重复非空列表")
    if not isinstance(payload["changes"],str) or payload["changes"] not in {"NONE","UNRECORDED","EXTERNAL_ORDER_PENDING"}:
        raise HTTPException(422,"声明变化需明确无变化、未补录或外部委托待结果")
    record=text_value(payload["record_id"],"record_id")
    if any(d["record_id"]==record for d in account.get("declarations",[])):
        raise HTTPException(422,"声明标识已存在")
    result={**payload,"record_id":record,"basis":text_value(payload["basis"],"basis"),"confirmed_as_of":payload["effective_at"]}
    projection=copy.deepcopy(account)
    projection.setdefault("declarations",[]).append(result)
    return projection,[{"event_type":"ACCOUNT_DECLARATION","payload":result}]


def consistency(account,pending):
    pending=[d for d in pending if d["command"]["kind"] not in {"PERMISSIONS","BASELINE"}]
    if any(d["status"]=="QUARANTINED" or d["command"]["kind"]=="RECONCILIATION" for d in pending):
        return "RECONCILE_REQUIRED",["存在待核原始材料或尚未处理的券商差异"]
    latest={}
    for d in account.get("declarations",[]):
        for scope in d["scope"]:latest[scope]=d
    if pending or any(d["changes"]!="NONE" for d in latest.values()):
        return "UPDATE_PENDING",["存在未确认草稿、未补录变化或外部委托待结果，先核对实际事实"]
    if account.get("fees_pending") or account.get("rights_fee_breakdown_pending"):
        return "RECONCILE_REQUIRED",["费用或配股费用分拆仍待核，不输出确定净结果"]
    if account.get("reconciliation",{}).get("unresolved"):
        return "RECONCILE_REQUIRED",["券商核对尚有未决或未知字段，查看分列差异"]
    return account["state"],[]


def use_check(account,pending,command,timestamp):
    required=timestamp(command.required_as_of,"required_as_of")
    scope=[] if command.purpose=="MARKET_OBSERVATION" else SCOPES if command.purpose in {"NEW_RISK","REDUCTION"} else ["TRADES","CASH","EQUITY"]
    state,reasons=consistency(account,pending)
    missing=[]
    for item in scope:
        matches=[d for d in account.get("declarations",[]) if item in d["scope"] and d["changes"]=="NONE" and datetime.fromisoformat(d["confirmed_as_of"])>=datetime.fromisoformat(required) and datetime.fromisoformat(d["recorded_at"])>=datetime.fromisoformat(account["latest_fact_recorded_at"])]
        if not matches:missing.append(item)
    if scope and state not in {"UPDATE_PENDING","RECONCILE_REQUIRED"}:
        if account["cash_balance"] is None or (command.purpose=="NEW_RISK" and (account["broker_available"] is None or account["broker_frozen"] is None)) or (command.purpose=="REDUCTION" and any(p["sellable_quantity"] is None for p in account["positions"])):
            state="RECONCILE_REQUIRED"
            reasons.append("所需资金或可卖数量未知；减仓用途先核对可卖数量")
        elif missing:
            state="STALE_DECLARATION"
            reasons.append("本次用途缺少所需范围/截至时点的无变化声明，无需补每日记录")
        else:
            state="CONFIRMED_AS_OF"
    return {"purpose":command.purpose,"required_as_of":required,"account_version":account["version"],"state":state,
            "allowed":not scope or state=="CONFIRMED_AS_OF","required_scope":scope,"missing_scope":missing,"reasons":reasons,
            "next_step":"先同步事实或核对差异，再对本次所需范围声明" if scope and state!="CONFIRMED_AS_OF" else "仅账户事实检查通过；正式资格仍须独立核验",
            "known_positions":account["positions"],"executable_quantity":None,"independent_market_observation_allowed":True}


def normalize_snapshot(value,number,text_value):
    from roll.accounts.cash_events import instrument
    scalars=["cash_balance","broker_available","broker_frozen","withdrawable","investment_income","investment_expenses"]
    if not isinstance(value,dict) or set(value)!=set(scalars)|{"positions","pending_items"}:
        raise HTTPException(422,"快照需要分列现金、券商可用/冻结/可取、持仓、待结算及实际收入/税费；未知填null")
    result={k:number(value[k],k,nullable=True) for k in scalars}
    result.update(positions=[],pending_items=[])
    for group,identity,fields in [("positions","instrument",{"instrument","quantity","sellable_quantity"}),("pending_items","record_id",{"record_id","outstanding_amount"})]:
        if not isinstance(value[group],list):raise HTTPException(422,group+"需要列表")
        seen=set()
        for item in value[group]:
            if not isinstance(item,dict) or set(item)!=fields:raise HTTPException(422,group+"字段缺失或存在未知字段")
            key=instrument(item[identity],text_value) if identity=="instrument" else text_value(item[identity],identity)
            if key is None or key in seen:raise HTTPException(422,group+"标识不能为空或重复")
            seen.add(key)
            row={identity:key,**{f:number(item[f],f,8 if group=="positions" else 2,nullable=True) for f in fields-{identity}}}
            if group=="positions" and row["quantity"] is not None and row["sellable_quantity"] is not None and Decimal(row["sellable_quantity"])>Decimal(row["quantity"]):
                raise HTTPException(422,"券商可卖数量不能超过其报告数量")
            result[group].append(row)
    return result


def differences(account,snapshot):
    rows=[]
    def add(field,mirror,broker,identity=None):
        known=mirror is not None and broker is not None
        rows.append({"field":field,"identity":identity,"mirror":mirror,"broker":broker,
                     "status":"UNKNOWN" if not known else "MATCH" if Decimal(mirror)==Decimal(broker) else "MISMATCH",
                     "delta":money(Decimal(broker)-Decimal(mirror)) if known and field not in {"quantity","sellable_quantity"} else format(Decimal(broker)-Decimal(mirror),"f") if known else None})
    for field in ["cash_balance","broker_available","broker_frozen","withdrawable","investment_income","investment_expenses"]:
        add(field,account.get(field,"0.00") if field in {"investment_income","investment_expenses"} else account[field],snapshot[field])
    mirror={p["instrument"]:p for p in account["positions"]}
    observed={p["instrument"]:p for p in snapshot["positions"]}
    for key in sorted(mirror.keys()|observed.keys()):
        for field in ["quantity","sellable_quantity"]:
            add(field,mirror.get(key,{"quantity":"0","sellable_quantity":"0"})[field],observed.get(key,{}).get(field),key)
    claims={p["record_id"]:p["outstanding_amount"] for p in account.get("pending_items",[])}
    observations={p["record_id"]:p["outstanding_amount"] for p in snapshot["pending_items"]}
    for key in sorted(claims.keys()|observations.keys()):add("outstanding_amount",claims.get(key),observations.get(key),key)
    return rows


def reconcile_snapshot(payload,account,number,text_value):
    if set(payload)!=RECONCILIATION_FIELDS:
        raise HTTPException(422,"对账需要逐项快照、来源、原因、标识及明确处理的原草稿引用")
    snapshot=normalize_snapshot(payload["snapshot"],number,text_value)
    record=text_value(payload["record_id"],"record_id")
    if any(r["record_id"]==record for r in account.get("reconciliations",[])):
        raise HTTPException(422,"对账材料标识重复")
    if not isinstance(payload["resolved_draft_ids"],list):
        raise HTTPException(422,"已处理草稿引用需要不重复列表")
    resolved=[text_value(d,"resolved_draft_ids") for d in payload["resolved_draft_ids"]]
    if len(set(resolved))!=len(resolved):raise HTTPException(422,"已处理草稿引用需要不重复列表")
    projection=copy.deepcopy(account)
    before=differences(account,snapshot)
    cash_delta="0.00" if snapshot["cash_balance"] is None else money(Decimal(snapshot["cash_balance"])-Decimal(account["cash_balance"]))
    if snapshot["cash_balance"] is not None:projection["cash_balance"]=snapshot["cash_balance"]
    for field in ["broker_available","broker_frozen","withdrawable"]:
        projection[field]=snapshot[field]
        projection[field+"_as_of"]=payload["effective_at"] if snapshot[field] is not None else None
    projection["broker_available_basis"]="USER_RECONCILED"
    projection["conservative_available"]=snapshot["broker_available"]
    projection["conservative_available_basis"]="USER_CONFIRMED" if snapshot["broker_available"] is not None else "券商可用未知"
    for value in snapshot["positions"]:
        position=next((p for p in projection["positions"] if p["instrument"]==value["instrument"]),None)
        if value["quantity"] is None:continue
        if position is None:
            position={"instrument":value["instrument"],"quantity":"0","sellable_quantity":None,"reference_cost":None,"buy_time":None,"historical_fees":None}
            projection["positions"].append(position)
        if Decimal(position["quantity"])!=Decimal(value["quantity"]):
            for lot in projection.setdefault("lots",[]):
                if lot["instrument"]==value["instrument"] and Decimal(lot["remaining_quantity"])>0:
                    lot.update(reconciliation_closed_quantity=lot["remaining_quantity"],reconciliation_closed_cost=lot["remaining_cost"],remaining_quantity="0",remaining_cost=None if lot["remaining_cost"] is None else "0.00")
            if Decimal(value["quantity"])>0:
                projection["lots"].append({"lot_id":"reconcile:"+record+":"+value["instrument"],"instrument":value["instrument"],"original_quantity":value["quantity"],"remaining_quantity":value["quantity"],"original_cost":None,"remaining_cost":None,"cost_basis":"UNKNOWN","effective_at":payload["effective_at"]})
            position["reference_cost"]=None
            projection["realized_gain"]=None
        position.update(quantity=value["quantity"],sellable_quantity=value["sellable_quantity"])
    update_fee_state(projection)
    after=differences(projection,snapshot)
    unresolved=[d for d in after if d["status"]=="MISMATCH" or (d["status"]=="UNKNOWN" and d["field"] in {"cash_balance","broker_available","broker_frozen","quantity","sellable_quantity","outstanding_amount"})]
    row={**payload,"record_id":record,"reason":text_value(payload["reason"],"reason"),"snapshot":snapshot,"resolved_draft_ids":resolved,
         "differences_before":before,"unresolved":unresolved,"cash_alignment_delta":cash_delta,"historical_cash_classification":"UNEXPLAINED_ALIGNMENT" if cash_delta!="0.00" else "NO_CASH_CHANGE",
         "limitation":"快照对齐不能重建漏记历史；现金差额不记为收入或外部投入，数量重建的成本保持未知"}
    projection.setdefault("reconciliations",[]).append(row)
    projection["reconciliation"]=row
    return projection,[{"event_type":"RECONCILIATION","payload":row}]
