"""Post-close market score shared by the workbench, frozen reports and historical replay."""
from datetime import date, timedelta
from math import isfinite
from pathlib import Path
from statistics import fmean

from roll.db import connect
from roll.market.calendar import is_session
from roll.market.daily import initialize_market
from roll.market.inputs import BROAD_ETFS, initialize_inputs, input_rows

WEIGHTS = {"trend": 35, "funding": 30, "breadth": 20, "valuation": 15}
FEATURES = {
    "trend": {"close_ma20": "沪深 300 收盘与 MA20", "close_ma60": "沪深 300 收盘与 MA60",
              "close_ma120": "沪深 300 收盘与 MA120", "ma20_ma60": "MA20 与 MA60",
              "ma60_ma120": "MA60 与 MA120", "volatility_rank": "沪深 300 波动分位（270 个收盘）",
              "turnover_confirmation": "两市成交额确认（20 个交易日）"},
    "funding": {"flow_z5": "四只宽基 ETF 份额与单位净值（5 日净流量 Z）",
                "flow_z20": "四只宽基 ETF 份额与单位净值（20 日净流量 Z）",
                "margin10": "两市两融余额（连续 11 日）", "margin5": "两市两融余额（连续 6 日）"},
    "breadth": {"breadth5": "全市场涨跌家数（连续 5 日有效分母）"},
    "valuation": {"pe_rank": "沪深 300 PE(TTM)（连续 1260 日）", "pb_rank": "沪深 300 PB（连续 1260 日）"},
}
DEVIATION = ((-.05, 0), (0, 50), (.05, 100))
FLOW = ((-2, 0), (-.5, 25), (0, 50), (.5, 75), (2, 100))
VALUATION = ((0, 100), (.30, 80), (.40, 50), (.70, 50), (.85, 25), (1, 15))


def interpolate(value, nodes):
    if value <= nodes[0][0]:
        return nodes[0][1]
    for (left, low), (right, high) in zip(nodes, nodes[1:]):
        if value <= right:
            return low + (high - low) * (value - left) / (right - left)
    return nodes[-1][1]


def regime_for_score(score):
    if not 0 <= score <= 100:
        raise ValueError("市场分数须在 0 至 100 之间")
    if score < 25:
        return "防守", .15
    if score < 50:
        return "谨慎", .35
    if score < 75:
        return "均衡", .60
    return "进攻", .80


def _dimension(name, f):
    if name == "trend":
        price = fmean(interpolate(f[key], DEVIATION) for key in ("close_ma20", "close_ma60", "close_ma120"))
        alignment = fmean(interpolate(f[key], DEVIATION) for key in ("ma20_ma60", "ma60_ma120"))
        volatility = interpolate(f["volatility_rank"], ((0, 100), (.50, 50), (.85, 25), (1, 0)))
        turnover = interpolate(f["turnover_confirmation"], ((-.5, 0), (0, 50), (.5, 100)))
        return fmean((price, alignment, volatility, turnover))
    if name == "funding":
        flows = fmean(interpolate(f[key], FLOW) for key in ("flow_z5", "flow_z20"))
        margin = min(interpolate(f["margin10"], DEVIATION),
                     interpolate(f["margin5"], ((-.04, 0), (-.02, 25), (0, 100))))
        return fmean((flows, margin))
    if name == "breadth":
        return interpolate(f["breadth5"], ((0, 0), (.40, 25), (.50, 50), (.55, 75), (1, 100)))
    return fmean(interpolate(f[key], VALUATION) for key in ("pe_rank", "pb_rank"))


def score_features(features):
    dimensions, missing = {}, []
    for name, required in FEATURES.items():
        gaps = [label for key, label in required.items()
                if features.get(key) is None or not isfinite(features[key])]
        missing.extend(gaps)
        dimensions[name] = None if gaps else _dimension(name, features)
    available = {name: WEIGHTS[name] for name, value in dimensions.items() if value is not None}
    weight = sum(available.values())
    score = sum(dimensions[k] * w for k, w in available.items()) / weight if weight >= 65 else None
    regime, cap = regime_for_score(score) if score is not None else (None, None)
    return {"status": "今日晴雨表不可用" if score is None else "可用", "dimensions": dimensions,
            "coverage": weight / 100, "score": score, "regime": regime, "position_cap": cap, "missing": missing}


def _sessions(start, end):
    """Include up to 1259 verified prior sessions for the longest feature window."""
    first, last = date.fromisoformat(start), date.fromisoformat(end)
    if first > last:
        raise ValueError("起始日期晚于截止日")
    cursor, warmup = first - timedelta(days=1), []
    while len(warmup) < 1259 and cursor.year >= 2013:
        if is_session(cursor):
            warmup.append(cursor.isoformat())
        cursor -= timedelta(days=1)
    days = warmup[::-1]
    cursor = first
    while cursor <= last:
        if is_session(cursor):
            days.append(cursor.isoformat())
        cursor += timedelta(days=1)
    return days


def _feature_history(db, days):
    import pandas as pd

    def series(rows, field):
        observations = {row["trade_date"]: row[field] for row in rows if field in row}
        values = pd.to_numeric(pd.Series(observations, dtype="object"), errors="coerce").reindex(days)
        return values.astype(float).replace([float("inf"), float("-inf")], float("nan"))

    def read(group, symbol):
        return input_rows(db, group, symbol, days[0], days[-1])

    def percentile(values, window):
        # Average rank assigns ties their midpoint. Subtracting half a rank
        # gives (strictly lower + half of ties) / N on a full session window.
        return (values.rolling(window).rank(method="average") - .5) / window

    bars = db.execute("SELECT trade_date, close_raw FROM daily_bars WHERE symbol='000300.SH' "
                      "AND trade_date BETWEEN ? AND ? ORDER BY trade_date", (days[0], days[-1]))
    close = series((dict(row) for row in bars), "close_raw")
    close = close.where(close > 0)
    features = {}
    averages = {n: close.rolling(n).mean() for n in (20, 60, 120)}
    for n, average in averages.items():
        features[f"close_ma{n}"] = close / average - 1
    features["ma20_ma60"] = averages[20] / averages[60] - 1
    features["ma60_ma120"] = averages[60] / averages[120] - 1
    volatility = close.pct_change(fill_method=None).rolling(20).std(ddof=0) * 252 ** .5
    features["volatility_rank"] = percentile(volatility, 250)
    turnover = series(read("turnover", "CN"), "turnover_yuan")
    turnover = turnover.where(turnover >= 0)
    activity = turnover / turnover.rolling(20).mean() - 1
    confirmed = activity.where(close >= averages[20], -activity.abs())
    features["turnover_confirmation"] = confirmed.mask(
        (close == averages[20]) & activity.notna(), 0).where(close.notna() & averages[20].notna())

    flows = []
    for symbol in BROAD_ETFS:
        shares = series(read("etf_shares", symbol), "shares")
        nav = series(read("etf_nav", symbol), "nav")
        flows.append(shares.where(shares >= 0).diff() * nav.where(nav > 0))
    flow = sum(flows)
    for n in (5, 20):
        total = flow.rolling(n).sum()
        baseline = total.rolling(250)
        mean, std = baseline.mean(), baseline.std(ddof=0)
        features[f"flow_z{n}"] = ((total - mean) / std).mask((std == 0) & (total == mean), 0)
    margin = series(read("margin", "CN"), "balance_yuan")
    margin = margin.where(margin >= 0)
    for n in (5, 10):
        prior = margin.shift(n)
        features[f"margin{n}"] = (margin / prior.where(prior > 0) - 1).where(margin.rolling(n + 1).count() == n + 1)

    breadth = read("breadth", "CN")
    up, down = series(breadth, "advancing"), series(breadth, "declining")
    counts = (up >= 0) & (down >= 0) & (up % 1 == 0) & (down % 1 == 0)
    features["breadth5"] = (up / (up + down).where((up + down) > 0)).where(counts).rolling(5).mean()
    valuation = read("valuation", "000300.SH")
    for column, key in (("pe_ttm", "pe_rank"), ("pb", "pb_rank")):
        values = series(valuation, column)
        features[key] = percentile(values.where(values > 0), 1260)
    return pd.DataFrame(features, index=days)


def scores_in_transaction(db, start: str, end: str):
    days = _sessions(start, end)
    if not days or days[-1] < start:
        return []
    history = _feature_history(db, days).loc[start:end]
    return [{"trade_date": day, **score_features(features)} for day, features in
            zip(history.index, history.to_dict(orient="records"))]


def barometer_history(data_dir: Path, start: str, end: str):
    with connect(data_dir / "roll.sqlite3") as db:
        initialize_market(db)
        initialize_inputs(db)
        db.execute("BEGIN")
        return scores_in_transaction(db, start, end)


def barometer_at(data_dir: Path, trade_date: str):
    rows = barometer_history(data_dir, trade_date, trade_date)
    if not rows:
        raise ValueError("请选择交易日")
    return rows[0]
