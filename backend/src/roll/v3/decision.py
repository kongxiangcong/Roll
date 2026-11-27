"""Pure P0–P4 arbitration for all securities in one account."""
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
import json
from operator import eq, ge, gt, le, lt, ne

from roll.v3.account import AccountSnapshot, RiskBudget
from roll.v3.execution import (
    EXECUTION_RULES_VERSION,
    ExecutionIntent,
    ExecutionRules,
    affordable_quantity,
    estimate_fees,
    sellable_order_quantity,
    supports_security,
)
from roll.v3.market import utc_timestamp
from roll.v3.storage import instant, json_text, session_time


DECISION_RULES_VERSION = "after-close-p0-p4-v1"
ZERO = Decimal(0)
ONE = Decimal(1)
_COMPARISONS = {"<": lt, "<=": le, "==": eq, "!=": ne, ">=": ge, ">": gt}


def _number(value):
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return number if number.is_finite() else None


@dataclass(frozen=True)
class SecurityInput:
    close: Decimal | None = None
    trading_status: str = "unknown"
    industry: str | None = None
    industry_state: str = "unknown"
    stock_state: str = "unknown"
    signals: Mapping[str, dict] = field(default_factory=dict)
    upper_limit: Decimal | None = None
    lower_limit: Decimal | None = None
    features: Mapping[str, object] = field(default_factory=dict)
    feature_observations: Mapping[str, dict] = field(default_factory=dict)


@dataclass(frozen=True)
class DecisionData:
    as_of: str
    session: str
    snapshot_id: str
    securities: Mapping[str, SecurityInput]
    market_state: str = "unknown"


@dataclass(frozen=True)
class PlanReservation:
    symbol: str
    remaining: Decimal
    quantity: int = 0
    broker_offset: Decimal = ZERO
    side: str = "BUY"

    def __post_init__(self):
        object.__setattr__(self, "remaining", Decimal(str(self.remaining)))
        object.__setattr__(self, "broker_offset", Decimal(str(self.broker_offset)))
        if not ZERO <= self.broker_offset <= self.remaining or self.quantity < 0:
            raise ValueError("计划预留金额、已扣除冻结款与股数无效")


@dataclass(frozen=True)
class DecisionRules:
    simulated: bool = False
    strategy_versions: tuple[str, ...] = ()
    reservations: tuple[PlanReservation, ...] = ()
    execution: ExecutionRules = field(default_factory=ExecutionRules)
    allow_price_only: bool = False

    def __post_init__(self):
        if self.allow_price_only and not (self.simulated and self.strategy_versions):
            raise ValueError("仅显式指定策略版本的模拟裁决可使用量价口径")


@dataclass(frozen=True)
class TradingPlan:
    book_id: str
    symbol: str
    as_of: str
    session: str
    snapshot_id: str
    account_snapshot_id: str
    budget_id: str | None
    dossier_version: str | None
    strategy_version: str | None
    simulated: bool
    market_state: str
    industry: str | None
    industry_state: str
    stock_state: str
    research: dict
    account_constraints: dict
    reasons: dict
    candidates: tuple[dict, ...]
    action: str
    quantity: int
    current_quantity: int
    target_quantity: int
    target_fraction: Decimal | None
    sellable_quantity: int | None
    allowed_directions: tuple[str, ...]
    limit_price: Decimal | None
    cash_reserved: Decimal
    estimated_fees: Decimal
    execution_window: dict
    valid_until: str
    execution_conditions: tuple[str, ...]
    cancel_conditions: tuple[str, ...]
    exit_conditions: tuple[str, ...]
    if_unfilled: str
    intraday_actions: tuple[str, ...]
    execution_parameters: ExecutionRules
    confirmation_status: str = "PENDING"
    decision_rules_version: str = DECISION_RULES_VERSION
    execution_rules_version: str = EXECUTION_RULES_VERSION

    def as_dict(self):
        return json.loads(json_text(asdict(self)))

    def execution_intent(self, plan_id) -> ExecutionIntent | None:
        return execution_intent(self.as_dict(), plan_id)


def execution_intent(plan: Mapping, plan_id=None) -> ExecutionIntent | None:
    """Create the frozen next-open intent from either a plan or its persisted payload."""
    if plan["action"] not in ("BUY", "SELL") or plan["quantity"] <= 0:
        return None
    return ExecutionIntent(
        plan_id or plan["plan_id"], plan["symbol"], plan["action"], plan["quantity"],
        plan["as_of"], _number(plan["limit_price"]),
        _number(plan["cash_reserved"]) if plan["action"] == "BUY" else None,
    )


def _valuation(account, securities):
    holdings = defaultdict(int)
    for lot in account.lots:
        holdings[lot.symbol] += lot.quantity
    marked_shares = holdings.copy()
    cash_receivable = ZERO
    for receivable in account.receivables:
        marked_shares[receivable.symbol] += receivable.quantity
        cash_receivable += receivable.amount
    priced = {}
    unpriced = []
    for symbol, shares in sorted(marked_shares.items()):
        if not shares:
            continue
        close = _number(securities.get(symbol, SecurityInput()).close)
        if close is None or close <= ZERO:
            unpriced.append(symbol)
        else:
            priced[symbol] = close * shares
    nav = None if unpriced else account.cash + cash_receivable + sum(priced.values(), ZERO)
    return holdings, marked_shares, priced, nav, unpriced


def uncommitted_cash(account, budget, committed):
    """Cash available after the local reserve and commitments net of broker freezing."""
    if account.available_cash is None or budget is None:
        return None
    return max(ZERO, min(account.cash, account.available_cash) - budget.cash_reserve - committed)


@dataclass
class _Capacity:
    budget: RiskBudget | None
    nav: Decimal | None
    cash: Decimal
    committed: Decimal
    current: dict
    total: Decimal
    industry: dict
    unknown_industry: Decimal
    budget_reasons: list

    @classmethod
    def read(cls, data, account, budget, priced, nav, rules):
        current = defaultdict(Decimal, priced)
        sell_reserved = defaultdict(int)
        committed = ZERO
        for reservation in rules.reservations:
            if reservation.side == "SELL":
                sell_reserved[reservation.symbol] += reservation.quantity
                continue
            committed += reservation.remaining - reservation.broker_offset
            current[reservation.symbol] += reservation.remaining
        industry = defaultdict(Decimal)
        for symbol, value in current.items():
            industry[data.securities.get(symbol, SecurityInput()).industry] += value

        budget_reasons = []
        checks = [
            (account.available_cash is None, "AVAILABLE_CASH_UNKNOWN"),
            (nav is None or nav <= ZERO, "ACCOUNT_VALUE_UNKNOWN"),
            (budget is None, "RISK_BUDGET_MISSING"),
        ]
        if budget:
            if instant(budget.effective_at) > instant(data.as_of) or instant(budget.known_at) > instant(data.as_of):
                checks.append((True, "RISK_BUDGET_NOT_EFFECTIVE"))
            close = session_time(data.session, 15)
            for cutoff, reason in [(budget.expires_at, "RISK_BUDGET_EXPIRES"),
                                   (budget.funds_needed_at, "FUNDS_NEEDED")]:
                checks.append((cutoff is not None and instant(cutoff) <= close, reason))
        budget_reasons.extend(reason for condition, reason in checks if condition)
        cash = ZERO
        if not budget_reasons:
            cash = uncommitted_cash(account, budget, committed)
        return cls(budget, nav, cash, committed, current, sum(current.values(), ZERO),
                   industry, industry[None], budget_reasons), sell_reserved

    def limits(self, symbol, security):
        reasons = list(self.budget_reasons)
        if self.budget:
            for name in self.budget.pause_conditions:
                observed = security.features.get(name)
                if observed is not False:
                    status = "TRIGGERED" if observed is True else "UNKNOWN"
                    reasons.append(f"PAUSE_{status}:{name}")
        if reasons:
            return ZERO, ZERO, ZERO, reasons
        budget = self.budget
        symbol_limit = self.nav * budget.max_symbol_exposure
        total_headroom = self.nav * budget.max_total_exposure - self.total
        industry_headroom = self.nav * budget.max_industry_exposure
        if security.industry is not None:
            industry_headroom -= self.industry[security.industry] + self.unknown_industry
        elif budget.max_industry_exposure < ONE:
            industry_headroom = ZERO
            reasons.append("INDUSTRY_UNKNOWN")
        if total_headroom <= ZERO:
            reasons.append("TOTAL_EXPOSURE_LIMIT")
        if industry_headroom <= ZERO:
            reasons.append("INDUSTRY_EXPOSURE_LIMIT")
        if symbol_limit <= self.current[symbol]:
            reasons.append("SYMBOL_EXPOSURE_LIMIT")
        if self.cash <= ZERO:
            reasons.append("CASH_RESERVE_OR_COMMITMENTS")
        headroom = max(ZERO, min(total_headroom, industry_headroom, symbol_limit - self.current[symbol]))
        return symbol_limit, headroom, self.cash, reasons

    def reserve(self, symbol, industry, gross, gross_and_fees):
        self.current[symbol] += gross
        self.industry[industry] += gross
        if industry is None:
            self.unknown_industry += gross
        self.total += gross
        self.cash -= gross_and_fees


def _trigger_state(trigger, features):
    name = trigger.get("feature") or trigger.get("id")
    if not isinstance(name, str):
        return None
    actual = features.get(name)
    operation = trigger.get("operator")
    if operation is None:
        return actual if isinstance(actual, bool) else None
    if not isinstance(operation, str):
        return None
    comparator = _COMPARISONS.get(operation)
    expected = trigger.get("threshold")
    if comparator and actual is not None and expected is not None:
        observed_number, expected_number = _number(actual), _number(expected)
        if observed_number is not None and expected_number is not None:
            return comparator(observed_number, expected_number)
        if operation in {"==", "!="}:
            return comparator(actual, expected)
    return None


def _research(dossier, as_of, security):
    if dossier is None or dossier.get("review_status") != "published":
        return {"status": "missing"}, ["DOSSIER_MISSING"], False
    cutoff = instant(as_of)
    if any(dossier.get(key) and instant(dossier[key]) > cutoff for key in ("effective_at", "published_at", "as_of")):
        return {"status": "not_effective"}, ["DOSSIER_NOT_EFFECTIVE"], False
    result = {"version": dossier["version"], "valid_until": dossier.get("valid_until")}
    if dossier.get("valid_until") and instant(dossier["valid_until"]) <= cutoff:
        return {**result, "status": "expired"}, ["DOSSIER_EXPIRED"], False

    gate = dossier.get("fundamental_gate", "unknown")
    thesis = dossier.get("thesis_status", "unknown")
    reasons = []
    if gate != "pass":
        reasons.append(f"FUNDAMENTAL_{gate.upper()}")
    if thesis != "intact":
        reasons.append(f"THESIS_{thesis.upper()}")
    exit_required = thesis == "broken"
    triggers = []
    for trigger in dossier.get("invalidation_triggers", ()):
        status = _trigger_state(trigger, security.features)
        name = trigger.get("id", trigger.get("feature", "unnamed"))
        effect = trigger.get("effect")
        trace = {"id": name, "status": status, "effect": effect, "evidence_refs": trigger.get("evidence_refs", ())}
        feature = trigger.get("feature") or trigger.get("id")
        if isinstance(feature, str) and feature in security.feature_observations:
            trace["observation"] = security.feature_observations[feature]
        triggers.append(trace)
        if effect in ("block_new_risk", "pause", "pause_strategy", "risk_exit", "exit"):
            if status is None:
                reasons.append(f"TRIGGER_UNKNOWN:{name}")
            elif status:
                reasons.append(f"TRIGGER_FIRED:{name}")
                exit_required |= effect in ("risk_exit", "exit")
    result.update(status="active", fundamental_gate=gate, thesis_status=thesis, triggers=triggers,
                  constraint_basis=dossier.get("constraint_basis", {}), reviewer=dossier.get("reviewer"),
                  evidence_refs=dossier.get("evidence_refs", ()),
                  strategy_whitelist=dossier.get("strategy_whitelist", ()))
    return result, reasons, exit_required


def _strategy_options(entries, symbol, data, security, research, rules):
    paused = any(trigger["status"] is True and trigger["effect"] in ("pause", "pause_strategy")
                 for trigger in research.get("triggers", ()))
    options = []
    for entry in entries:
        strategy = entry["strategy"]
        version = strategy["version"]
        family = entry.get("protocol", {}).get("family")
        scope = entry.get("scope", strategy.get("scope", {}))
        registered = entry.get("production_eligible", False)
        simulated = (rules.simulated and version in rules.strategy_versions
                     and entry.get("simulation_eligible", False))
        exclusions = []
        if not (registered or simulated):
            exclusions.append("STRATEGY_NOT_ADMITTED")
        elif rules.strategy_versions and version not in rules.strategy_versions:
            exclusions.append("STRATEGY_NOT_REQUESTED")
        if entry.get("status") in ("suspended", "retired"):
            exclusions.append("STRATEGY_UNAVAILABLE")
        if paused:
            exclusions.append("STRATEGY_PAUSED_BY_RESEARCH")
        if symbol not in scope.get("symbols", ()):
            exclusions.append("SECURITY_OUT_OF_SCOPE")
        if not rules.allow_price_only and (research["status"] != "active" or not (
            {version, family} & set(research.get("strategy_whitelist", ()))
        )):
            exclusions.append("STRATEGY_NOT_WHITELISTED")
        for key, state in (("market_states", data.market_state), ("industry_states", security.industry_state),
                           ("stock_states", security.stock_state)):
            if key in scope and state not in scope[key]:
                exclusions.append(f"{key.upper()}_OUT_OF_SCOPE")
        signal = security.signals.get(version, {}) if registered or simulated else {}
        fraction = _number(signal.get("target_fraction"))
        if signal.get("status") != "ready" or fraction is None or not ZERO <= fraction <= ONE:
            fraction = None
        acceptance = entry.get("acceptance", {}).get("independent_run") or {}
        options.append({
            "strategy_version": version, "family": family, "registry_status": entry["status"],
            "priority": strategy.get("decision_priority", 100), "simulation_only": not registered,
            "risk": strategy.get("risk"), "exit_rule": strategy.get("exit"),
            "protocol_version": entry.get("protocol", {}).get("version"),
            "acceptance_run_id": acceptance.get("run_id"), "evidence_ref": acceptance.get("evidence_ref"),
            "publication": entry.get("publication"), "signal_status": signal.get("status", "missing"),
            "signal_missing": signal.get("missing", ()), "signal": signal.get("signal"), "target_fraction": fraction,
            "applicability_reasons": exclusions,
        })
    return sorted(options, key=lambda entry: (entry["priority"], entry["strategy_version"]))


def _directions(security, close, known_sellable, shares, account, symbol, session, rules):
    reasons = []
    if not supports_security(symbol, session):
        reasons.append("SECURITY_OUT_OF_EXECUTION_SCOPE")
    if security.trading_status == "suspended":
        reasons.append("SUSPENDED_AT_CUTOFF")
    elif security.trading_status != "trading":
        reasons.append("TRADING_STATUS_UNKNOWN")
    if close is None or close <= ZERO:
        reasons.append("CLOSE_UNAVAILABLE")
    if reasons:
        return (), reasons
    allowed = ["BUY"]
    legal_shares = sellable_order_quantity(symbol, session, known_sellable or 0, account.lots, rules.execution)
    if legal_shares:
        allowed.append("SELL")
        if legal_shares < shares:
            reasons.append("SELLABLE_QUANTITY_LIMITED")
    elif shares:
        reasons.append("SELLABLE_QUANTITY_UNKNOWN" if known_sellable is None else "NO_LEGAL_SELLABLE_QUANTITY")
    upper, lower = _number(security.upper_limit), _number(security.lower_limit)
    if upper is not None and close >= upper:
        reasons.append("UPPER_LIMIT_AT_CUTOFF")
    if lower is not None and close <= lower:
        reasons.append("LOWER_LIMIT_AT_CUTOFF")
    # Exchange bands and order queues are checked against the target session's opening quote.
    reasons.append("CONFIRM_OPENING_STATUS_AND_PRICE_BANDS")
    return tuple(allowed), reasons


def _order(symbol, data, account, rules, security, current, marked, sellable, directions, fraction,
           symbol_limit, headroom, cash, p2):
    close = _number(security.close)
    if fraction == ZERO and current:
        if "SELL" not in directions:
            return "WATCH", 0, 0, ZERO, ["SELL_BLOCKED_P0"]
        quantity = sellable_order_quantity(symbol, data.session, sellable, account.lots, rules.execution)
        fee = estimate_fees(symbol, data.session, "SELL", close, quantity, rules.execution)
        return "SELL", quantity, 0, fee, ["FLAT_TARGET"]
    if fraction == ZERO:
        return "HOLD", 0, current, ZERO, ["FLAT_TARGET"]
    if "BUY" not in directions:
        return "WATCH", 0, current, ZERO, ["BUY_BLOCKED_P0"]
    if not symbol_limit or not headroom or not cash:
        return "WATCH", 0, current, ZERO, ["BUY_BLOCKED_P1"]
    if p2:
        return "WATCH", 0, current, ZERO, ["BUY_BLOCKED_P2"]
    target = int(symbol_limit * fraction / close)
    if target <= marked:
        return "HOLD", 0, current, ZERO, ["TARGET_ALREADY_MET"]
    # The open may be dearer than the close. The reservation also caps the actual
    # opening notional so a price change cannot put the account above its P1 limits.
    max_gross = min(headroom, close * (target - marked))
    quantity = affordable_quantity(symbol, data.session, close, int(max_gross / close),
                                   min(cash, headroom), rules.execution)
    if not quantity:
        return "WATCH", 0, current, ZERO, ["SHARED_CASH_OR_RISK_BELOW_MINIMUM_ORDER"]
    fee = estimate_fees(symbol, data.session, "BUY", close, quantity, rules.execution)
    return "BUY", quantity, current + quantity, fee, ["BUY_WITHIN_SHARED_LIMITS"]


def decide(data: DecisionData, account: AccountSnapshot, budget: RiskBudget | None,
           dossier: Mapping[str, dict | None], registry: Mapping[str, Sequence[dict]],
           rules: DecisionRules = DecisionRules()) -> tuple[TradingPlan, ...]:
    """Arbitrate one account's frozen inputs without storage, network, or wall-clock access."""
    if instant(account.effective_at) > instant(data.as_of) or instant(account.known_at) > instant(data.as_of):
        raise ValueError("账户快照晚于裁决截止时点")
    cutoff = utc_timestamp(data.as_of)
    session = date.fromisoformat(str(data.session)).isoformat()
    if date.fromisoformat(session) <= instant(cutoff).date():
        raise ValueError("计划时段须晚于裁决交易日")
    holdings, marked_shares, priced, nav, unpriced = _valuation(account, data.securities)
    capacity, sell_reserved = _Capacity.read(data, account, budget, priced, nav, rules)
    candidates = {}
    for symbol, security in data.securities.items():
        research, thesis_reasons, thesis_exit = _research(dossier.get(symbol), cutoff, security)
        options = _strategy_options(registry.get(symbol, ()), symbol, data, security, research, rules)
        priorities = [option["priority"] for option in options
                      if not option["applicability_reasons"] and option["target_fraction"] is not None]
        candidates[symbol] = (min(priorities, default=float("inf")), research, thesis_reasons, thesis_exit, options)

    plans = []
    for symbol in sorted(candidates, key=lambda symbol: (candidates[symbol][0], symbol)):
        _, research, p2, thesis_exit, options = candidates[symbol]
        security = data.securities[symbol]
        close = _number(security.close)
        current = holdings[symbol]
        sellable = account.known_sellable(symbol, session)
        if sellable is not None:
            sellable = max(0, sellable - sell_reserved[symbol])
        directions, p0 = _directions(security, close, sellable, current, account, symbol, session, rules)
        symbol_limit, headroom, cash, p1 = capacity.limits(symbol, security)
        buy_restrictions = p2
        if rules.allow_price_only:
            buy_restrictions = [reason for reason in p2 if reason in {"FUNDAMENTAL_FAIL", "THESIS_BROKEN"}
                                or reason.startswith("TRIGGER_FIRED:")]
            p2 = [*p2, "PRICE_ONLY_SIMULATION"]
        account_constraints = {
            "cash": account.cash, "broker_available_cash": account.available_cash,
            "cash_reserve": budget.cash_reserve if budget else None,
            "existing_reservations_net_of_broker": capacity.committed, "cash_available_to_allocate": cash,
            "account_value": nav, "unpriced_holdings": unpriced, "existing_position_value": priced.get(symbol),
            "total_reserved_and_position_value": capacity.total,
            "symbol_value_limit": symbol_limit if budget else None, "value_available_to_allocate": headroom,
            "max_total_exposure": budget.max_total_exposure if budget else None,
            "max_symbol_exposure": budget.max_symbol_exposure if budget else None,
            "max_industry_exposure": budget.max_industry_exposure if budget else None,
            "funds_needed_at": budget.funds_needed_at if budget else None,
            "budget_expires_at": budget.expires_at if budget else None,
        }
        action, quantity, target, fee, allocation_reason = "WATCH", 0, current, ZERO, "NO_FEASIBLE_STRATEGY"
        chosen = None
        target_fraction = None
        risk_target = 0 if thesis_exit and current else None

        if risk_target is not None:
            target = risk_target
            maximum = min(current - risk_target, sellable or 0)
            if "SELL" in directions:
                quantity = sellable_order_quantity(symbol, session, maximum, account.lots, rules.execution)
            if quantity:
                action = "SELL"
                fee = estimate_fees(symbol, session, "SELL", close, quantity, rules.execution)
                allocation_reason = "RISK_EXIT" if current - quantity <= risk_target else "PARTIAL_RISK_EXIT"
            else:
                action, allocation_reason = "RISK_EXIT_PENDING", "RISK_EXIT_BLOCKED_P0"

        p3 = []
        for option in options:
            version = option["strategy_version"]
            exclusions = option["applicability_reasons"]
            p3.extend(f"{version}:{reason}" for reason in exclusions)
            option["selection_reasons"] = list(exclusions)
            option["selected"] = False
            if option["target_fraction"] is None:
                option["selection_reasons"].append("NO_READY_SIGNAL")
            if exclusions or option["target_fraction"] is None:
                continue
            if risk_target is not None:
                option["selection_reasons"].append("PRESET_RISK_EXIT_TAKES_PRIORITY")
            elif chosen is not None:
                option["selection_reasons"].append("LOWER_REGISTERED_PRIORITY")
            else:
                alternative = _order(symbol, data, account, rules, security, current, marked_shares[symbol],
                                     sellable, directions, option["target_fraction"], symbol_limit,
                                     headroom, cash, buy_restrictions)
                option_action, order_size, option_target, order_fee, why = alternative
                option["selection_reasons"].extend(why)
                if option_action == "WATCH":
                    continue
                action, quantity, target, fee = option_action, order_size, option_target, order_fee
                if action == "HOLD":
                    target = current
                chosen, target_fraction = version, option["target_fraction"]
                option["selected"] = True
                allocation_reason = why[0]
        if chosen is None and risk_target is None and options:
            exclusions = [reason for option in options for reason in option["selection_reasons"]]
            allocation_reason = next((reason for reason in exclusions if reason.startswith("BUY_BLOCKED")
                                      or reason == "SHARED_CASH_OR_RISK_BELOW_MINIMUM_ORDER"), allocation_reason)

        reserved = ZERO
        if action == "BUY":
            gross = close * quantity
            reserved = gross + fee
            capacity.reserve(symbol, security.industry, gross, reserved)
            target = current + quantity

        opening = utc_timestamp(session_time(session, 9, 30))
        plans.append(TradingPlan(
            book_id=account.book_id, symbol=symbol, as_of=cutoff, session=session, snapshot_id=data.snapshot_id,
            account_snapshot_id=account.snapshot_id, budget_id=budget.budget_id if budget else None,
            dossier_version=research.get("version"), strategy_version=chosen, simulated=rules.simulated,
            market_state=data.market_state, industry=security.industry, industry_state=security.industry_state,
            stock_state=security.stock_state, research=research, account_constraints=account_constraints,
            reasons={"P0": p0, "P1": p1 or ["RISK_BUDGET_WITHIN_LIMITS"], "P2": p2 or ["RESEARCH_CONSTRAINTS_PASS"],
                     "P3": p3 or (["STRATEGY_ELIGIBLE"] if options else ["NO_REGISTERED_STRATEGY"]),
                     "P4": [allocation_reason]}, candidates=tuple(options), action=action, quantity=quantity,
            current_quantity=current, target_quantity=target, target_fraction=target_fraction,
            sellable_quantity=sellable, allowed_directions=directions, limit_price=None, cash_reserved=reserved,
            estimated_fees=fee, execution_window={"start": opening, "end": opening},
            valid_until=utc_timestamp(session_time(session, 15)),
            execution_conditions=("TARGET_SESSION_OPEN", "CONFIRM_TRADING_STATUS_PRICE_BANDS_AND_SELLABLE_SHARES",
                                  "LIMIT_TO_ORDER_SHARES_AND_RESERVED_CASH"),
            cancel_conditions=("SUPERSEDED", "SESSION_EXPIRED", "PRESET_RISK_PAUSE"),
            exit_conditions=("PUBLISHED_INVALIDATION", "ACCOUNT_RISK_LIMIT", "FROZEN_STRATEGY_EXIT_SIGNAL"),
            if_unfilled="RECORD_REASON_AND_WAIT_FOR_NEXT_AFTER_CLOSE_DECISION",
            intraday_actions=("CHECK_PRESET_CONDITIONS", "PAUSE_OR_CANCEL", "APPLY_PRESET_RISK_EXIT_IF_EXECUTABLE"),
            execution_parameters=rules.execution,
        ))
    return tuple(plans)
