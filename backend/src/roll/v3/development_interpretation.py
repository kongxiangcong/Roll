"""Frozen public evidence and the development report contract."""

import re
from decimal import Decimal
from hashlib import sha256

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat

from roll.v3.storage import json_text


INSTRUCTIONS = """只用本次冻结的江西铜业 E0/E1 开发实验输入回答 question，按 JSON Schema 提交一份中文解读。
每项 claims 说明一项结果及其意义，并在 metrics 中填入 public.metrics 的确切键与原始 JSON 值。
也可用 evidence 的确切键加 #字段名定位数字，如 trade:e0:交易日#quantity 或 segment:始日:末日#net_difference。
可引用的字段见 evidence_metric_fields。收益与回撤数值是比率，null 表示无依据。
用 evidence_refs 引用 evidence 的确切键，结合模拟成交、信号或区段说明差异；有对应依据时至少引用一项。
区分市场条件直接拦截与后续现金持仓分化，说明费用、最大回撤和相对两个基准的表现是否支持判断。
在 uncertainties 说明样本、重建口径或差异集中等限制，在 gaps 说明缺少的证据及其影响。
coverage 有路径或输入范围缺口时须记录在 gaps。gaps 的 evidence_refs 只填关联的已知证据，确实无可用引用时填空列表。
公开证据列出部分可定位记录，evidence_coverage 给出完整记录数与本次提供数。避免用摘录推算整体结果。
记录内的关联键用于在完整回执中定位，只有 evidence 的顶层键是本次可引述的证据。
说明中的实验数值只通过 metrics 引述；日期可通过 evidence_refs 定位。
没有足够依据时可提交有引用的描述性结论，或将 claims 留空并说明 gaps。
新条件只写入 follow_up。开发期模拟不能据此推广到其他窗口、标的或实盘。"""

EVIDENCE_METRIC_FIELDS = {
    "trade": ("quantity", "intended_quantity", "price", "fee", "gross", "slippage_cost"),
    "segment": ("net_difference", "return_contribution", "cost_difference", "slippage_difference"),
    "drawdown": ("magnitude", "peak_nav", "trough_nav"),
}

METRICS = (
    "start_nav", "end_nav", "total_return", "max_drawdown", "fills", "costs", "slippage_cost",
    "excess_return_vs_buy_and_hold", "excess_return_vs_no_active_trading", "path_complete", "valued_sessions",
    "partial_fills", "failed_fills", "completed_round_trips",
)


class ReportField(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class MetricCitation(ReportField):
    ref: str
    value: str | int | FiniteFloat | bool | None


class Claim(ReportField):
    interpretation: str = Field(min_length=1)
    metrics: list[MetricCitation] = Field(min_length=1)
    evidence_refs: list[str]


class EvidenceGap(ReportField):
    reason: str = Field(min_length=1)
    required_evidence: str = Field(min_length=1)
    evidence_refs: list[str]


class DevelopmentReply(ReportField):
    claims: list[Claim]
    uncertainties: list[str] = Field(min_length=1)
    gaps: list[EvidenceGap]
    follow_up: list[str]


def is_development(manifest):
    return manifest.get("kind") == "development_experiment"


def _select(source, *keys):
    return {key: source[key] for key in keys if key in source}


def _endpoints(rows, limit):
    if len(rows) <= limit:
        return rows
    first = limit // 2
    return [*rows[:first], *rows[-(limit - first):]]


def _legacy_trades(receipt):
    for session in receipt["sessions"]:
        for path in ("e0", "e1"):
            execution = session["paths"][path]["execution"]
            if execution["fill"] is not None:
                day = session["date"]
                yield {
                    "ref": f"trade:{path}:{day}", "path": path, "date": day,
                    **_select(execution, "status", "reason"),
                    **_select(execution["fill"], "side", "quantity", "price", "fee", "gross"),
                }


def _signal(row):
    paths = {}
    for path, values in row["paths"].items():
        outcome = values["next_open"]
        paths[path] = {
            **_select(values, "action", "quantity", "gate_reason"),
            "candidate": _select(values["candidate"] or {}, "action", "quantity"),
            "next_open": _select(outcome, "status", "reason", "trade_ref",
                                 *(("date",) if outcome["status"] not in ("OUTSIDE_WINDOW", "NO_INTENT") else ())),
        }
    stock = row["stock"] or {}
    return {
        **_select(row, "date", "common_evaluable", "direct_market_block", "candidate_difference",
                  "prior_filter_signal_ref"),
        "stock": {**_select(stock, "status", "signal"),
                  **_select(stock.get("conditions") or {}, "fast_average", "slow_average", "above_slow_average")},
        "market": _select(row["market"], "status", "close", "average", "above_average"),
        "paths": paths,
    }


def _segment(row):
    return {
        **_select(row, "start", "end", "net_difference", "return_contribution", "cost_difference",
                  "slippage_difference"),
        "paths": {path: {**_select(detail, "nav_change", "costs", "slippage_cost"),
                         "trade_refs": _endpoints(detail["trade_refs"], 4)}
                  for path, detail in row["paths"].items()},
    }


def _drawdown(row):
    points = row["positions"]
    phases = ("opening", "after_execution", "closing")
    selected = [point for point in points if len({point[phase]["total_shares"] for phase in phases}) > 1]
    if points:
        selected = [points[0], *(point for point in selected if point not in (points[0], points[-1]))]
        if len(points) > 1:
            selected.append(points[-1])
    return {
        **_select(row, "path", "status", "magnitude", "peak_date", "trough_date", "peak_nav", "trough_nav"),
        "position_changes": [
            {"date": point["date"], "opening_shares": point["opening"]["total_shares"],
             "after_execution_shares": point["after_execution"]["total_shares"],
             "closing_shares": point["closing"]["total_shares"], "trade_ref": point["trade_ref"]}
            for point in _endpoints(selected, 10)
        ],
        "gap_refs": _endpoints(row["gap_refs"], 4),
    }


def _public_evidence(receipt):
    attribution = receipt.get("attribution", {})
    evidence, counts = {}, {}

    def add(kind, total, rows):
        evidence.update(rows)
        counts[kind] = {"available": total, "included": len(rows)}

    signals = attribution.get("signals", [])
    direct = [row for row in signals if row["direct_market_block"]]
    different = [row for row in signals if row["candidate_difference"] and not row["direct_market_block"]]
    difference_samples = [*_endpoints(direct, 6), *_endpoints(different, 6)]

    segments = attribution.get("segments", [])
    largest = sorted(segments, key=lambda row: abs(Decimal(row["net_difference"] or 0)), reverse=True)
    important_trades = {path["next_open"]["trade_ref"] for row in difference_samples for path in row["paths"].values()}
    if largest:
        for path in largest[0]["paths"].values():
            important_trades.update(_endpoints(path["trade_refs"], 4))

    trades = attribution.get("trades")
    if trades is None:
        trades = list(_legacy_trades(receipt))
    primary = [row for row in trades if row["ref"] in important_trades]
    remaining = [row for row in trades if row["ref"] not in important_trades]
    trade_samples = [*primary, *_endpoints(remaining, 40 - len(primary))]
    add("trades", len(trades), {
        row["ref"]: _select(row, "path", "date", "signal_ref", "status", "reason", "side", "quantity",
                            "intended_quantity", "price", "fee", "gross", "slippage_cost")
        for row in trade_samples
    })

    cited = {row["signal_ref"] for row in trade_samples if "signal_ref" in row}
    cited_signals = [row for row in signals if row["ref"] in cited]
    signal_samples = [*difference_samples, *_endpoints(cited_signals, 10)]
    add("signals", len(signals), {row["ref"]: _signal(row) for row in signal_samples})
    add("segments", len(segments), {row["ref"]: _segment(row) for row in largest[:12]})
    drawdowns = attribution.get("drawdowns", {})
    add("drawdowns", len(drawdowns), {row["ref"]: _drawdown(row) for row in drawdowns.values()})

    gaps = attribution.get("gaps", {})
    if not gaps:
        gaps = {f"#/coverage/path_gaps/{index}": gap for index, gap in enumerate(receipt["coverage"]["path_gaps"])}
    groups = {}
    for ref, gap in gaps.items():
        key = (gap.get("feature"), gap["phase"], gap["reason"], tuple(gap.get("paths", ())))
        groups.setdefault(key, []).append((ref, gap))
    representatives = [(rows[0][0], {**_select(rows[0][1], "date", "feature", "phase", "reason", "paths",
                                               "observation_quality", "affected_metrics"),
                                      "similar_records": len(rows)}) for rows in groups.values()]
    representatives.sort(key=lambda pair: pair[1]["phase"] == "signal_coverage")
    add("gaps", len(gaps), dict(representatives[:18]))
    return evidence, counts


def _sources(snapshot):
    # The full audit stays on the receipt. Identifiers with path syntax and
    # arbitrary import notes never become model instructions or local locators.
    def label(value):
        return re.fullmatch(r"[\w.-]{1,64}", value or "") is not None

    return [
        {**_select(source, "series", "symbol", "first_received_at", "last_received_at"),
         "source": source["source"] if label(source["source"]) else None,
         "revisions": [revision for revision in source["revisions"] if label(revision)][:8]}
        for source in snapshot["sources"][:16]
    ]


def public_development_input(manifest, receipt):
    """Select compact evidence for the assistant from the immutable development receipt."""
    snapshot = receipt["snapshot"]
    sample = receipt["sample"]
    opportunities = receipt["opportunities"]
    metrics = {f"metric:{path}:{name}": values[name]
               for path, values in receipt["metrics"].items() for name in METRICS}
    evidence, counts = _public_evidence(receipt)
    divergence = opportunities["path_divergence"]
    coverage = receipt["coverage"]
    attribution = receipt.get("attribution", {})
    comparison = _select(attribution.get("comparison", {}), "classification", "total_net_difference",
                         "attributed_net_difference", "residual_net_difference", "total_cost_difference",
                         "total_slippage_difference", "dominant_segment_ref", "dominant_absolute_share")
    for name, value in comparison.items():
        if name not in ("classification", "dominant_segment_ref"):
            metrics[f"#/attribution/comparison/{name}"] = value
    for name in ("nominal_signal_days", "common_evaluable_days", "coverage_loss_days"):
        metrics[f"#/opportunities/{name}"] = opportunities[name]
    for name in ("blocked_buy_count", "eligible_e1_buy_candidates"):
        metrics[f"#/opportunities/market_filter/{name}"] = opportunities["market_filter"][name]
    return {
        **_select(manifest, "kind", "symbol", "as_of", "question", "snapshot_id"),
        "receipt_id": receipt["receipt_id"], "frozen_input_ref": receipt["input_ref"],
        "preset": {**_select(receipt["preset"], "id", "e0", "e1", "signal_time", "execution_time"),
                   "initial_cash_cny": receipt["preset"]["protocol"]["initial_cash_cny"]},
        "window": _select(sample, "nominal_window", "effective_window"),
        "snapshot": {
            **_select(snapshot, "use_mode", "selection_rules_version", "availability_basis", "risks",
                      "external_data_requests", "paid_data_cost_cny"),
            "sources": _sources(snapshot),
        },
        "metric_basis": receipt["metric_basis"],
        "metric_scopes": {path: values["metric_scope"] for path, values in receipt["metrics"].items()},
        "coverage": {
            **_select(opportunities, "nominal_signal_days", "common_evaluable_days", "coverage_loss_days",
                      "coverage_losses_by_reason", "warmup_days_by_feature"),
            "path_gap_count": len(coverage["path_gaps"]), "input_scope_gaps": coverage["input_scope_gaps"],
        },
        "opportunities": {
            **_select(opportunities, "evaluable_buy_candidates", "buy_candidates_blocked_by_coverage"),
            "market_filter": _select(opportunities["market_filter"], "blocked_buy_count",
                                     "eligible_e1_buy_candidates", "common_evaluable_signal_days"),
            "path_divergence": {
                "pre_gate_candidate_difference_count": divergence["pre_gate_candidate_difference_count"],
                "final_action_difference_count": len(divergence["final_action_difference_dates"]),
                "next_open_difference_count": len(divergence["next_open_difference_signal_dates"]),
                "next_open_fill_difference_count": len(divergence["next_open_fill_difference_signal_dates"]),
            },
        },
        "out_of_window_intents": list(receipt["boundary"]["pending_intents"]),
        "comparison": comparison,
        "attribution_basis": attribution.get("basis", {}),
        "metrics": metrics,
        "evidence": evidence,
        "evidence_coverage": counts,
        "evidence_metric_fields": EVIDENCE_METRIC_FIELDS,
    }


def _known_gaps(public):
    return bool(public["coverage"]["path_gap_count"] or public["coverage"]["input_scope_gaps"])


def offline_interpretation(public):
    """The built-in offline executor verifies delivery with a reproducible descriptive observation."""
    refs = ["metric:e0:costs", "metric:e1:costs"]
    matching_ref = next((ref for ref in public["evidence"] if ref.startswith(("trade:", "signal:", "segment:"))), None)
    gaps = [{
        "reason": "冻结回执记录了路径或输入范围缺口，受影响指标的口径以回执为准。",
        "required_evidence": "缺口日期的估值、撮合或权益依据",
        "evidence_refs": [ref for ref, item in public["evidence"].items()
                          if item.get("phase") in ("valuation", "execution", "entitlement", "decision")],
    }] if _known_gaps(public) else []
    return {
        "claims": [{
            "interpretation": "两条模拟路径的交易费用见引述指标。",
            "metrics": [{"ref": ref, "value": public["metrics"][ref]} for ref in refs],
            "evidence_refs": [matching_ref] if matching_ref else [],
        }],
        "uncertainties": ["结论局限于冻结开发窗口和模拟成交口径。"],
        "gaps": gaps,
        "follow_up": [],
    }


def _metric_value(public, ref):
    if ref in public["metrics"]:
        return public["metrics"][ref]
    item, _, field = ref.partition("#")
    allowed = public["evidence_metric_fields"].get(item.partition(":")[0], ())
    if field in allowed:
        return public["evidence"][item][field]
    raise KeyError(ref)


def prepare_development_report(result, attempt, public):
    reply = DevelopmentReply.model_validate(result, strict=True).model_dump()
    if not reply["claims"] and not reply["gaps"]:
        raise ValueError("开发解读须提供有冻结依据的结论或证据缺口")
    if _known_gaps(public) and not reply["gaps"]:
        raise ValueError("开发解读须说明冻结回执中的路径或输入范围缺口")
    if any(not text.strip() for text in (*reply["uncertainties"], *reply["follow_up"])):
        raise ValueError("研究局限和后续线索须有明确说明")
    located = set(public["evidence"])
    claims = reply["claims"]
    timing_refs = {ref for ref in located if ref.startswith(("trade:", "signal:", "segment:"))}
    if claims and timing_refs and not any(timing_refs.intersection(claim["evidence_refs"]) for claim in claims):
        raise ValueError("开发结论须定位冻结回执中的成交、信号或区段")
    for claim in claims:
        for metric in claim["metrics"]:
            try:
                expected = _metric_value(public, metric["ref"])
            except KeyError:
                raise ValueError("开发解读引用了冻结公开输入以外的指标") from None
            value = metric["value"]
            if type(expected) is not type(value) or expected != value:
                raise ValueError("开发解读的指标数值与冻结回执不符")
    for entry in (*claims, *reply["gaps"]):
        if not located.issuperset(entry["evidence_refs"]):
            raise ValueError("开发解读引用了冻结公开输入以外的依据")
    report = {"receipt_id": public["receipt_id"], "attempt_id": attempt["attempt_id"], **reply}
    return {**report, "version": "development-report-" + sha256(json_text(report).encode()).hexdigest()}
