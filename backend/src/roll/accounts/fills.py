"""Actual fill projection and precise lot costs, used only by Ledger.prepare."""
import copy
import re
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP, localcontext

from fastapi import HTTPException


def money(value):
    return format(value.quantize(Decimal("0.01"),rounding=ROUND_HALF_UP),".2f")


def actual_fill(payload, account, number, text_value):
    fields={"effective_at","source","instrument","direction","quantity","price","record_id","fill_id","order_id","behavior_context","fee","broker_available_after"}
    if set(payload)!=fields:
        raise HTTPException(422,"成交字段缺失或存在未知字段")
    if account["version"]==0:
        raise HTTPException(409,"请先建立账户基线")
    instrument=text_value(payload["instrument"],"instrument")
    if not re.fullmatch(r"(?:SSE|SZSE|BSE):\d{6}",instrument):
        raise HTTPException(422,"证券必须为交易所:六位代码")
    quantity=number(payload["quantity"],"quantity",8)
    price=number(payload["price"],"price",8)
    if Decimal(quantity)<=0 or Decimal(price)<=0:
        raise HTTPException(422,"实际成交数量和价格必须大于零")
    if not isinstance(payload["direction"],str) or payload["direction"] not in {"BUY","SELL"}:
        raise HTTPException(422,"成交方向必须为BUY或SELL")
    fee=payload["fee"]
    if not isinstance(fee,dict) or set(fee)!={"status","amount","reserve_amount","basis"} or not isinstance(fee["status"],str) or fee["status"] not in {"KNOWN","PROVISIONAL"}:
        raise HTTPException(422,"需要已知或有依据暂估的成交费用")
    if fee["status"]=="KNOWN":
        amount=number(fee["amount"],"fee.amount")
        if fee["reserve_amount"] is not None:
            raise HTTPException(422,"已知费用不能包含暂估预留")
    else:
        amount=number(fee["reserve_amount"],"fee.reserve_amount")
        if fee["amount"] is not None or Decimal(amount)<=0:
            raise HTTPException(422,"未知费用需正数保守预留，不得当成已知零费用")
    basis=text_value(fee["basis"],"fee.basis")
    record_id=text_value(payload["record_id"],"record_id")
    fill_id=text_value(payload["fill_id"],"fill_id") if payload["fill_id"] is not None else None
    order_id=text_value(payload["order_id"],"order_id") if payload["order_id"] is not None else None
    behavior=payload["behavior_context"]
    if not isinstance(behavior,str) or behavior not in {"NO_RECOMMENDATION","CONTRARY","EXCESS_QUANTITY","OFFLINE","UNSPECIFIED"}:
        raise HTTPException(422,"成交行为标记无效")
    for prior in account.get("fills",[]):
        if prior["record_id"]==record_id or (fill_id is not None and prior["fill_id"]==fill_id):
            same=(prior["instrument"]==instrument and prior["direction"]==payload["direction"]
                  and Decimal(prior["quantity"])==Decimal(quantity) and Decimal(prior["price"])==Decimal(price)
                  and prior["fee"]["status"]==fee["status"] and Decimal(prior["charged_fee"])==Decimal(amount))
            if same:
                raise HTTPException(409,{"code":"FILL_ALREADY_RECORDED","record_id":prior["record_id"],"receipt_id":prior.get("receipt_id")})
            raise HTTPException(422,"成交标识已存在但内容不同，原输入隔离待核，不覆盖既有事实")
    with localcontext() as context:
        context.prec=80
        gross=money(Decimal(quantity)*Decimal(price))
        cost=money(Decimal(gross)+Decimal(amount))
        cash=money(Decimal(account["cash_balance"])-Decimal(cost) if payload["direction"]=="BUY"
                   else Decimal(account["cash_balance"])+Decimal(gross)-Decimal(amount))
    if Decimal(cash)<0:
        raise HTTPException(422,"成交导致负现金，需要核对漏记资金或成交")
    projection=copy.deepcopy(account)
    lots=projection.setdefault("lots",[])
    for existing in projection["positions"]:
        if not any(l["instrument"]==existing["instrument"] for l in lots):
            reference=existing["reference_cost"]
            baseline_cost=None if reference is None else money(Decimal(reference)*Decimal(existing["quantity"]))
            lots.append({"lot_id":"baseline:"+existing["instrument"],"instrument":existing["instrument"],
                         "original_quantity":existing["quantity"],"remaining_quantity":existing["quantity"],
                         "original_cost":baseline_cost,"remaining_cost":baseline_cost,"cost_basis":"UNKNOWN" if reference is None else "REFERENCE",
                         "effective_at":account["effective_at"]})
    projection["cash_balance"]=cash
    projection["cash_balance_basis"]="KNOWN_FEES"
    projection["broker_available"]=number(payload["broker_available_after"],"broker_available_after",nullable=True)
    projection["broker_available_as_of"]=payload["effective_at"] if projection["broker_available"] is not None else None
    projection["broker_available_basis"]="USER_CONFIRMED" if projection["broker_available"] is not None else "UNKNOWN_AFTER_FILL"
    projection["broker_frozen_as_of"]=account.get("broker_frozen_as_of",account["effective_at"])
    projection["withdrawable_as_of"]=account.get("withdrawable_as_of",account["effective_at"])
    previous=account.get("conservative_available",account["broker_available"])
    projection["conservative_available"]=None if previous is None else money(max(Decimal(0),Decimal(previous)-Decimal(cost))) if payload["direction"]=="BUY" else None
    if projection["broker_available"] is not None:
        projection["conservative_available"]=projection["broker_available"]
    projection["conservative_available_basis"]="USER_CONFIRMED" if projection["broker_available"] is not None else "从最近已确认可用资金估计，非当前券商快照"
    positions=projection["positions"]
    position=next((p for p in positions if p["instrument"]==instrument),None)
    if position is None and payload["direction"]=="BUY":
        position={"instrument":instrument,"quantity":"0","sellable_quantity":None,"reference_cost":None,
                  "buy_time":None,"historical_fees":None,"acquisition_cost":"0.00"}
        positions.append(position)
    with localcontext() as context:
        context.prec=80
        if payload["direction"]=="BUY":
            position["quantity"]=format(Decimal(position["quantity"])+Decimal(quantity),"f")
            known_cost=position.get("acquisition_cost")
            position["acquisition_cost"]=None if known_cost is None else money(Decimal(known_cost)+Decimal(cost))
            lots.append({"lot_id":record_id,"instrument":instrument,"original_quantity":quantity,
                         "remaining_quantity":quantity,"original_cost":cost,"remaining_cost":cost,
                         "cost_basis":fee["status"],"effective_at":payload["effective_at"]})
        else:
            if position is None or Decimal(position["quantity"])<Decimal(quantity):
                raise HTTPException(422,"实际卖出超过已记录持仓，需要核对漏记成交")
            remaining_to_sell=Decimal(quantity)
            released=Decimal(0)
            unknown_cost=False
            allocations=[]
            for lot in sorted(lots,key=lambda item:datetime.fromisoformat(item["effective_at"])):
                if lot["instrument"]!=instrument or Decimal(lot["remaining_quantity"])==0:
                    continue
                taken=min(remaining_to_sell,Decimal(lot["remaining_quantity"]))
                new_quantity=Decimal(lot["remaining_quantity"])-taken
                cumulative_sold=Decimal(lot["original_quantity"])-new_quantity
                if lot["original_cost"] is None:
                    new_cost=allocated=None
                else:
                    new_cost=Decimal(lot["original_cost"])-Decimal(money(Decimal(lot["original_cost"])*cumulative_sold/Decimal(lot["original_quantity"])))
                    allocated=Decimal(lot["remaining_cost"])-new_cost
                lot.update(remaining_quantity=format(new_quantity,"f"),remaining_cost=None if new_cost is None else money(new_cost))
                if allocated is not None:
                    released+=allocated
                unknown_cost=unknown_cost or lot["cost_basis"] in {"REFERENCE","UNKNOWN"}
                allocations.append({"lot_id":lot["lot_id"],"quantity":format(taken,"f"),"released_cost":None if allocated is None else money(allocated),"cost_basis":lot["cost_basis"]})
                remaining_to_sell-=taken
                if remaining_to_sell==0:
                    break
            if remaining_to_sell:
                raise HTTPException(422,"持仓批次资料不足，需要核对基线成本")
            position["quantity"]=format(Decimal(position["quantity"])-Decimal(quantity),"f")
            position["sellable_quantity"]=None
            position["acquisition_cost"]=None if position.get("acquisition_cost") is None else money(Decimal(position["acquisition_cost"])-released)
            projection["realized_gain"]=None if unknown_cost or projection.get("realized_gain","0.00") is None else money(Decimal(projection.get("realized_gain","0.00"))+Decimal(gross)-Decimal(amount)-released)
            if Decimal(position["quantity"])==0:
                positions.remove(position)
    fill_record={**payload,"instrument":instrument,"quantity":quantity,"price":price,"gross_amount":gross,
                 "fee":{"status":fee["status"],"amount":amount if fee["status"]=="KNOWN" else None,
                        "reserve_amount":None if fee["status"]=="KNOWN" else amount,"basis":basis},"charged_fee":amount,
                 "record_id":record_id,"fill_id":fill_id,"order_id":order_id,
                 "action_association":{"status":"UNKNOWN","decision_id":None}}
    if payload["direction"]=="SELL":
        fill_record["lot_allocations"]=allocations
        fill_record["released_cost"]=None if unknown_cost else money(released)
    projection.setdefault("fills",[]).append(fill_record)
    if fill_id is None:
        fill_record["identity_warning"]="缺少券商分笔成交标识，按本次手工记录保留；相似价量不自动合并，请核对是否为独立成交"
    reason={"CONTRARY":"用户标记与建议相反","EXCESS_QUANTITY":"用户标记超出建议数量","OFFLINE":"用户标记离线发生","NO_RECOMMENDATION":"没有对应建议","UNSPECIFIED":"建议关联未知"}[behavior]
    projection["latest_fill_facts"]=[f"{instrument} 实际{'新增' if payload['direction']=='BUY' else '减少'} {quantity} 股暴露（{reason}，截至 {payload['effective_at']}）"]
    update_fee_state(projection)
    return projection,[{"event_type":payload["direction"]+"_FILL","payload":fill_record}]


def update_fee_state(account):
    unresolved=[f["record_id"] for f in account.get("fills",[]) if f["fee"]["status"]=="PROVISIONAL"
                and f["record_id"] not in account.get("fee_resolutions",{})]
    account["fees_pending"]=unresolved
    account["cash_balance_basis"]="PROVISIONAL_FEES" if unresolved else "KNOWN_FEES"
    account["net_result_state"]="FEE_PENDING" if unresolved else "COST_UNKNOWN" if account.get("realized_gain","0.00") is None else "KNOWN_FEES"
    for position in account["positions"]:
        active=[l for l in account.get("lots",[]) if l["instrument"]==position["instrument"] and Decimal(l["remaining_quantity"])>0]
        position["acquisition_cost"]=None if any(l["cost_basis"] in {"REFERENCE","UNKNOWN"} for l in active) else money(sum((Decimal(l["remaining_cost"]) for l in active),Decimal(0)))
        position["cost_basis"]="PROVISIONAL" if any(l["instrument"]==position["instrument"] and l["cost_basis"]=="PROVISIONAL" for l in account.get("lots",[])) else "KNOWN" if position.get("acquisition_cost") is not None else "UNKNOWN"


def fee_adjustment(payload,account,number,text_value):
    if set(payload)!={"effective_at","source","target_record_id","actual_fee_amount","basis"}:
        raise HTTPException(422,"费用调整字段缺失或存在未知字段")
    target=text_value(payload["target_record_id"],"target_record_id")
    amount=number(payload["actual_fee_amount"],"actual_fee_amount")
    basis=text_value(payload["basis"],"basis")
    fill=next((f for f in account.get("fills",[]) if f["record_id"]==target),None)
    if fill is None:
        raise HTTPException(422,"费用调整找不到已确认成交")
    prior=account.get("fee_resolutions",{}).get(target,{}).get("actual_fee_amount",fill["charged_fee"])
    delta=Decimal(amount)-Decimal(prior)
    projection=copy.deepcopy(account)
    projection["cash_balance"]=money(Decimal(account["cash_balance"])-delta)
    if Decimal(projection["cash_balance"])<0:
        raise HTTPException(422,"费用调整导致负现金，需要核对账户")
    lot=next((l for l in projection.get("lots",[]) if l["lot_id"]==target),None)
    cost_delta=Decimal(0)
    if lot is not None:
        cost_delta,gain_delta=adjust_lot_fee(lot,projection["lots"],delta)
        position=next((p for p in projection["positions"] if p["instrument"]==fill["instrument"]),None)
        if position and position.get("acquisition_cost") is not None:
            position["acquisition_cost"]=money(Decimal(position["acquisition_cost"])+cost_delta)
        if projection.get("realized_gain") is not None:
            projection["realized_gain"]=money(Decimal(projection["realized_gain"])+gain_delta)
    elif projection.get("realized_gain") is not None:
        projection["realized_gain"]=money(Decimal(projection["realized_gain"])-delta)
    projection.setdefault("fee_resolutions",{})[target]={"actual_fee_amount":amount,"basis":basis,"effective_at":payload["effective_at"]}
    if projection.get("conservative_available") is not None:
        projection["conservative_available"]=money(max(Decimal(0),Decimal(projection["conservative_available"])-delta))
    projection["broker_available"]=None
    projection["broker_available_as_of"]=None
    projection["broker_available_basis"]="UNKNOWN_AFTER_FEE_ADJUSTMENT"
    update_fee_state(projection)
    event={**payload,"actual_fee_amount":amount,"previous_charged_fee":prior,"cash_delta":money(-delta),"remaining_cost_delta":money(cost_delta)}
    return projection,[{"event_type":"FEE_ADJUSTMENT","payload":event}]


def adjust_lot_fee(lot,lots,delta):
    """Carry a root buy-fee adjustment through actual share-change transfers."""
    old_remaining=Decimal(lot["remaining_cost"])
    old_transfer=Decimal(lot.get("transferred_cost","0.00"))
    old_released=Decimal(lot["original_cost"])-old_remaining-old_transfer
    original_cost=Decimal(lot["original_cost"])+delta
    sold=Decimal(lot["original_quantity"])-Decimal(lot["remaining_quantity"])-Decimal(lot.get("transferred_quantity","0"))
    released=Decimal(money(original_cost*sold/Decimal(lot["original_quantity"])))
    remaining=original_cost-released
    lot.update(original_cost=money(original_cost),cost_basis="KNOWN")
    gain_delta=old_released-released
    if "transfer_child_id" in lot:
        lot["transferred_cost"]=money(remaining)
        child=next(item for item in lots if item["lot_id"]==lot["transfer_child_id"])
        cost_delta,child_gain_delta=adjust_lot_fee(child,lots,remaining-old_transfer)
        return cost_delta,gain_delta+child_gain_delta
    lot["remaining_cost"]=money(remaining)
    return remaining-old_remaining,gain_delta
