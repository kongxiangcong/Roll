"""Fixed, long-only daily-bar experiment, separate from research family budgets."""
from decimal import Decimal, ROUND_HALF_UP
import math


def backtest(rows):
    if len(rows) < 25:
        raise ValueError('AT_LEAST_25_DAILY_ROWS_REQUIRED')
    days = [r['date'] for r in rows]
    if days != sorted(set(days)):
        raise ValueError('DUPLICATE_OR_UNORDERED_DAYS')
    for r in rows:
        values = [float(r[k]) for k in ['open', 'high', 'low', 'close', 'preclose', 'volume']]
        if not all(math.isfinite(v) for v in values) or min(values[:5]) <= 0 or values[-1] < 0:
            raise ValueError('INVALID_PRICE_OR_VOLUME')
        o, h, l, c = values[:4]
        if not l <= min(o, c) <= max(o, c) <= h or r['adjustflag'] != '3':
            raise ValueError('INVALID_RAW_OHLC')
        if r['isST'] != '0' or r['tradestatus'] not in {'0', '1'}:
            raise ValueError('ONLY_ORDINARY_MAIN_BOARD_SCOPE')
    # The first slice deliberately uses an action-free tail. Never execute adjusted prices,
    # or silently treat an ex-dividend gap as a trading loss.
    cuts = [i for i in range(1, len(rows)) if abs(float(rows[i]['preclose']) - float(rows[i-1]['close'])) > .011]
    cut = cuts[-1] if cuts else 0
    excluded = days[:cut]
    rows = rows[cut:]
    if len(rows) < 25:
        raise ValueError('INSUFFICIENT_ACTION_FREE_TAIL')
    closes = [float(r['close']) for r in rows]

    def simulate(buy_hold=False):
        cash, qty, highwater, drawdown = 100000., 0, 100000., 0.
        trades, curve, nofill = [], [], []
        for i in range(20, len(rows)):
            r = rows[i]
            # Signal uses only completed rows before this day's opening auction.
            want = buy_hold or sum(closes[i-5:i])/5 > sum(closes[i-20:i])/20
            side = 'BUY' if want and qty == 0 else 'SELL' if not want and qty else None
            if side:
                o, lo, hi, pre = (float(r[k]) for k in ['open', 'low', 'high', 'preclose'])
                upper = float((Decimal(r['preclose'])*Decimal('1.10')).quantize(Decimal('.01'), rounding=ROUND_HALF_UP))
                lower = float((Decimal(r['preclose'])*Decimal('.90')).quantize(Decimal('.01'), rounding=ROUND_HALF_UP))
                px = float((Decimal(str(o))*Decimal('1.0005' if side == 'BUY' else '.9995')).quantize(Decimal('.01'), rounding=ROUND_HALF_UP))
                reason = None
                if r['tradestatus'] != '1' or float(r['volume']) <= 0:
                    reason = 'SUSPENDED_OR_ZERO_VOLUME'
                elif hi == lo or (side == 'BUY' and o >= upper) or (side == 'SELL' and o <= lower):
                    reason = 'LIMIT_OR_ONE_PRICE_NO_FILL'
                elif not lo <= px <= hi or not lower <= px <= upper:
                    reason = 'SLIPPAGE_PRICE_OUTSIDE_BAR'
                amount = int(cash / (px * 100)) * 100 if side == 'BUY' else qty
                def cost(n):
                    gross = n * px
                    return round(max(5., gross * .0003) + gross * .00001 + (gross * .0005 if side == 'SELL' else 0), 2)
                if side == 'BUY':
                    while amount > 0 and amount * px + cost(amount) > cash:
                        amount -= 100
                if amount > float(r['volume']) * .01:
                    reason = 'VOLUME_PARTICIPATION_EXCEEDED'
                if reason or amount == 0:
                    nofill.append({'date': r['date'], 'side': side, 'reason': reason or 'INSUFFICIENT_CASH'})
                else:
                    fee = cost(amount)
                    cash = round(cash + (amount*px if side == 'SELL' else -amount*px) - fee, 2)
                    qty = amount if side == 'BUY' else 0
                    trades.append({'date': r['date'], 'signal_date': rows[i-1]['date'], 'side': side, 'quantity': amount, 'price': px, 'fee': fee, 'cash_after': cash})
            nav = round(cash + qty*closes[i], 2)
            highwater = max(highwater, nav)
            drawdown = min(drawdown, nav/highwater-1)
            curve.append({'date': r['date'], 'nav': nav, 'cash': cash, 'quantity': qty})
        return {'return_pct': round((curve[-1]['nav']/100000-1)*100, 4), 'max_drawdown_pct': round(drawdown*100, 4),
                'trades': trades, 'nav': curve, 'no_fills': nofill, 'open_quantity': qty,
                'final_valuation': 'LAST_CLOSE_MARK_TO_MARKET_NO_FORCED_LIQUIDATION'}
    return {'version': 'sma5-20-next-open-v1', 'initial_cash': 100000, 'signal': 'SMA5 > SMA20 => long; otherwise cash; next session open',
            'data_start': rows[0]['date'], 'start': rows[20]['date'], 'end': rows[-1]['date'], 'excluded_before_action_free_tail': excluded,
            'warmup_rows': 20, 'strategy': simulate(), 'buy_hold': simulate(True), 'cash_return_pct': 0,
            'assumptions': ['未复权人民币价格；股数单位股；100股整手；每天仅一次开盘交易，T+1。',
                '假设普通主板10%涨跌停；触及方向涨跌停、单一价、停牌、零成交或滑点越界不成交。特殊临时交易规则未独立核验。',
                '佣金万3最低5元，过户费十万1，卖出印花税万5，双向5bp滑点；均为可复现假设，非用户券商实际费率。',
                '仅使用最后一次昨收/前日收盘不连续之后的窗口；公司行为完整性依赖供应商口径，非总收益或严格历史时点证明。',
                '最大成交量参与率1%；日线不能验证真实排队和成交概率；未做参数优化或收益显著性证明。',
                '基准与策略同日起点、同一费用与成交约束；期末持仓按收盘估值，不强制卖出。']}
