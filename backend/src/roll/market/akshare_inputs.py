"""AKShare field mapping for dated mainland-market inputs."""
from datetime import date, timedelta
from decimal import Decimal
from functools import cached_property


def number(value):
    parsed = Decimal(str(value))
    if not parsed.is_finite() or parsed < 0:
        raise ValueError("缺失或无效的市场数据")
    return parsed


def compact(day):
    return day.replace("-", "")


def dated(value):
    return date.fromisoformat(str(value)[:10]).isoformat()


class AkshareInputs:
    def __init__(self, sdk=None):
        self._sdk = sdk
        self._shanghai_shares = {}

    @cached_property
    def sdk(self):
        if self._sdk is not None:
            return self._sdk
        import akshare

        return akshare

    def calendar(self):
        from roll.market.calendar import is_session, SSE_HISTORICAL_HOLIDAYS

        # Use the shared exchange calendar for years covered by the annual notices.
        # Extend the calendar from AKShare when the bundled notices run out.
        first = date(min(SSE_HISTORICAL_HOLIDAYS), 1, 1)
        last = date(2026, 12, 31)
        days = []
        day = first
        while day <= last:
            if is_session(day):
                days.append(day.isoformat())
            day += timedelta(days=1)
        if date.today() > last:
            observed = self.sdk.tool_trade_date_hist_sina().to_dict("records")
            days.extend(dated(r["trade_date"]) for r in observed if dated(r["trade_date"]) > last.isoformat())
        return days

    def bars(self, symbol, days):
        code, exchange = symbol.split(".")
        rows = self.sdk.fund_etf_hist_sina(symbol=exchange.lower() + code).to_dict("records")
        for row in rows:
            day = dated(row["date"])
            if days[0] <= day <= days[-1]:
                prices = {key: number(row[key]) for key in ("open", "high", "low", "close")}
                if (prices["low"] <= 0 or prices["low"] > min(prices["open"], prices["close"])
                        or prices["high"] < max(prices["open"], prices["close"])):
                    continue
                yield day, {key: str(value) for key, value in prices.items()}

    def shares(self, symbol, days):
        code, exchange = symbol.split(".")
        if exchange == "SH":
            for day in days:
                if day not in self._shanghai_shares:
                    frame = self.sdk.fund_etf_scale_sse(date=compact(day))
                    # AKShare already converts SSE's ten-thousand-unit figure to units.
                    self._shanghai_shares[day] = {
                        r["基金代码"]: r["基金份额"] for r in frame.to_dict("records")
                        if dated(r["统计日期"]) == day}
                if code in self._shanghai_shares[day]:
                    yield day, {"shares": str(number(self._shanghai_shares[day][code]))}
        elif exchange == "SZ":
            # The exchange limits each query to six calendar months.
            for i in range(0, len(days), 75):
                window = days[i:i + 75]
                frame = self.sdk.fund_scale_daily_szse(start_date=compact(window[0]),
                                                       end_date=compact(window[-1]), symbol="ETF")
                for row in frame.to_dict("records"):
                    if row["基金代码"] == code:
                        yield dated(row["日期"]), {"shares": str(number(row["基金份额"]))}
        else:
            raise ValueError("未知交易所")

    def nav(self, symbol, days):
        frame = self.sdk.fund_etf_fund_info_em(fund=symbol.split(".")[0],
                                              start_date=compact(days[0]), end_date=compact(days[-1]))
        for row in frame.to_dict("records"):
            value = number(row["单位净值"])
            if value > 0:
                yield dated(row["净值日期"]), {"nav": str(value)}

    def breadth(self, symbol, days):
        frame = self.sdk.stock_market_activity_legu()
        row = {r["item"]: r["value"] for r in frame.to_dict("records")}
        day = dated(row["统计日期"])
        if day in days:
            yield day, {"advancing": str(number(row["上涨"])), "declining": str(number(row["下跌"]))}

    def turnover(self, symbol, days):
        for day in days:
            sh = self.sdk.stock_sse_deal_daily(date=compact(day)).to_dict("records")
            sz = self.sdk.stock_szse_summary(date=compact(day)).to_dict("records")
            amount = next(r for r in sh if r["单日情况"] == "成交金额")
            amounts = {r["证券类别"]: r["成交金额"] for r in sz}
            # Exclude B shares, ETFs and buybacks. Shenzhen SME board was separate until 2021.
            sz_a = number(amounts["主板A股"]) + number(amounts["创业板A股"]) + number(amounts.get("中小板", 0))
            sh_a = number(amount["主板A"]) + number(amount["科创板"])
            yield day, {"turnover_yuan": str(sh_a * 100_000_000 + sz_a)}

    def valuation(self, symbol, days):
        pe = self.sdk.stock_index_pe_lg(symbol="沪深300").to_dict("records")
        pb = self.sdk.stock_index_pb_lg(symbol="沪深300").to_dict("records")
        price_book = {dated(r["日期"]): r["市净率"] for r in pb}
        for row in pe:
            day = dated(row["日期"])
            if days[0] <= day <= days[-1] and day in price_book:
                earnings, book = number(row["滚动市盈率"]), number(price_book[day])
                if earnings > 0 and book > 0:
                    yield day, {"pe_ttm": str(earnings), "pb": str(book)}

    def margin(self, symbol, days):
        sh = self.sdk.stock_margin_sse(start_date=compact(days[0]), end_date=compact(days[-1]))
        daily = {dated(r["信用交易日期"]): number(r["融资融券余额"]) for r in sh.to_dict("records")}
        for day in days:
            if day not in daily:
                continue
            sz = self.sdk.stock_margin_szse(date=compact(day)).to_dict("records")
            if len(sz) == 1:
                yield day, {"balance_yuan": str(daily[day] + number(sz[0]["融资融券余额"]) * 100_000_000)}
