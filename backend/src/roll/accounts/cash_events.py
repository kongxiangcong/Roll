"""User-confirmed cash and equity facts, projected by the single ledger writer."""
import copy
import re
from decimal import Decimal, ROUND_HALF_UP

from fastapi import HTTPException
from roll.accounts.fills import money,update_fee_state


CASH_KINDS={"CASH_IN","CASH_OUT","DIVIDEND","INTEREST","TAX","FEE"}
CASH_FIELDS={"effective_at","source","record_id","amount","instrument","basis","broker_available_after"}
PENDING_FIELDS={"effective_at","source","record_id","item_type","amount","instrument","basis"}
SETTLEMENT_FIELDS={"effective_at","source","record_id","target_record_id","amount","basis","broker_available_after"}
CORRECTION_FIELDS={"effective_at","source","record_id","target_record_id","corrected_amount","basis","broker_available_after"}
SHARE_FIELDS={"effective_at","source","record_id","instrument","new_quantity","basis"}
RIGHTS_FIELDS={"effective_at","source","record_id","instrument","quantity","amount","fee_amount","basis","broker_available_after"}
EVENT_FIELDS={**{kind:CASH_FIELDS for kind in CASH_KINDS},"PENDING_ITEM":PENDING_FIELDS,"SETTLEMENT":SETTLEMENT_FIELDS,"CASH_CORRECTION":CORRECTION_FIELDS,"SHARE_CHANGE":SHARE_FIELDS,"RIGHTS_SUBSCRIPTION":RIGHTS_FIELDS}


def instrument(value,text_value):
    if value is None:
        return None
    result=text_value(value,"instrument")
    if not re.fullmatch(r"(?:SSE|SZSE|BSE):\d{6}",result):
        raise HTTPException(422,"证券必须为交易所:六位代码")
    return result


def actual_cash(kind,payload,account,number,text_value):
    if set(payload)!=EVENT_FIELDS[kind]:
        raise HTTPException(422,"现金事件字段缺失或存在未知字段")
    if account["version"]==0:
        raise HTTPException(409,"请先建立账户基线")
    record=text_value(payload["record_id"],"record_id")
    # Normalize only projected identity; raw commands and CSV rows stay intact.
    payload={**payload,"record_id":record}
    if "target_record_id" in payload:
        payload["target_record_id"]=text_value(payload["target_record_id"],"target_record_id")
    if any(item["record_id"]==record for item in account.get("cash_records",[])+account.get("share_records",[])):
        raise HTTPException(422,"流水标识已存在，请核对原记录，不重复入账")
    if kind=="SHARE_CHANGE":
        return share_change(payload,account,number,text_value)
    if kind=="RIGHTS_SUBSCRIPTION":
        if any(item["record_id"]==record for item in account.get("fills",[])):
            raise HTTPException(422,"配股标识与已确认成交重复，请核对原记录")
        return rights_subscription(payload,account,number,text_value)
    if kind=="CASH_CORRECTION":
        return cash_correction(payload,account,number,text_value)
    amount=number(payload["amount"],"amount")
    if Decimal(amount)<=0:
        raise HTTPException(422,"实际现金流水金额需大于零")
    item_type=kind
    if kind=="PENDING_ITEM":
        item_type=payload["item_type"]
        if not isinstance(item_type,str) or item_type not in {"DIVIDEND","INTEREST","TAX","FEE"}:
            raise HTTPException(422,"待结算类别必须为分红/利息/税/费")
    elif kind=="SETTLEMENT":
        target=text_value(payload["target_record_id"],"target_record_id")
        pending=next((item for item in account.get("pending_items",[]) if item["record_id"]==target),None)
        if pending is None or Decimal(amount)>Decimal(pending["outstanding_amount"]):
            raise HTTPException(422,"关联待结算不存在或结算超过剩余余额")
        item_type=pending["item_type"]
    category={"CASH_IN":"EXTERNAL_IN","CASH_OUT":"EXTERNAL_OUT","DIVIDEND":"INVESTMENT_INCOME",
              "INTEREST":"INVESTMENT_INCOME","TAX":"INVESTMENT_EXPENSE","FEE":"INVESTMENT_EXPENSE"}[item_type]
    record_payload={**payload,"record_id":record,"amount":amount,"kind":kind,"flow_category":category,
                    "basis":text_value(payload["basis"],"basis")}
    if "instrument" in payload:
        record_payload["instrument"]=instrument(payload["instrument"],text_value)
    projection=copy.deepcopy(account)
    sign=1 if category in {"EXTERNAL_IN","INVESTMENT_INCOME"} else -1
    projection["cash_balance"]=money(Decimal(account["cash_balance"])+(0 if kind=="PENDING_ITEM" else sign*Decimal(amount)))
    if Decimal(projection["cash_balance"])<0:
        raise HTTPException(422,"流水导致负现金，需要核对漏记资金")
    projection.setdefault("cash_records",[]).append(record_payload)
    refresh_balances(projection)
    if kind=="PENDING_ITEM":
        for field in ["broker_available","broker_frozen","withdrawable"]:
            projection.setdefault(field+"_as_of",account["effective_at"] if account[field] is not None else None)
        return projection,[{"event_type":kind,"payload":record_payload}]
    projection["broker_available"]=number(payload["broker_available_after"],"broker_available_after",nullable=True)
    projection["broker_available_as_of"]=payload["effective_at"] if projection["broker_available"] is not None else None
    projection["broker_available_basis"]="USER_CONFIRMED" if projection["broker_available"] is not None else "UNKNOWN_AFTER_CASH_EVENT"
    projection["conservative_available"]=projection["broker_available"]
    projection["conservative_available_basis"]="USER_CONFIRMED" if projection["broker_available"] is not None else "当前券商快照未知"
    projection["broker_frozen_as_of"]=account.get("broker_frozen_as_of",account["effective_at"])
    projection["withdrawable_as_of"]=account.get("withdrawable_as_of",account["effective_at"])
    return projection,[{"event_type":kind,"payload":record_payload}]


def refresh_balances(account):
    categories={"EXTERNAL_IN":"external_cash_in","EXTERNAL_OUT":"external_cash_out","INVESTMENT_INCOME":"investment_income","INVESTMENT_EXPENSE":"investment_expenses"}
    totals={value:Decimal(0) for value in categories.values()}
    pending=[]
    records=account.get("cash_records",[])
    resolutions=account.get("cash_resolutions",{})
    def resolved(record):
        return Decimal(resolutions.get(record["record_id"],{}).get("amount",record["amount"]))
    for record in records:
        if record["kind"]=="PENDING_ITEM":
            settlements=[r for r in records if r["kind"]=="SETTLEMENT" and r["target_record_id"]==record["record_id"]]
            settled=sum((resolved(r) for r in settlements),Decimal(0))
            remaining=resolved(record)-settled
            if remaining<0:
                raise HTTPException(422,"更正后结算总额超过确认待结算金额")
            pending.append({**record,"resolved_amount":money(resolved(record)),"settled_amount":money(settled),"outstanding_amount":money(remaining),
                            "status":"CANCELLED" if resolved(record)==0 else "OPEN" if settled==0 else "SETTLED" if remaining==0 else "PARTIAL",
                            "settlement_ids":[r["record_id"] for r in settlements]})
        elif record["kind"]!="CASH_CORRECTION":
            totals[categories[record["flow_category"]]]+=resolved(record)
    account.update({key:money(value) for key,value in totals.items()})
    account["pending_items"]=pending
    account["pending_income"]=money(sum((Decimal(item["outstanding_amount"]) for item in pending if item["flow_category"]=="INVESTMENT_INCOME"),Decimal(0)))
    account["pending_expenses"]=money(sum((Decimal(item["outstanding_amount"]) for item in pending if item["flow_category"]=="INVESTMENT_EXPENSE"),Decimal(0)))


def stamp_cash(account,payload,**metadata):
    for record in account.get("cash_records",[])+account.get("pending_items",[])+account.get("share_records",[]):
        if record["record_id"]==payload["record_id"]:
            record.update(metadata)


def cash_correction(payload,account,number,text_value):
    target=text_value(payload["target_record_id"],"target_record_id")
    original=next((r for r in account.get("cash_records",[]) if r["record_id"]==target and r["kind"]!="CASH_CORRECTION"),None)
    if original is None:
        raise HTTPException(422,"找不到可更正的已确认现金/待结算记录")
    amount=number(payload["corrected_amount"],"corrected_amount")
    basis=text_value(payload["basis"],"basis")
    previous=account.get("cash_resolutions",{}).get(target,{})
    old_amount=previous.get("amount",original["amount"])
    delta=Decimal(amount)-Decimal(old_amount)
    projection=copy.deepcopy(account)
    sign=1 if original["flow_category"] in {"EXTERNAL_IN","INVESTMENT_INCOME"} else -1
    cash_delta=Decimal(0) if original["kind"]=="PENDING_ITEM" else sign*delta
    projection["cash_balance"]=money(Decimal(account["cash_balance"])+cash_delta)
    if Decimal(projection["cash_balance"])<0:
        raise HTTPException(422,"更正导致负现金，需要核对原记录")
    record={**payload,"kind":"CASH_CORRECTION","record_id":text_value(payload["record_id"],"record_id"),
            "basis":basis,"corrected_amount":amount,"previous_amount":old_amount,"cash_delta":money(cash_delta),
            "previous_correction_id":previous.get("correction_id"),"flow_category":"ADJUSTMENT"}
    projection.setdefault("cash_records",[]).append(record)
    projection.setdefault("cash_resolutions",{})[target]={"amount":amount,"correction_id":record["record_id"],"basis":basis,"effective_at":payload["effective_at"]}
    refresh_balances(projection)
    if original["kind"]=="PENDING_ITEM":
        if payload["broker_available_after"] is not None:
            raise HTTPException(422,"待结算金额更正不确认券商可用资金")
    else:
        projection["broker_available"]=number(payload["broker_available_after"],"broker_available_after",nullable=True)
        projection["broker_available_as_of"]=payload["effective_at"] if projection["broker_available"] is not None else None
        projection["broker_available_basis"]="USER_CONFIRMED" if projection["broker_available"] is not None else "UNKNOWN_AFTER_CASH_CORRECTION"
        projection["conservative_available"]=projection["broker_available"]
        projection["conservative_available_basis"]="USER_CONFIRMED" if projection["broker_available"] is not None else "当前券商快照未知"
        projection["broker_frozen_as_of"]=account.get("broker_frozen_as_of",account["effective_at"])
        projection["withdrawable_as_of"]=account.get("withdrawable_as_of",account["effective_at"])
    return projection,[{"event_type":"CASH_CORRECTION","payload":record}]


def share_change(payload,account,number,text_value):
    security=instrument(payload["instrument"],text_value)
    if security is None:
        raise HTTPException(422,"股份变动需明确证券")
    quantity=number(payload["new_quantity"],"new_quantity",8)
    if Decimal(quantity)<=0:
        raise HTTPException(422,"股份变动后数量须大于零")
    projection=copy.deepcopy(account)
    position=next((p for p in projection["positions"] if p["instrument"]==security),None)
    if position is None:
        raise HTTPException(422,"股份变动需核对原已记录持仓")
    old_quantity=Decimal(position["quantity"])
    lots=projection.setdefault("lots",[])
    active=[lot for lot in lots if lot["instrument"]==security and Decimal(lot["remaining_quantity"])>0]
    if not active:
        reference=position["reference_cost"]
        cost=None if reference is None else money(Decimal(reference)*old_quantity)
        lot={"lot_id":"baseline:"+security,"instrument":security,"original_quantity":str(old_quantity),
             "remaining_quantity":str(old_quantity),"original_cost":cost,"remaining_cost":cost,
             "cost_basis":"UNKNOWN" if reference is None else "REFERENCE","effective_at":account["effective_at"]}
        lots.append(lot)
        active=[lot]
    children=[]
    remainder=Decimal(quantity)
    for index,lot in enumerate(active):
        new_quantity=remainder if index==len(active)-1 else (Decimal(lot["remaining_quantity"])*Decimal(quantity)/old_quantity).quantize(Decimal("0.00000001"),rounding=ROUND_HALF_UP)
        remainder-=new_quantity
        if new_quantity<=0:
            raise HTTPException(422,"变动后批次数量低于八位精度，需要核对批次数量")
        child={"lot_id":payload["record_id"]+":"+lot["lot_id"],"instrument":security,
               "original_quantity":format(new_quantity,"f"),"remaining_quantity":format(new_quantity,"f"),
               "original_cost":lot["remaining_cost"],"remaining_cost":lot["remaining_cost"],
               "cost_basis":lot["cost_basis"],"effective_at":lot["effective_at"],"parent_lot_id":lot["lot_id"]}
        children.append(child)
        lot.update(transferred_quantity=lot["remaining_quantity"],transferred_cost=lot["remaining_cost"],
                   transfer_child_id=child["lot_id"],remaining_quantity="0",remaining_cost=None if lot["remaining_cost"] is None else "0.00")
    lots.extend(children)
    reference_before=position["reference_cost"]
    position.update(quantity=quantity,sellable_quantity=None,reference_cost=None)
    for field in ["broker_available","broker_frozen","withdrawable"]:
        projection.setdefault(field+"_as_of",account["effective_at"] if account[field] is not None else None)
    update_fee_state(projection)
    record={**payload,"kind":"SHARE_CHANGE","record_id":text_value(payload["record_id"],"record_id"),"instrument":security,
            "new_quantity":quantity,"quantity_before":format(old_quantity,"f"),"basis":text_value(payload["basis"],"basis"),
            "cost_after":position["acquisition_cost"],"reference_cost_before":reference_before,"lot_transfers":[{"parent_lot_id":c["parent_lot_id"],"lot_id":c["lot_id"],"quantity":c["original_quantity"],"cost":c["original_cost"]} for c in children]}
    projection.setdefault("share_records",[]).append(record)
    return projection,[{"event_type":"SHARE_CHANGE","payload":record}]


def rights_subscription(payload,account,number,text_value):
    security=instrument(payload["instrument"],text_value)
    quantity=number(payload["quantity"],"quantity",8)
    amount=number(payload["amount"],"amount")
    fee=number(payload["fee_amount"],"fee_amount",nullable=True)
    if security is None or Decimal(quantity)<=0 or Decimal(amount)<=0 or (fee is not None and Decimal(fee)>Decimal(amount)):
        raise HTTPException(422,"配股需明确证券、正数量、实际总支付金额；费用不能超过已付总额")
    projection=copy.deepcopy(account)
    cash=Decimal(account["cash_balance"])-Decimal(amount)
    if cash<0:
        raise HTTPException(422,"配股支付导致负现金，需要核对漏记资金")
    position=next((p for p in projection["positions"] if p["instrument"]==security),None)
    lots=projection.setdefault("lots",[])
    if position is not None and not any(l["instrument"]==security for l in lots):
        reference=position["reference_cost"]
        cost=None if reference is None else money(Decimal(reference)*Decimal(position["quantity"]))
        lots.append({"lot_id":"baseline:"+security,"instrument":security,"original_quantity":position["quantity"],
                     "remaining_quantity":position["quantity"],"original_cost":cost,"remaining_cost":cost,
                     "cost_basis":"UNKNOWN" if reference is None else "REFERENCE","effective_at":account["effective_at"]})
    if position is None:
        position={"instrument":security,"quantity":"0","sellable_quantity":None,"reference_cost":None,"buy_time":None,"historical_fees":None}
        projection["positions"].append(position)
    before=position["quantity"]
    position.update(quantity=format(Decimal(before)+Decimal(quantity),"f"),sellable_quantity=None,reference_cost=None)
    lots.append({"lot_id":payload["record_id"],"instrument":security,"original_quantity":quantity,"remaining_quantity":quantity,
                 "original_cost":amount,"remaining_cost":amount,"cost_basis":"KNOWN","effective_at":payload["effective_at"],"origin":"PAID_RIGHTS"})
    projection["cash_balance"]=money(cash)
    projection["broker_available"]=number(payload["broker_available_after"],"broker_available_after",nullable=True)
    projection["broker_available_as_of"]=payload["effective_at"] if projection["broker_available"] is not None else None
    projection["broker_available_basis"]="USER_CONFIRMED" if projection["broker_available"] is not None else "UNKNOWN_AFTER_RIGHTS_PAYMENT"
    projection["conservative_available"]=projection["broker_available"]
    projection["conservative_available_basis"]="USER_CONFIRMED" if projection["broker_available"] is not None else "当前券商快照未知"
    projection["broker_frozen_as_of"]=account.get("broker_frozen_as_of",account["effective_at"])
    projection["withdrawable_as_of"]=account.get("withdrawable_as_of",account["effective_at"])
    record={**payload,"kind":"RIGHTS_SUBSCRIPTION","record_id":text_value(payload["record_id"],"record_id"),"instrument":security,
            "quantity":quantity,"amount":amount,"fee_amount":fee,"basis":text_value(payload["basis"],"basis"),
            "quantity_before":before,"new_quantity":position["quantity"],"flow_category":"INVESTMENT_ACQUISITION",
            "gross_subscription_amount":None if fee is None else money(Decimal(amount)-Decimal(fee))}
    projection.setdefault("share_records",[]).append(record)
    refresh_balances(projection)
    update_fee_state(projection)
    record["cost_after"]=position["acquisition_cost"]
    return projection,[{"event_type":"SHARE_CHANGE","payload":record}]
