"""Project plan commitments from append-only condition, order, and fill facts."""
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
import json

from roll.v3.account import fill_gross
from roll.v3.decision import PlanReservation, ZERO


SCHEMA = """
CREATE TABLE IF NOT EXISTS commitment_event (
    seq INTEGER PRIMARY KEY,
    book_id TEXT NOT NULL,
    plan_id TEXT NOT NULL REFERENCES plan_revision(plan_id),
    event_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    reference_id TEXT NOT NULL,
    status TEXT NOT NULL,
    effective_at TEXT NOT NULL,
    known_at TEXT NOT NULL,
    payload TEXT NOT NULL,
    UNIQUE (book_id, event_id)
);
CREATE INDEX IF NOT EXISTS commitment_event_order ON commitment_event(book_id, kind, reference_id);
"""


def money(value):
    return None if value is None else format(value.normalize(), "f")


@dataclass(frozen=True)
class _Allowance:
    amount: Decimal = ZERO
    quantity: int = 0

    def remaining(self, filled):
        quantity = max(0, self.quantity - filled.quantity)
        return _Allowance(max(ZERO, self.amount - filled.amount) if quantity else ZERO, quantity)


def _filled(fills, side):
    amount = ZERO
    quantity = 0
    for event in fills:
        payload = event["payload"]
        quantity += payload["quantity"]
        if side == "BUY":
            amount += fill_gross(payload["quantity"], payload["price"]) + Decimal(payload["fee"])
    return _Allowance(amount, quantity)


def _order_fills(orders, fills):
    attributed = defaultdict(list)
    for fill in fills:
        order_id = fill["payload"].get("broker_order_id")
        if order_id is None:
            # Old or manually entered fills need only a plan link when the broker order is unambiguous.
            pending = []
            for reference, events in orders.items():
                state = next((event for event in reversed(events) if event["effective_at"] <= fill["effective_at"]), None)
                if state is not None and state["status"] == "pending":
                    pending.append(reference)
            if len(pending) == 1:
                order_id, = pending
        if order_id in orders:
            attributed[order_id].append(fill)
    return attributed


def _order_balances(orders, fills, cap, side):
    attributed = _order_fills(orders, fills)
    for order_id, events in orders.items():
        status = events[-1]["status"]
        order_amount, quantity = cap.amount, cap.quantity
        frozen, frozen_at = ZERO, None
        for event in events:
            payload = event["payload"]
            order_amount = Decimal(payload["max_amount"]) if payload.get("max_amount") is not None else order_amount
            if payload.get("order_quantity") is not None:
                quantity = payload["order_quantity"]
            if payload.get("broker_frozen") is not None:
                frozen, frozen_at = Decimal(payload["broker_frozen"]), event["effective_at"]
        order_fills = attributed[order_id]
        confirmed = _filled(order_fills, side)
        remaining = _Allowance(order_amount, quantity).remaining(confirmed) if status == "pending" else _Allowance()
        spent = _filled((fill for fill in order_fills if frozen_at and fill["effective_at"] > frozen_at), side).amount
        offset = min(remaining.amount, max(ZERO, frozen - spent))
        yield _fact_details(events[-1]) | {
            "order_id": order_id, "max_amount": money(order_amount), "order_quantity": quantity,
            "confirmed_fill_amount": money(confirmed.amount), "confirmed_fill_quantity": confirmed.quantity,
            "remaining_amount": money(remaining.amount), "remaining_quantity": remaining.quantity,
            "broker_frozen_offset": money(offset),
        }, remaining, offset


def _fact_details(event):
    return {key: event[key] for key in ("event_id", "status", "effective_at", "known_at")}


def project_reservation(plan, events, fills, *, as_of, replacing_session, replacing_symbols):
    side = plan["side"]
    cap = _Allowance(Decimal(plan["max_amount"]), plan["order_quantity"])
    matching = [fill for fill in fills if fill["payload"]["side"] == side
                and fill["payload"]["symbol"] == plan["symbol"]]
    confirmed = _filled(matching, side)
    residual = cap.remaining(confirmed)
    replacing = plan["session"] == replacing_session and (
        replacing_symbols is None or plan["symbol"] in replacing_symbols
    )
    ordinary = residual if plan["latest"] == 1 and not replacing and plan["expires_at"] > as_of else _Allowance()
    condition = None
    orders = defaultdict(list)
    for event in events:
        event = dict(event) | {"payload": json.loads(event["payload"])}
        if event["kind"] == "condition":
            condition = event
        else:
            orders[event["reference_id"]].append(event)
    conditional = _Allowance()
    if condition is not None:
        condition = _fact_details(condition) | condition["payload"]
        if condition["status"] == "active" and condition["expires_at"] > as_of:
            conditional = residual

    order_details = []
    order_amount, order_quantity, offset = ZERO, 0, ZERO
    for details, remaining, frozen in _order_balances(orders, matching, cap, side):
        order_details.append(details)
        order_amount += remaining.amount
        order_quantity += remaining.quantity
        offset += frozen
    # A pending order can execute against the same allowance as the plan or condition.
    amount = max(ordinary.amount, conditional.amount, order_amount)
    quantity = max(ordinary.quantity, conditional.quantity, order_quantity)
    reservation = PlanReservation(plan["symbol"], amount, quantity, offset, side)
    details = {
        "plan_id": plan["plan_id"], "symbol": plan["symbol"], "session": plan["session"], "side": side,
        "expires_at": plan["expires_at"], "max_amount": money(cap.amount), "order_quantity": cap.quantity,
        "confirmed_fill_amount": money(confirmed.amount), "confirmed_fill_quantity": confirmed.quantity,
        "remaining_amount": money(amount), "remaining_quantity": quantity, "broker_frozen_offset": money(offset),
        "condition": condition, "orders": order_details,
    }
    return details, reservation
