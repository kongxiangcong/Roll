#!/usr/bin/env python3
"""Auditable FCFF scenario valuation; standard library only.

DCF/EPV adapted from equity-research-skill scripts/dcf.py (Sirius, MIT).
See THIRD_PARTY_NOTICES.md. Outputs are conditional research values.
"""
import argparse
import hashlib
import json
import math
import sys
from pathlib import Path


def number(value, name, minimum=None, strict=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name}: expected finite number")
    if minimum is not None and (value <= minimum if strict else value < minimum):
        raise ValueError(f"{name}: must be {'>' if strict else '>='} {minimum}")
    return value


def required(data, key):
    if key not in data:
        raise ValueError(f"missing field: {key}")
    return data[key]


def vector(values, name):
    if not isinstance(values, list) or not values:
        raise ValueError(f"{name}: expected nonempty array")
    return [number(x, name) for x in values]


def rates(wacc, g):
    number(wacc, "wacc", 0, True)
    number(g, "terminal_g", -1, True)
    if wacc <= g:
        raise ValueError("wacc must exceed terminal_g")


def fcff_from_cfo(cfo, capex, interest_paid, tax_rate, interest_classification):
    """Mechanical interest adjustment only; does not normalize finance subsidiaries/NWC.

    Financing-classified interest is absent from CFO but its tax shield remains.
    Assumes the stated interest tax deduction was usable in the same period.
    """
    number(cfo, "cfo")
    number(capex, "capex", 0)
    number(interest_paid, "interest_paid", 0)
    number(tax_rate, "tax_rate", 0)
    if tax_rate > 1:
        raise ValueError("tax_rate must be <= 1")
    if interest_classification == "operating":
        adjustment = interest_paid * (1 - tax_rate)
    elif interest_classification == "financing":
        adjustment = -interest_paid * tax_rate
    else:
        raise ValueError("interest_classification must be operating or financing; split mixed flows first")
    return cfo - capex + adjustment


def equity_adjustment(cfg):
    """Positive adjustments deduct from EV; negative adjustments add to equity."""
    if ("net_debt" in cfg) == ("equity_bridge" in cfg):
        raise ValueError("provide exactly one of net_debt or equity_bridge")
    if "net_debt" in cfg:
        return number(cfg["net_debt"], "net_debt"), None
    rows = cfg["equity_bridge"]
    if not isinstance(rows, list) or not rows:
        raise ValueError("equity_bridge must be a nonempty list")
    names = set()
    for row in rows:
        if set(row) != {"name", "amount", "source", "treatment"}:
            raise ValueError("bridge rows require name, amount, source, treatment")
        if not all(isinstance(row[k], str) and row[k].strip() for k in ("name", "source", "treatment")):
            raise ValueError("bridge name/source/treatment must be nonempty text")
        if row["name"] in names:
            raise ValueError("duplicate equity_bridge name")
        names.add(row["name"])
        number(row["amount"], "equity_bridge.amount")
    return sum(row["amount"] for row in rows), rows


def cashflows(sc):
    if "fcf" in sc:
        if "revenue" in sc or "fcf_margin" in sc:
            raise ValueError("provide fcf OR revenue + fcf_margin")
        return vector(sc["fcf"], "fcf")
    revenue = vector(required(sc, "revenue"), "revenue")
    margins = vector(required(sc, "fcf_margin"), "fcf_margin")
    if len(revenue) != len(margins) or any(r < 0 for r in revenue):
        raise ValueError("revenue/margin lengths must match; revenue must be nonnegative")
    return [r * m for r, m in zip(revenue, margins)]


def dcf(fcfs, wacc, g, shares, net_debt):
    rates(wacc, g)
    # End-of-year cash flows. The final explicit year is a normalized base.
    if fcfs[-1] <= 0:
        raise ValueError("terminal base FCFF must be positive; extend forecast or use another model")
    pv = sum(f / (1 + wacc) ** t for t, f in enumerate(fcfs, 1))
    terminal_fcf = fcfs[-1] * (1 + g)
    terminal_value = terminal_fcf / (wacc - g)
    pv_terminal = terminal_value / (1 + wacc) ** len(fcfs)
    ev = pv + pv_terminal
    return {"enterprise_value": ev, "equity_value": ev - net_debt,
            "per_share": (ev - net_debt) / shares, "pv_explicit": pv,
            "terminal_fcf_next_year": terminal_fcf, "pv_terminal": pv_terminal,
            "terminal_share_of_ev": pv_terminal / ev if ev > 0 else None}


def reverse(price, shares, net_debt, wacc, g, fcfs, margins, base_revenue, market_equity_value=None):
    """Keep years 1..N fixed; solve required year N+1 terminal cash flow."""
    ev = (market_equity_value if market_equity_value is not None else price * shares) + net_debt
    pv = sum(f / (1 + wacc) ** t for t, f in enumerate(fcfs, 1))
    required_fcf = (ev - pv) * (1 + wacc) ** len(fcfs) * (wacc - g)
    result = {"market_enterprise_value": ev, "terminal_year": len(fcfs) + 1,
              "terminal_fcf_required": required_fcf, "rows": []}
    if required_fcf <= 0:
        result["status"] = "no_positive_terminal_requirement"
        return result
    result["status"] = "conditional_terminal_requirement"
    for margin in margins:
        number(margin, "steady_margin", 0, True)
        revenue = required_fcf / margin
        result["rows"].append({"steady_margin": margin, "terminal_revenue_required": revenue,
                               "revenue_cagr_to_terminal_year":
                               (revenue / base_revenue) ** (1 / (len(fcfs) + 1)) - 1})
    return result


def run(cfg):
    if not isinstance(cfg, dict):
        raise ValueError("config must be an object")
    allowed = {"metadata", "cash_flow_basis", "shares", "net_debt", "wacc", "terminal_g",
               "scenarios", "sensitivity", "reverse", "epv", "equity_bridge", "review"}
    unknown = set(cfg) - allowed
    if unknown:
        raise ValueError(f"unsupported fields: {sorted(unknown)}")
    if required(cfg, "cash_flow_basis") != "FCFF":
        raise ValueError("only FCFF + WACC supported; FCFE requires cost of equity")
    meta = required(cfg, "metadata")
    for key in ("company", "as_of", "currency", "amount_unit", "shares_unit", "sources", "assumptions"):
        if not meta.get(key):
            raise ValueError(f"metadata.{key} is required")
    if (meta["amount_unit"], meta["shares_unit"]) not in {
        ("unit", "share"), ("million", "million_shares"), ("100_million", "100_million_shares")
    }:
        raise ValueError("amount/share scales must match: unit/share, million/million_shares, 100_million/100_million_shares")
    shares = number(required(cfg, "shares"), "shares", 0, True)
    debt, bridge = equity_adjustment(cfg)
    wacc = required(cfg, "wacc")
    g = required(cfg, "terminal_g")
    rates(wacc, g)
    scenarios = required(cfg, "scenarios")
    if not isinstance(scenarios, list) or not scenarios:
        raise ValueError("scenarios must be nonempty")
    rows, paths, probabilities = [], {}, []
    weighted = all("probability" in sc for sc in scenarios)
    if not weighted and any("probability" in sc for sc in scenarios):
        raise ValueError("provide research weights for all scenarios or none")
    for sc in scenarios:
        extra = set(sc) - {"name", "probability", "fcf", "revenue", "fcf_margin"}
        if extra:
            raise ValueError(f"unsupported scenario fields: {sorted(extra)}; specify full annual paths")
        name = required(sc, "name")
        if not isinstance(name, str) or not name or name in paths:
            raise ValueError("scenario names must be nonempty and unique")
        p = number(sc["probability"], "probability", 0) if weighted else None
        if weighted:
            probabilities.append(p)
        paths[name] = cashflows(sc)
        rows.append({"name": name, **({"probability": p} if weighted else {}), "fcff": paths[name],
                     **dcf(paths[name], wacc, g, shares, debt)})
    if weighted and not math.isclose(sum(probabilities), 1, abs_tol=1e-9, rel_tol=0):
        raise ValueError("scenario probabilities must sum to 1")
    if len({len(p) for p in paths.values()}) != 1:
        raise ValueError("scenario horizons must match for comparison")
    review = cfg.get("review", {"status": "unreviewed", "limitations": ["Economic suitability has not been reviewed"]})
    if set(review) != {"status", "limitations"} or review["status"] not in {"unreviewed", "conditional", "blocked", "reviewed"}:
        raise ValueError("review requires status (unreviewed/conditional/blocked/reviewed) and limitations")
    if not isinstance(review["limitations"], list) or any(not isinstance(x, str) or not x.strip() for x in review["limitations"]):
        raise ValueError("review.limitations must be a list of nonempty strings")
    if review["status"] != "reviewed" and not review["limitations"]:
        raise ValueError("unreviewed/conditional/blocked models must state limitations")
    result = {"schema_version": 2, "metadata": meta, "cash_flow_basis": "FCFF",
              "review": review, "equity_adjustment": debt, "equity_bridge": bridge,
              "discount_timing": "year_end", "scenarios": rows,
              "scenario_range": [min(r["per_share"] for r in rows), max(r["per_share"] for r in rows)],
              "warnings": ["Conditional scenario range, not a statistical confidence interval.",
                           "Sources and economic assumptions require human verification."]}
    if weighted:
        result["weighted_per_share"] = sum(r["probability"] * r["per_share"] for r in rows)
    for row in rows:
        if row["terminal_share_of_ev"] is None or row["terminal_share_of_ev"] > 0.75:
            result["warnings"].append(f"{row['name']}: EV is nonpositive or terminal contribution exceeds 75%; review terminal assumptions")
        if row["equity_value"] < 0:
            result["warnings"].append(f"{row['name']}: negative residual equity; distress/option value not modeled")
    if "sensitivity" in cfg:
        s = cfg["sensitivity"]
        path = paths[required(s, "scenario")]
        result["sensitivity"] = []
        for w in vector(required(s, "wacc"), "sensitivity.wacc"):
            for growth in vector(required(s, "terminal_g"), "sensitivity.terminal_g"):
                rates(w, growth)
                result["sensitivity"].append({"wacc": w, "terminal_g": growth,
                    "per_share": dcf(path, w, growth, shares, debt)["per_share"]})
    if "reverse" in cfg:
        r = cfg["reverse"]
        if set(r) - {"scenario", "price", "market_equity_value", "steady_margins", "base_revenue"}:
            raise ValueError("unsupported reverse fields")
        if ("price" in r) == ("market_equity_value" in r):
            raise ValueError("reverse requires exactly one of price or market_equity_value")
        if ("steady_margins" in r) != ("base_revenue" in r):
            raise ValueError("reverse revenue conversion needs both steady_margins and base_revenue")
        if meta.get("listing_structure") == "A+H" and "price" in r:
            raise ValueError("A+H reverse requires combined market_equity_value in model currency")
        margins = vector(r["steady_margins"], "steady_margins") if "steady_margins" in r else []
        for m in margins:
            number(m, "steady_margin", 0, True)
        result["reverse"] = reverse(
            number(r.get("price", 1), "price", 0, True), shares, debt, wacc, g,
            paths[required(r, "scenario")], margins,
            number(r.get("base_revenue", 1), "base_revenue", 0, True),
            number(r["market_equity_value"], "market_equity_value", 0, True) if "market_equity_value" in r else None)
    if "epv" in cfg:
        e = cfg["epv"]
        if set(e) != {"normalized_fcff"}:
            raise ValueError("epv requires only normalized_fcff after maintenance reinvestment")
        fcf = number(e["normalized_fcff"], "normalized_fcff", 0, True)
        ev = fcf / wacc
        result["epv"] = {"enterprise_value": ev, "equity_value": ev - debt,
                         "per_share": (ev - debt) / shares, "growth": 0,
                         "wacc": wacc}
    # Also catch overflow/nonfinite derived values before writing an artifact.
    json.dumps(result, allow_nan=False)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--require-reviewed", action="store_true", help="exit 3 unless explicit economic review status is reviewed; still save diagnostic output")
    args = parser.parse_args()
    try:
        raw = args.config.read_bytes()
        result = run(json.loads(raw.decode("utf-8-sig")))
        result["input_sha256"] = hashlib.sha256(raw).hexdigest()
        result["calculator_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        rendered = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)
        if args.output:
            if args.output.resolve() == args.config.resolve():
                raise ValueError("output must not overwrite config")
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(rendered + "\n", encoding="utf-8")
        else:
            print(rendered)
        if args.require_reviewed and result["review"]["status"] != "reviewed":
            print("[valuation review] computation completed, economic review not passed", file=sys.stderr)
            return 3
    except (ValueError, KeyError, TypeError, AttributeError, OSError, OverflowError, ZeroDivisionError) as exc:
        print(f"[valuation error] {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
