#!/usr/bin/env python3
"""周期股估值参照带：把"某个价格水平对应什么估值"算成一张可复算的表。

为什么要有这个脚本：周期股的利润是价格的函数，所以"估值贵不贵"这个问题没法脱离
"当时价格在哪"单独回答。只报"PB 处 98.7% 分位"解决不了问题 —— 读者要的是
"胶价 1.3 万 / 1.8 万 / 4 万时，各自大致对应什么位置"。这张表就是回答它。

打印五节，只算参照不做判断：
  1. 区间实证：把历史每一天按品种价格分档，统计每档内的 PB 分布（25/50/75 分位），
     再按当前每股净资产折成每股参照区间。
  2. 盈利阶梯：以"基准年度正常化归母净利 + 价格敏感度"推每个价格档的正常化净利与 ROE，
     并标出该档落在历史价格区间内还是外。
  3. 盈亏平衡价：净利恰好为零的价格，附一档"基准利润变了它会移动多少"的杠杆表。
  4. 预期反算：当前市值若按 N 倍正常化盈利定价，需要多少净利、对应什么价格。
  5. 稳健性检查：分年 PB 中位数，判断样本期内有没有体制断裂。

红线：输出的是 **参照区间与推算过程**，不是目标价、不是买卖建议。
脚本不产出任何"合理价位""高估/低估"的措辞，报告里也不许出现。

口径前提（2026-10-15 补，踩过坑）：
  敏感度覆盖的主体，与基准利润覆盖的主体，**可能不是同一个**。本脚本二者都收，
  但不会替你检查。二者不一致时（自产端的敏感度 ÷ 集团口径的基准利润），
  解出来的"盈亏平衡价"只在"除价格外其余一切不变"的假设下成立，**它是价格水平，不是成本**。
  报告里出现这个数，必须带上限定词与假设，并给出杠杆表上的移动幅度。

用法：
    python3 scripts/cycle_valuation.py \
        --valuation outputs/<项目>/02-工作底稿/估值序列.json \
        --prices    outputs/<项目>/02-工作底稿/沪胶价格序列.json \
        --equity 95.0 --shares 42.7943 \
        --self-output 104200 --base-price 15564 --base-profit -15.95 \
        --sensitivity-scope 自产 10.42 万吨 --base-profit-scope 集团口径

金融股（保险、银行）用法 —— 利润对利率不是线性关系，后三节不能算，走 band-only：
    python3 scripts/cycle_valuation.py \
        --valuation outputs/<项目>/02-工作底稿/估值序列_601318.json \
        --prices    outputs/<项目>/02-工作底稿/国债收益率序列_bp.json \
        --equity 10004.19 --shares 181.0764 \
        --band-only --xlabel "10 年期国债收益率（基点）" \
        --bands "0-160,160-200,200-240,240-280,280-320,320-1000"
此时 --base-price / --base-profit / --self-output / --sensitivity / --tiers / --pe-grid 都可省略。

数据来源约定（与 references/03 一致）：
  --valuation  东方财富 RPT_VALUEANALYSIS 逐日序列，含 CLOSE_PRICE / PB_MRQ / TOTAL_SHARES
  --prices     品种主力连续合约日收盘序列，格式 [{d: 'YYYY-MM-DD', c: 价格}, ...]
               利率轴同理，把 c 换成当日 10 年期国债收益率（基点）即可
"""

import argparse
import json
import statistics
import sys

# 合同要求的口径声明：不给就在输出里打警示，但不阻断——避免把"忘了写"变成"跑不了"。
DEFAULT_MIN_BAND_SAMPLES = 60
BAND_WARN_SAMPLES = 120     # 低于这个天数提示分位不够稳
REGIME_DEV_MULT = 3.0       # 年度中位数偏离聚类标准差超过 3 倍，判体制断裂


def die(msg):
    """可读的报错，统一走非零退出码；不要让它变成原始堆栈。"""
    raise SystemExit(f"参数或数据有问题：{msg}")


def load_valuation(path):
    """读估值序列，返回 {日期: (收盘价, PB, 总股本)}。"""
    rows = json.load(open(path, encoding="utf-8"))
    out = {}
    for r in rows:
        date = str(r["TRADE_DATE"])[:10]
        out[date] = (
            float(r["CLOSE_PRICE"]),
            float(r["PB_MRQ"]),
            float(r.get("TOTAL_SHARES") or 0),
        )
    return out


def load_prices(path):
    """读品种价格序列，返回 {日期: 价格}。字段名兼容 d/c 与 date/close 两套写法。"""
    rows = json.load(open(path, encoding="utf-8"))
    out = {}
    for r in rows:
        date = str(r.get("d") or r.get("date"))[:10]
        out[date] = float(r.get("c") or r.get("close"))
    return out


def quantile(sorted_values, p):
    """线性插值分位数。样本量小的时候，插值比取整位置稳。"""
    if not sorted_values:
        return None
    if len(sorted_values) == 1:
        return sorted_values[0]
    pos = (len(sorted_values) - 1) * p
    lo, hi = int(pos), min(int(pos) + 1, len(sorted_values) - 1)
    return sorted_values[lo] + (sorted_values[hi] - sorted_values[lo]) * (pos - lo)


def join(valuation, prices, start=None):
    """按日期取交集，并返回一份覆盖率报告。

    价格序列比交易日序列长是常态，交集才是可用样本。start 用于剔除体制不一致的年份。
    PB ≤ 0 的观测一律丢弃（净资产为负时市净率没有经济含义），但**丢弃了多少要报出来**——
    静默丢样本，是分档统计被悄悄扭曲的常见原因。
    """
    common = sorted(d for d in set(valuation) & set(prices) if not start or d >= start)
    dropped = [d for d in common if not valuation[d][1] > 0]
    rows = [(d, prices[d], valuation[d][0], valuation[d][1])
            for d in common if valuation[d][1] > 0]
    return rows, {
        "valuation_days": len(valuation),
        "price_days": len(prices),
        "common": len(common),
        "dropped_pb": len(dropped),
        "dropped_dates": dropped[:5],
    }


def band_table(rows, bands, bps, min_samples, xlabel="价格（元/吨）"):
    """区间实证法：按 x 轴分档统计 PB 分布，再折成每股参照区间。

    x 轴通常是品种价格；金融股可以换成利率（基点）——那时只有本函数与
    regime_table 有意义，盈利阶梯与盈亏平衡段不适用。"""
    print(f"\n【一】区间实证：历史各 {xlabel} 档位下的 PB 分布")
    print("（PB 为市净率；每股 = PB × **当前**每股净资产 %.4f 元。"
          "这一列是按今天的净资产刻度换算的历史市净率，不是历史股价的复现）\n" % bps)
    print(f"| {xlabel}档 | 样本天数 | PB 25 分位 | PB 中位 | PB 75 分位 | 每股 25 分位 | 每股中位 | 每股 75 分位 |")
    print("|---|---|---|---|---|---|---|---|")
    thin, short = [], []
    for lo, hi in bands:
        subset = sorted(r[3] for r in rows if lo <= r[1] < hi)
        label = f"{lo:,.0f}–{hi:,.0f}" if hi < 10**8 else f"≥{lo:,.0f}"
        if len(subset) < min_samples:
            print(f"| {label} | {len(subset)} | 样本不足（下限 {min_samples} 天），不出分位 | | | | | |")
            short.append(label)
            continue
        if len(subset) < BAND_WARN_SAMPLES:
            thin.append(f"{label}（{len(subset)} 天）")
        q25, q50, q75 = (quantile(subset, p) for p in (0.25, 0.5, 0.75))
        print(
            f"| {label} | {len(subset)} | {q25:.2f} | {q50:.2f} | {q75:.2f} "
            f"| {q25 * bps:.2f} | {q50 * bps:.2f} | {q75 * bps:.2f} |"
        )
    if thin:
        print(f"\n警示：以下档位样本在 {min_samples}~{BAND_WARN_SAMPLES} 天之间，"
              f"分位数不够稳（抽 {min_samples} 点重抽样，75 分位可摆动约 0.6~1.0 个 PB）："
              + "、".join(thin))
        print("这一档的天数必须写进报告；同一档位里 1,100 天与 74 天得出的结论分量完全不同。")
    if short:
        print(f"警示：以下档位样本不足、未出分位，对应价格区间**没有实证支撑**：" + "、".join(short))
    meds = [quantile(sorted(r[3] for r in rows if lo <= r[1] < hi), 0.5)
            for lo, hi in bands]
    meds = [m for m in meds if m is not None]
    if len(meds) >= 3 and any(meds[i] > meds[i + 1] for i in range(len(meds) - 1)):
        print("\n注意：分档中位数不是单调的（低价档的 PB 高于相邻中价档）。"
              "先看【六】的分年表再下结论——多半是年份构成造成的，不是价格效应。"
              "样本期短的档位尤其要查这一点。")
    return short


def price_range(rows):
    """样本内价格的极值，用来标外推。"""
    ps = [r[1] for r in rows]
    return min(ps), max(ps)


def profit_ladder(tiers, sensitivity, base_price, base_profit, equity, price_lo, price_hi):
    """盈利阶梯：正常化净利 = 基准净利 + (价格 − 基准价格) × 敏感度。"""
    print("\n【二】盈利阶梯：各价格档下的正常化归母净利与 ROE")
    print("（敏感度：价格每变动 1,000 元/吨，归母净利变动 %.4f 亿元）" % sensitivity)
    print("（“是否在样本内”看的是该档价格有没有落在历史价格区间 %.0f–%.0f 元/吨之内）\n"
          % (price_lo, price_hi))
    print("| 价格（元/吨） | 相对基准价格变动 | 正常化归母净利（亿元） | ROE | 是否在样本内 |")
    print("|---|---|---|---|---|")
    out = []
    outside = []
    for p in tiers:
        profit = base_profit + sensitivity * (p - base_price) / 1000.0
        roe = profit / equity * 100.0
        in_sample = price_lo <= p <= price_hi
        if not in_sample:
            outside.append(p)
        out.append((p, profit, roe))
        print(f"| {p:,.0f} | {p - base_price:+,.0f} | {profit:+.2f} | {roe:+.1f}% "
              f"| {'是' if in_sample else '**否，外推**'} |")
    if outside:
        print("\n警示：以下档位**超出历史价格区间**，是线性外推、不是统计："
              + "、".join(f"{p:,.0f}" for p in outside))
        print(f"  外推距离最大的一档是基准价的 {max(outside) / base_price:.2f} 倍。"
              "报告里必须写明“这是外推，不是统计”，并退回上一轮周期的极值锚。")
    return out, outside


def breakeven(sensitivity, base_price, base_profit, price_lo, price_hi):
    """解盈亏平衡价：基准净利 + 敏感度 × (价格 − 基准价格) / 1000 = 0。"""
    price = base_price + (-base_profit) / sensitivity * 1000.0
    print(f"\n【三】盈亏平衡价：正常化归母净利恰好为零的价格 ≈ {price:,.0f} 元/吨")
    print("  这是价格水平，不是成本；只在“除价格外其余一切不变”的假设下成立。")
    if price > price_hi:
        print(f"  警示：该价格是样本内最高价 {price_hi:,.0f} 的 {price / price_hi:.2f} 倍，"
              "属纯外推，须与假设和移动幅度一起写进报告。")
    if price < price_lo:
        print(f"  警示：该价格低于样本内最低价 {price_lo:,.0f}，检查敏感度与基准利润的口径。")
    return price


def leverage_table(sensitivity, base_price, base_profit):
    """法四：把基准利润放大一倍、缩小一半，看平衡价移动多少。

    口径错配最常见的后果，就是平衡价对基准利润的杠杆极大——挪一个假设结论走一半，
    这样的结论不能单独报出去。
    """
    print("\n【四】平衡价的杠杆：基准利润换个假设，它会移动多少")
    print("（用来检查“这个结论稳不稳”。移动幅度大的，报告里必须把假设摆在结论旁边）\n")
    print("| 基准利润（亿元） | 相对原假设 | 盈亏平衡价（元/吨） | 与原值之差 |")
    print("|---|---|---|---|")
    base_price_eq = base_price + (-base_profit) / sensitivity * 1000.0
    for label, factor in (("× 0.5", 0.5), ("× 1.0（原假设）", 1.0), ("× 2.0", 2.0)):
        bp = base_profit * factor
        price = base_price + (-bp) / sensitivity * 1000.0
        print(f"| {bp:+.2f} | {label} | {price:,.0f} | {price - base_price_eq:+,.0f} |")
    print(f"\n偏导：基准利润每变动 1 亿元，平衡价移动 {-1000.0 / sensitivity:,.0f} 元/吨。")


def reverse_expectation(market_cap, sensitivity, base_price, base_profit, pe_grid, price_hi):
    """预期反算：当前市值按 N 倍正常化盈利定价，需要多少净利、对应什么价格。"""
    print("\n【五】预期反算：当前市值需要多高的价格才能被盈利解释")
    print(f"（当前市值 {market_cap:.2f} 亿元）\n")
    print("| 隐含 PE | 需要的正常化归母净利（亿元） | 对应价格（元/吨） | 是否在样本内 |")
    print("|---|---|---|---|")
    for pe in pe_grid:
        need = market_cap / pe
        price = base_price + (need - base_profit) / sensitivity * 1000.0
        print(f"| {pe} 倍 | {need:.2f} | {price:,.0f} | {'是' if price <= price_hi else '**否，外推**'} |")


def regime_table(rows, xlabel="价格"):
    """稳健性检查：把样本按年切开，看同一价格档在不同年份的 PB 是否一致。"""
    print("\n【六】稳健性检查：分年 PB 中位数与当年价格区间")
    print("（同一价格在不同年份若给出不同的 PB，说明存在体制断裂，分档统计只能当参照）\n")
    print(f"| 年份 | 样本天数 | {xlabel}区间 | {xlabel}均值 | PB 中位 | 偏离聚类 |")
    print("|---|---|---|---|---|---|")
    by_year = {}
    for d, price, _, pb in rows:
        by_year.setdefault(d[:4], []).append((price, pb))
    medians = {}
    for year in sorted(by_year):
        vals = by_year[year]
        prices = [v[0] for v in vals]
        medians[year] = quantile(sorted(v[1] for v in vals), 0.5)
    if len(medians) >= 3:
        # 用中位数年份的邻域做聚类基准：取各年中位数，再取中位数所在的那一段。
        allmed = sorted(medians.values())
        cluster = [m for m in allmed if abs(m - statistics.median(allmed)) <= 0.35]
        base = statistics.median(cluster) if len(cluster) >= 3 else statistics.median(allmed)
        sd = statistics.pstdev(cluster) if len(cluster) >= 3 else statistics.pstdev(allmed)
        for year in sorted(by_year):
            vals = by_year[year]
            prices = [v[0] for v in vals]
            dev = medians[year] - base
            flag = ""
            if sd > 0 and abs(dev) > REGIME_DEV_MULT * sd:
                flag = "**体制断裂**"
            print(f"| {year} | {len(vals)} | {min(prices):,.0f}–{max(prices):,.0f} "
                  f"| {statistics.mean(prices):,.0f} | {medians[year]:.2f} "
                  f"| {dev:+.2f}{flag} |")
        if sd > 0:
            print(f"\n聚类基准 {base:.2f}，聚类标准差 {sd:.3f}；偏离超过 "
                  f"{REGIME_DEV_MULT * sd:.2f}（三倍）判体制断裂。")
            broken = [y for y in medians if abs(medians[y] - base) > REGIME_DEV_MULT * sd]
            if broken:
                print(f"**命中：{'、'.join(sorted(broken))} 年与前后的体制不同。** "
                      "断裂在样本首端的，用 `--start` 从其之后重跑，并把剔除理由写进局限说明；"
                      "断裂落在样本末端的（最近这一年），说明它已经进入新体制，"
                      "该读数**只能代表新体制、不得与旧体制混算**，报告里要分开写。")
    else:
        print("（样本不足三年，不做体制断裂判定）")


def parse_bands(text):
    """解析 "0-12000,12000-15000,18000-99999" 形式的分档。"""
    bands = []
    for chunk in text.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        parts = chunk.split("-")
        if len(parts) != 2:
            die(f"价格分档写法不对：{chunk!r}，应形如 0-12000")
        try:
            lo, hi = float(parts[0]), float(parts[1])
        except ValueError:
            die(f"价格分档不是数字：{chunk!r}")
        if lo >= hi:
            die(f"价格分档起点不小于终点：{chunk!r}")
        bands.append((lo, hi))
    if not bands:
        die("价格分档为空")
    return bands


def parse_floats(text, what, positive=True):
    out = []
    for chunk in text.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        try:
            v = float(chunk)
        except ValueError:
            die(f"{what} 不是数字：{chunk!r}")
        if positive and v <= 0:
            die(f"{what} 必须为正数，收到 {v}")
        out.append(v)
    if not out:
        die(f"{what} 为空")
    return out


def main():
    ap = argparse.ArgumentParser(description="周期股估值参照带（只算参照，不给判断）")
    ap.add_argument("--valuation", required=True, help="估值序列 JSON（东财逐日）")
    ap.add_argument("--prices", required=True, help="品种价格序列 JSON")
    ap.add_argument("--equity", type=float, required=True,
                    help="归母净资产（亿元，已剔除其他权益工具/永续债，与行情 PB 口径一致）")
    ap.add_argument("--shares", type=float, required=True, help="总股本（亿股）")
    ap.add_argument("--self-output", type=float, help="自产量（吨/年）；与 --sensitivity 二选一")
    ap.add_argument("--sensitivity", type=float,
                    help="价格每变动 1,000 元/吨对应的归母净利变动（亿元）。用于双产品装置、"
                         "或敏感度需按历史实测校准的品种；给了它就忽略 --self-output/--tax")
    ap.add_argument("--sensitivity-scope", default="（未声明）",
                    help="敏感度覆盖的主体范围，如“自产 10.42 万吨”。写给读者看，不参与计算")
    ap.add_argument("--base-profit-scope", default="（未声明）",
                    help="基准利润覆盖的主体范围，如“集团口径”。与上一项不一致时，"
                         "平衡价的名称必须带限定词")
    ap.add_argument("--start", default=None, help="样本起始日期（含），用于剔除体制不一致的年份")
    ap.add_argument("--tax", type=float, default=0.15, help="所得税率，取值域 [0, 1)，默认 0.15")
    ap.add_argument("--base-price", type=float, default=None,
                    help="基准年度均价（元/吨）；--band-only 时可省略")
    ap.add_argument("--base-profit", type=float, default=None,
                    help="基准年度正常化归母净利（亿元，已剔除非经常性项）；--band-only 时可省略")
    ap.add_argument("--tiers", default="12000,13000,15000,18000,22000,33600,40000",
                    help="要出参照的价格档，逗号分隔")
    ap.add_argument("--pe-grid", default="15,20,25", help="反算用的隐含 PE")
    ap.add_argument("--bands", default="0-12000,12000-15000,15000-18000,18000-22000,22000-1000000",
                    help="区间实证法的价格分档")
    ap.add_argument("--min-band-samples", type=int, default=DEFAULT_MIN_BAND_SAMPLES,
                    help=f"单个价格档出分位所需的最少天数，默认 {DEFAULT_MIN_BAND_SAMPLES}")
    ap.add_argument("--band-only", action="store_true",
                    help="只出【一】区间实证与【六】稳健性检查。金融股把利率当横轴时用这个："
                         "利润对利率不是线性关系，盈利阶梯与盈亏平衡段不适用")
    ap.add_argument("--xlabel", default="价格（元/吨）",
                    help="横轴的名字，如「10 年期国债收益率（基点）」。只影响表头与措辞，不参与计算")
    args = ap.parse_args()

    # 输入校验：域外取值会静默产出荒谬结果（负数价格、翻转符号），一律前置拦掉。
    if not args.equity > 0:
        die("--equity 必须为正数")
    if not args.shares > 0:
        die("--shares 必须为正数")
    if args.band_only:
        # 这两项在只出区间实证时用不到，给了也只用它做域外取值检查。
        if args.base_price is not None and args.base_price <= 0:
            die("--base-price 必须为正数")
    else:
        if args.base_price is None or not args.base_price > 0:
            die("--base-price 必须为正数（只有 --band-only 模式才能省略）")
        if args.base_profit is None:
            die("--base-profit 为必填（只有 --band-only 模式才能省略）")
    if not 0 <= args.tax < 1:
        die("--tax 必须在 [0, 1) 区间内")
    if args.min_band_samples < 1:
        die("--min-band-samples 至少为 1")
    bands = parse_bands(args.bands)
    if args.band_only:
        # 后三节（盈利阶梯 / 平衡价 / 隐含 PE 反算）都建立在"价格→利润"的线性敏感度上。
        # 这一支不输出它们，所以不解析、也不校验这三组参数。
        tiers = pe_grid = sensitivity = None
        sens_note = ""
    else:
        tiers = parse_floats(args.tiers, "价格档")
        pe_grid = parse_floats(args.pe_grid, "隐含 PE")
        if args.sensitivity is not None:
            if not args.sensitivity > 0:
                die("--sensitivity 必须为正数")
            sensitivity = args.sensitivity
            sens_note = "（直接给定，非按自产量推算）"
        else:
            if args.self_output is None:
                die("--self-output 与 --sensitivity 至少要给一个")
            if not args.self_output > 0:
                die("--self-output 必须为正数")
            # 敏感度 = 自产量 × 1,000 元/吨 × (1 − 税率) ÷ 1e8。
            # 前面那个 1,000 不能省：不乘它就变成"每 1 元/吨"的敏感度，盈亏平衡价会被放大一千倍。
            sensitivity = args.self_output * 1000 * (1 - args.tax) / 1e8
            sens_note = f"（自产 {args.self_output:,.0f} 吨 × (1 − {args.tax:.0%})）"

    try:
        valuation = load_valuation(args.valuation)
        prices = load_prices(args.prices)
    except FileNotFoundError as e:
        die(f"找不到数据文件：{e.filename}")
    except (KeyError, ValueError, json.JSONDecodeError) as e:
        die(f"数据文件格式不对（{type(e).__name__}: {e}）")

    rows, cov = join(valuation, prices, args.start)
    if len(rows) < 250:
        die(f"可用样本只有 {len(rows)} 天，不足一个交易年，统计没有意义。"
            "检查 --start 是否切得太晚，或两条序列是否覆盖同一时期")

    bps = args.equity / args.shares
    price_lo, price_hi = price_range(rows)

    print(f"样本区间 {rows[0][0]} ~ {rows[-1][0]}，共 {len(rows)} 个交易日")
    print(f"覆盖率：估值序列 {cov['valuation_days']} 天，价格序列 {cov['price_days']} 天，"
          f"日期交集 {cov['common']} 天，因 PB ≤ 0 丢弃 {cov['dropped_pb']} 天"
          + (f"（例：{'、'.join(cov['dropped_dates'])}）" if cov["dropped_pb"] else ""))
    axis = args.xlabel
    print(f"样本内{axis}区间：{price_lo:,.0f} ~ {price_hi:,.0f}")
    print(f"每股净资产 {bps:.4f} 元（归母净资产 {args.equity} 亿元 ÷ 总股本 {args.shares} 亿股）")
    if sensitivity is not None:
        print(f"{axis}敏感度：每 1,000 元/吨 → 归母净利 {sensitivity:.4f} 亿元{sens_note}")
        print(f"　口径声明：敏感度覆盖「{args.sensitivity_scope}」；"
              f"基准利润覆盖「{args.base_profit_scope}」")
        if args.sensitivity_scope != args.base_profit_scope and "（未声明）" in (
                args.sensitivity_scope, args.base_profit_scope):
            print("　**两者口径未声明或可能不一致。平衡价只在“除价格外其余一切不变”下成立，"
                  "报告里必须带限定词，不得写成成本。**")
    else:
        print(f"（--band-only 模式：不计算{axis}敏感度，故不输出口径声明）")

    band_table(rows, bands, bps, args.min_band_samples, args.xlabel)

    if args.band_only:
        # 金融股（利率当横轴）走这一支：利润对利率不是线性关系，
        # 强行按"每 1,000 元/吨"外推会得到没有经济含义的阶梯与平衡价。
        regime_table(rows, args.xlabel)
        print("\n提示：--band-only 模式只出区间实证与稳健性检查。盈利阶梯、盈亏平衡价与临界价反算"
              "需要一条价格到利润的线性敏感度，保险与其他金融股不满足该前提，故不输出。")
        print("参照带的其余刻度（PEV、营运利润、PB-ROE）请在报告里按 references/05 与 07 的"
              "金融型方法手算，并把推导链、样本区间、假设清单、局限说明一并写入；"
              "口径检查见 references/12。")
        return

    profit_ladder(tiers, sensitivity, args.base_price, args.base_profit, args.equity,
                  price_lo, price_hi)
    breakeven(sensitivity, args.base_price, args.base_profit, price_lo, price_hi)
    leverage_table(sensitivity, args.base_price, args.base_profit)

    # 市值口径：优先用估值序列自带的股本真值，命令行值只作交叉校验。
    last_date = max(valuation)
    close, _, shares_json = valuation[last_date]
    # 接口给的总股本是"股"，命令行习惯用"亿股"，先归一化再比。
    shares_json_yi = shares_json / 1e8 if shares_json > 1e6 else shares_json
    if shares_json_yi > 0 and abs(shares_json_yi - args.shares) / args.shares > 0.005:
        print(f"\n警示：命令行股本 {args.shares} 亿股与估值序列自带的 "
              f"{shares_json_yi:.4f} 亿股（{last_date}）相差超过 0.5%，"
              "市值与每股净资产都按命令行值算的，请确认哪个是当期股本；"
              "增发或回购过的公司尤其要查这一步。")
    market_cap = close * args.shares
    print(f"市值口径：{last_date} 收盘价 {close:.2f} 元 × "
          f"总股本 {args.shares} 亿股 = {market_cap:.2f} 亿元")
    reverse_expectation(market_cap, sensitivity, args.base_price, args.base_profit,
                        pe_grid, price_hi)
    regime_table(rows)

    print("\n提示：以上全部是在某假设下算出来的参照，不是目标价。写进报告时必须同时给出"
          "样本区间、假设清单与局限说明（见 references/05 的《估值参照带》一节）；"
          "分子分母口径不一致的推算值须降级，见 references/12。")


if __name__ == "__main__":
    main()
